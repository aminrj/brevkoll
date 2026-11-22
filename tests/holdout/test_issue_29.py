"""Holdout tests for issue #29: accept 256 KB PDFs without 'File too large'."""

import os
import tempfile
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.upload import MAX_BYTES


class FakeOcr:
    """OCR stand-in: these tests are about upload size, not text."""

    def extract(self, data: bytes, kind: str) -> str:
        return "Faktura 2026-12-01, belopp 100 kr."


@pytest.fixture()
def make_client() -> Callable[..., TestClient]:
    tmp = Path(tempfile.mkdtemp())
    data_dir = tmp / "data"
    data_dir.mkdir()
    tmp_dir = tmp / "tmp"
    tmp_dir.mkdir()
    log = tmp / "fake_llm.jsonl"
    log.write_text("")

    os.environ["LLM_PROVIDER"] = "fake"
    os.environ["APP_DATA_DIR"] = str(data_dir)
    os.environ["FAKE_LLM_LOG"] = str(log)
    os.environ["APP_ENV"] = "test"
    os.environ["TMPDIR"] = str(tmp_dir)

    from app.main import create_app

    def _make() -> TestClient:
        app = create_app(ocr=FakeOcr())
        return TestClient(app, raise_server_exceptions=False)

    return _make


PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32  # 40 bytes; the sizes below count it


def _post_png(client: TestClient, data: bytes) -> int:
    png_header = PNG_HEADER
    return client.post(
        "/api/decode",
        files={"file": ("letter.png", png_header + data, "image/png")},
    ).status_code


def test_ac1_256_kb_pdf_is_accepted(make_client: Callable[..., TestClient]) -> None:
    """AC1: A 256 KB PDF is accepted (not 413 or 500)."""
    client = make_client()
    pdf_body = b"x" * (256 * 1024 - 8)
    pdf = b"%PDF-1.4\n" + pdf_body
    r = client.post(
        "/api/decode",
        files={"file": ("letter.pdf", pdf, "application/pdf")},
    )
    assert r.status_code == 200, f"256 KB PDF was rejected with {r.status_code}: {r.text[:200]}"


def test_ac2_file_just_under_10_mb_is_accepted(make_client: Callable[..., TestClient]) -> None:
    """AC2: A file just under 10 MB is accepted."""
    client = make_client()
    under = MAX_BYTES - 1 - len(PNG_HEADER)  # the whole file is MAX_BYTES - 1
    assert under > 0
    code = _post_png(client, b"\x00" * under)
    assert code == 200, f"File {under} bytes was rejected with {code}"


def test_ac3_file_1_byte_over_10_mb_is_413(make_client: Callable[..., TestClient]) -> None:
    """AC3: A file 1 byte over 10 MB returns 413 with the right body."""
    client = make_client()
    over = MAX_BYTES + 1 - len(PNG_HEADER)  # the whole file is MAX_BYTES + 1
    r = client.post(
        "/api/decode",
        files={"file": ("letter.png", PNG_HEADER + b"\x00" * over, "image/png")},
    )
    assert r.status_code == 413, f"Expected 413, got {r.status_code}: {r.text[:200]}"
    assert r.json() == {"error": "File too large."}
