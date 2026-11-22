import logging
import os
import ssl
from pathlib import Path

import httpx
import pytest
import trustme
from conftest import Env
from fastapi.testclient import TestClient
from helpers import FakeOcr, post

import app.llm
from app.config import ConfigError, Settings, load_settings
from app.errors import ModelUnavailable
from app.llm import OpenAICompatLLM
from app.main import _build_llm, create_app
from app.tls import model_ssl_context

HTTPS = "https://model.test:8743/v1"


def _tls_env(tmp_path: Path, ca: trustme.CA, client: trustme.LeafCert) -> dict[str, str]:
    paths = {name: tmp_path / name for name in ("tls.crt", "tls.key", "ca.crt")}
    client.cert_chain_pems[0].write_to_path(str(paths["tls.crt"]))
    client.private_key_pem.write_to_path(str(paths["tls.key"]))
    ca.cert_pem.write_to_path(str(paths["ca.crt"]))
    return {
        "LLM_PROVIDER": "openai_compat",
        "LLM_BASE_URL": HTTPS,
        "LLM_MODEL": "m",
        "LLM_TLS_CERT_FILE": str(paths["tls.crt"]),
        "LLM_TLS_KEY_FILE": str(paths["tls.key"]),
        "LLM_TLS_CA_FILE": str(paths["ca.crt"]),
    }


@pytest.fixture
def ca() -> trustme.CA:
    return trustme.CA()


@pytest.fixture
def tls_env(tmp_path: Path, ca: trustme.CA) -> dict[str, str]:
    return _tls_env(tmp_path, ca, ca.issue_cert("brevkoll-client"))


@pytest.mark.ac("AC1")
@pytest.mark.control("T2")
def test_context_trusts_only_the_configured_ca(tls_env: dict[str, str]) -> None:
    ctx = model_ssl_context(load_settings(tls_env))
    assert ctx is not None
    (only,) = ctx.get_ca_certs()
    pinned = ssl.create_default_context(cafile=tls_env["LLM_TLS_CA_FILE"]).get_ca_certs()
    assert only["subject"] == pinned[0]["subject"]
    assert ctx.check_hostname is True
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.minimum_version >= ssl.TLSVersion.TLSv1_2


@pytest.mark.control("T5")
def test_no_tls_settings_gives_no_context() -> None:
    assert model_ssl_context(load_settings({})) is None


@pytest.mark.control("T3")
def test_key_that_does_not_match_cert_is_config_error(tmp_path: Path, ca: trustme.CA) -> None:
    env = _tls_env(tmp_path, ca, ca.issue_cert("brevkoll-client"))
    other = tmp_path / "other.key"
    ca.issue_cert("someone-else").private_key_pem.write_to_path(str(other))
    env["LLM_TLS_KEY_FILE"] = str(other)
    with pytest.raises(ConfigError) as info:
        _build_llm(load_settings(env))
    message = str(info.value)
    assert "LLM_TLS_CERT_FILE" in message and "LLM_TLS_KEY_FILE" in message
    assert "BEGIN" not in message


@pytest.mark.control("T3")
def test_garbage_cert_file_is_config_error(tmp_path: Path, tls_env: dict[str, str]) -> None:
    Path(tls_env["LLM_TLS_CERT_FILE"]).write_text("not a certificate")
    with pytest.raises(ConfigError):
        _build_llm(load_settings(tls_env))


@pytest.mark.control("T5")
def test_build_llm_with_tls_returns_openai_compat_client(
    env: Env, tls_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert isinstance(_build_llm(load_settings(tls_env)), OpenAICompatLLM)
    calls: list[Settings] = []
    real = app.llm.model_ssl_context

    def recording(settings: Settings) -> ssl.SSLContext | None:
        calls.append(settings)
        return real(settings)

    monkeypatch.setattr(app.llm, "model_ssl_context", recording)
    for key, value in tls_env.items():
        monkeypatch.setenv(key, value)
    create_app(ocr=FakeOcr())
    assert calls == [load_settings(os.environ)]
    assert calls[0].llm_tls_cert_file == Path(tls_env["LLM_TLS_CERT_FILE"])


@pytest.mark.control("T4")
@pytest.mark.control("T5")
def test_tls_failure_is_502_and_logs_no_secrets(env: Env, caplog: pytest.LogCaptureFixture) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            "certificate verify failed: CN=front-end -----BEGIN", request=request
        )

    http = httpx.Client(transport=httpx.MockTransport(handler))
    llm = OpenAICompatLLM(HTTPS, "m", http, "sk-test")
    caplog.set_level(logging.DEBUG)
    response = post(TestClient(create_app(ocr=FakeOcr(), llm=llm), raise_server_exceptions=False))
    assert response.status_code == 502
    assert response.json() == {"error": ModelUnavailable.message}
    for secret in ("CN=front-end", "BEGIN", "sk-test"):
        assert secret not in caplog.text
