import json
import ssl
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import trustme
from fastapi.testclient import TestClient

from app.config import load_settings
from app.errors import ModelUnavailable
from app.main import _build_llm, create_app

CONTENT = '{"summary": "ok", "actions": []}'
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
CLIENT_CN = "brevkoll-client"


class _Ocr:
    def extract(self, data: bytes, kind: str) -> str:
        return "Hej föräldrar! Anmäl senast 2026-12-04."


class _Server(ThreadingHTTPServer):
    """Model stand-in: requires a client certificate signed by the test CA."""

    def __init__(self, ctx: ssl.SSLContext) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.socket = ctx.wrap_socket(self.socket, server_side=True, do_handshake_on_connect=False)
        self.subjects: list[str] = []

    def handle_error(self, request: object, client_address: object) -> None:
        return  # refused handshakes are the point of some tests


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        assert isinstance(self.server, _Server) and isinstance(self.connection, ssl.SSLSocket)
        self.rfile.read(int(self.headers.get("content-length", "0")))
        peer = self.connection.getpeercert()
        self.server.subjects.append(str(peer.get("subject")) if peer else "")
        body = json.dumps({"choices": [{"message": {"content": CONTENT}}]}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


@contextmanager
def _serve(server_ca: trustme.CA, client_ca: trustme.CA) -> Iterator[_Server]:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.verify_mode = ssl.CERT_REQUIRED
    client_ca.configure_trust(ctx)
    server_ca.issue_cert("127.0.0.1").configure_cert(ctx)
    server = _Server(ctx)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def ca() -> trustme.CA:
    return trustme.CA()


@pytest.fixture
def server(ca: trustme.CA) -> Iterator[_Server]:
    with _serve(ca, ca) as running:
        yield running


def _env(server: _Server, tmp_path: Path, ca: trustme.CA, *, cert: bool) -> dict[str, str]:
    port = server.server_address[1]
    env = {
        "LLM_PROVIDER": "openai_compat",
        "LLM_BASE_URL": f"https://127.0.0.1:{port}/v1",
        "LLM_MODEL": "m",
        "APP_DATA_DIR": str(tmp_path),
    }
    ca_file = tmp_path / "ca.crt"
    ca.cert_pem.write_to_path(str(ca_file))
    env["LLM_TLS_CA_FILE"] = str(ca_file)
    if cert:
        client = ca.issue_cert(CLIENT_CN, common_name=CLIENT_CN)
        client.cert_chain_pems[0].write_to_path(str(tmp_path / "tls.crt"))
        client.private_key_pem.write_to_path(str(tmp_path / "tls.key"))
        env["LLM_TLS_CERT_FILE"] = str(tmp_path / "tls.crt")
        env["LLM_TLS_KEY_FILE"] = str(tmp_path / "tls.key")
    return env


def _complete(env: dict[str, str]) -> str:
    return _build_llm(load_settings(env)).complete("hi", max_tokens=50, timeout=5)


@pytest.mark.ac("AC1")
@pytest.mark.ac("AC3")
def test_call_succeeds_with_client_certificate(
    server: _Server, tmp_path: Path, ca: trustme.CA
) -> None:
    assert _complete(_env(server, tmp_path, ca, cert=True)) == CONTENT
    (subject,) = server.subjects
    assert f"('commonName', '{CLIENT_CN}')" in subject


@pytest.mark.ac("AC3")
@pytest.mark.control("T5")
def test_call_without_tls_settings_fails_without_crash(server: _Server, tmp_path: Path) -> None:
    port = server.server_address[1]
    env = {"LLM_PROVIDER": "openai_compat", "LLM_BASE_URL": f"https://127.0.0.1:{port}/v1"}
    with pytest.raises(ModelUnavailable):
        _complete(env | {"LLM_MODEL": "m"})


@pytest.mark.ac("AC3")
def test_ca_only_is_rejected_by_server_requiring_client_cert(
    server: _Server, tmp_path: Path, ca: trustme.CA
) -> None:
    with pytest.raises(ModelUnavailable):
        _complete(_env(server, tmp_path, ca, cert=False))
    assert server.subjects == []


@pytest.mark.control("T2")
def test_server_signed_by_other_ca_is_refused(tmp_path: Path, ca: trustme.CA) -> None:
    with _serve(trustme.CA(), ca) as other:
        with pytest.raises(ModelUnavailable):
            _complete(_env(other, tmp_path, ca, cert=True))
        assert other.subjects == []


@pytest.mark.ac("AC3")
def test_decode_through_the_app_over_mtls(
    server: _Server, tmp_path: Path, ca: trustme.CA, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key, value in _env(server, tmp_path, ca, cert=True).items():
        monkeypatch.setenv(key, value)
    client = TestClient(create_app(ocr=_Ocr()), raise_server_exceptions=False)
    response = client.post("/api/decode", files={"file": ("letter.png", PNG, "image/png")})
    assert response.status_code == 200
    assert response.json()["summary"] == "ok"
