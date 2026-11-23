"""Holdout tests for issue #6: warn about OCR character errors on the result page.

Each test corresponds to one acceptance criterion. They must fail on the
current code and pass once the change is built.

This file is self-contained — it does not import from tests.unit so it can
live in thoughts/6/ before the factory moves it to tests/holdout/.
"""

import json
import re
import tempfile
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.llm import FakeLLM
from app.main import create_app
from app.redact import redact

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


class FakeOcr:
    """Minimal fake OCR that returns a fixed string."""

    def __init__(self, text: str = "Hej! Mejl: test@example.se. 2026-12-04.") -> None:
        self.text = text
        self.calls = 0

    def extract(self, data: bytes, kind: str) -> str:
        self.calls += 1
        return self.text


class Env:
    """Sets up env vars and temp dirs for the fake LLM."""

    def __init__(self, tmp_path: Path) -> None:
        self.data_dir = tmp_path / "data"
        self.data_dir.mkdir()
        self.tmp_dir = tmp_path / "tmp"
        self.tmp_dir.mkdir()
        self.log = tmp_path / "fake_llm.jsonl"

    def payloads(self) -> list[str]:
        if not self.log.exists():
            return []
        return [json.loads(line)["payload"] for line in self.log.read_text().splitlines()]


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Env:
    e = Env(tmp_path)
    monkeypatch.setattr(tempfile, "tempdir", str(e.tmp_dir))
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("APP_DATA_DIR", str(e.data_dir))
    monkeypatch.setenv("FAKE_LLM_LOG", str(e.log))
    monkeypatch.delenv("FAKE_LLM_RESPONSE", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    return e


@pytest.fixture
def make_client(env: Env) -> Callable[..., TestClient]:
    def make(ocr: FakeOcr | None = None) -> TestClient:
        app = create_app(ocr=ocr if ocr is not None else FakeOcr())
        return TestClient(app, raise_server_exceptions=False)

    return make


def _post_ui(client: TestClient) -> TestClient:
    """Helper: POST a PNG to /ui/decode and return the response."""
    return client.post(
        "/ui/decode",
        files={"file": ("letter.png", PNG, "image/png")},
        data={"language": "en"},
    )


def _post_api(client: TestClient) -> TestClient:
    """Helper: POST a PNG to /api/decode and return the response."""
    return client.post(
        "/api/decode",
        files={"file": ("letter.png", PNG, "image/png")},
        data={"language": "en"},
    )


def test_ac1_notice_mentions_email_and_ocr(make_client: Callable[..., TestClient]) -> None:
    """AC1: result page HTML contains a notice about email and OCR errors."""
    client = make_client()
    r = _post_ui(client)
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:200]}"
    body = r.text
    # The body must mention both "email" and "ocr" (case-insensitive).
    has_email = re.search(r"(?i)email", body)
    has_ocr = re.search(r"(?i)ocr", body)
    assert has_email and has_ocr, (
        "No notice mentioning both email and OCR errors found in result page"
    )


def test_ac2_api_contract_unchanged(make_client: Callable[..., TestClient]) -> None:
    """AC2: /api/decode response does not contain an ocr_warning field."""
    client = make_client()
    r = _post_api(client)
    assert r.status_code == 200
    body = r.json()
    assert "ocr_warning" not in body, "API response must not contain 'ocr_warning'"
    assert set(body.keys()) == {"summary", "actions", "dates", "ics"}


def test_ac3_notice_before_what_to_do(make_client: Callable[..., TestClient]) -> None:
    """AC3: the new notice appears before the 'What to do' heading."""
    client = make_client()
    r = _post_ui(client)
    assert r.status_code == 200
    body = r.text
    # Find the position of the first mention of email and the "What to do" heading.
    email_pos = re.search(r"(?i)email", body)
    what_to_do_match = re.search(r"<h2>What to do</h2>", body)
    assert email_pos, "No email mention found in result page (notice is missing)"
    assert what_to_do_match, "'What to do' heading not found"
    assert email_pos.start() < what_to_do_match.start(), (
        "OCR warning notice must appear before the 'What to do' heading"
    )
