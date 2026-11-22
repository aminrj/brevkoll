"""Holdout: the model over mutual TLS (spec ACs 1-3).

Certificates are made with the openssl CLI in a temp folder.
"""

import json
import shutil
import ssl
import subprocess
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from app.config import ConfigError, load_settings
from app.main import _build_llm

ANSWER = {"choices": [{"message": {"content": "ok"}}]}
OPENSSL = shutil.which("openssl") or "/usr/bin/openssl"


def _openssl(*args: str, cwd: Path) -> None:
    # fixed arguments written in this file, no outside input
    subprocess.run([OPENSSL, *args], cwd=cwd, check=True, capture_output=True)  # noqa: S603


@pytest.fixture(scope="module")
def pki(tmp_path_factory: pytest.TempPathFactory) -> Path:
    d = tmp_path_factory.mktemp("pki")
    _openssl(
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-keyout",
        "ca.key",
        "-out",
        "ca.crt",
        "-days",
        "2",
        "-subj",
        "/CN=test-ca",
        "-addext",
        "basicConstraints=critical,CA:TRUE",
        "-addext",
        "keyUsage=critical,keyCertSign,cRLSign",
        cwd=d,
    )
    for name in ("server", "client"):
        _openssl(
            "req",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            f"{name}.key",
            "-out",
            f"{name}.csr",
            "-subj",
            f"/CN={name}",
            cwd=d,
        )
        ext = d / f"{name}.ext"
        server = name == "server"
        usage = (
            "subjectAltName=IP:127.0.0.1\nextendedKeyUsage=serverAuth"
            if server
            else ("extendedKeyUsage=clientAuth")
        )
        ext.write_text(usage + "\n")
        _openssl(
            "x509",
            "-req",
            "-in",
            f"{name}.csr",
            "-CA",
            "ca.crt",
            "-CAkey",
            "ca.key",
            "-CAcreateserial",
            "-out",
            f"{name}.crt",
            "-days",
            "2",
            "-extfile",
            ext.name,
            cwd=d,
        )
    return d


class _Model(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass

    def do_POST(self) -> None:  # noqa: N802
        self.rfile.read(int(self.headers.get("content-length") or 0))
        body = json.dumps(ANSWER).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture(scope="module")
def mtls_model(pki: Path) -> Iterator[str]:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Model)
    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH, cafile=str(pki / "ca.crt"))
    ctx.load_cert_chain(str(pki / "server.crt"), str(pki / "server.key"))
    ctx.verify_mode = ssl.CERT_REQUIRED  # like the front end: no client cert, no answer
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"https://127.0.0.1:{srv.server_address[1]}/v1"
    srv.shutdown()


def _env(base_url: str, **extra: str) -> dict[str, str]:
    return {
        "LLM_PROVIDER": "openai_compat",
        "LLM_BASE_URL": base_url,
        "LLM_MODEL": "m",
        "LLM_API_KEY": "k",
        **extra,
    }


def _tls(pki: Path) -> dict[str, str]:
    return {
        "LLM_TLS_CERT_FILE": str(pki / "client.crt"),
        "LLM_TLS_KEY_FILE": str(pki / "client.key"),
        "LLM_TLS_CA_FILE": str(pki / "ca.crt"),
    }


def test_tls_settings_load(pki: Path) -> None:  # AC1
    load_settings(_env("https://127.0.0.1:1/v1", **_tls(pki)))


@pytest.mark.parametrize("drop", ["LLM_TLS_CERT_FILE", "LLM_TLS_KEY_FILE"])
def test_cert_and_key_go_together(pki: Path, drop: str) -> None:  # AC2
    env = _env("https://127.0.0.1:1/v1", **_tls(pki))
    del env[drop]
    with pytest.raises(ConfigError) as err:
        load_settings(env)
    assert "LLM_TLS_" in str(err.value)


def test_a_missing_file_is_named(pki: Path) -> None:  # AC2
    env = _env("https://127.0.0.1:1/v1", **{**_tls(pki), "LLM_TLS_CA_FILE": str(pki / "no.crt")})
    with pytest.raises(ConfigError) as err:
        load_settings(env)
    assert "LLM_TLS_CA_FILE" in str(err.value)


def test_the_call_succeeds_with_the_client_cert(pki: Path, mtls_model: str) -> None:  # AC1 AC3
    llm = _build_llm(load_settings(_env(mtls_model, **_tls(pki))))
    assert llm.complete("hi", max_tokens=5, timeout=10) == "ok"


def test_without_the_cert_the_call_fails_cleanly(pki: Path, mtls_model: str) -> None:  # AC3
    llm = _build_llm(load_settings(_env(mtls_model, LLM_TLS_CA_FILE=str(pki / "ca.crt"))))
    with pytest.raises(Exception) as err:  # noqa: B017 - any client error: it must raise, not hang
        llm.complete("hi", max_tokens=5, timeout=10)
    assert not isinstance(err.value, SystemExit | KeyboardInterrupt)
