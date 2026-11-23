"""Acceptance tests for issue #6: warn about OCR character errors on the result page."""

import os
import re
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import create_app


class _FakeOcr:
    def __init__(self, text: str = "Hej föräldrar! Anmäl senast 2026-12-04.") -> None:
        self.text = text
        self.calls = 0

    def extract(self, data: bytes, kind: str) -> str:
        self.calls += 1
        return self.text


def _make_client() -> TestClient:
    with patch.dict(os.environ, {"LLM_PROVIDER": "fake"}):
        return TestClient(create_app(ocr=_FakeOcr()), raise_server_exceptions=False)


def test_ac1_notice_mentions_email_and_ocr() -> None:
    """AC1: result page contains a <p class="notice"> whose text mentions both "email" and "OCR"."""
    client = _make_client()
    response = client.post(
        "/ui/decode",
        files={"file": ("letter.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 32, "image/png")},
        data={"language": "en"},
    )
    assert response.status_code == 200
    html = response.text
    notices = re.findall(r'<p class="notice"[^>]*>(.*?)</p>', html, re.S)
    assert len(notices) >= 2, f"Expected at least 2 notices, found {len(notices)}"
    combined = " ".join(notices)
    assert "email" in combined.lower(), "OCR warning notice should mention email"
    assert "ocr" in combined.lower(), "OCR warning notice should mention OCR"


def test_ac2_api_unchanged() -> None:
    """AC2: POST /api/decode JSON response has no ocr_warning field."""
    client = _make_client()
    response = client.post(
        "/api/decode",
        files={"file": ("letter.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 32, "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert "ocr_warning" not in body


def test_ac3_notice_before_what_to_do_heading() -> None:
    """AC3: the new notice element appears before the first <h2> on the result page."""
    client = _make_client()
    response = client.post(
        "/ui/decode",
        files={"file": ("letter.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 32, "image/png")},
        data={"language": "en"},
    )
    assert response.status_code == 200
    html = response.text
    # Find the position of the second notice (the OCR warning)
    # and the first <h2>
    first_h2 = html.index("<h2>")
    # The OCR warning notice should appear before the first <h2>
    assert re.search(r'<p class="notice"[^>]*>.*?ocr.*?</p>', html, re.S | re.I), (
        "OCR warning notice should exist"
    )
    ocr_notice_match = re.search(r'<p class="notice"[^>]*>.*?ocr.*?</p>', html, re.S | re.I)
    assert ocr_notice_match is not None
    assert ocr_notice_match.start() < first_h2, (
        "OCR warning notice should appear before the first <h2>"
    )
