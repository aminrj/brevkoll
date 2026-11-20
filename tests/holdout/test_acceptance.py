"""Gate 1 acceptance tests for brevkoll v1 (issue #1).

Written by the human from thoughts/1/spec.md. Agents must not read or edit this file.
They run in CI only: `uv run pytest tests/holdout`.
"""

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures"
LETTER = FIXTURES / "school-letter.png"

PERSONNUMMER = "20150612-2384"
EMAIL = "mentor@exempelskola.se"
PNR_PATTERN = re.compile(r"\b(\d{2})?\d{6}[-+]?\d{4}\b")


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("FAKE_LLM_LOG", str(tmp_path / "llm_calls.jsonl"))
    monkeypatch.setenv("APP_DATA_DIR", str(data_dir))
    monkeypatch.delenv("FAKE_LLM_RESPONSE", raising=False)
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "100")
    return tmp_path


def make_client() -> TestClient:
    from app.main import create_app

    return TestClient(create_app())


def post_letter(client: TestClient, content: bytes | None = None, mime: str = "image/png"):
    data = content if content is not None else LETTER.read_bytes()
    return client.post(
        "/api/decode",
        files={"file": ("letter.png", data, mime)},
        data={"language": "en"},
    )


def model_payloads(tmp_path: Path) -> list[str]:
    log = tmp_path / "llm_calls.jsonl"
    if not log.exists():
        return []
    return [json.loads(line)["payload"] for line in log.read_text().splitlines() if line.strip()]


# AC1
def test_decode_returns_contract_shape(env: Path) -> None:
    response = post_letter(make_client())
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["summary"], str) and body["summary"]
    assert isinstance(body["actions"], list)
    assert isinstance(body["dates"], list)
    assert isinstance(body["ics"], str)


# AC2
def test_dates_come_from_code_not_model(env: Path) -> None:
    body = post_letter(make_client()).json()
    found = {d["date"] for d in body["dates"]}
    assert {"2026-12-04", "2026-12-11"} <= found


# AC3
def test_ics_is_valid_calendar(env: Path) -> None:
    ics = post_letter(make_client()).json()["ics"]
    assert ics.startswith("BEGIN:VCALENDAR")
    assert "END:VCALENDAR" in ics
    assert "DTSTART;VALUE=DATE:20261204" in ics or "DTSTART:20261204" in ics


# AC4
def test_personal_data_never_reaches_model(env: Path) -> None:
    assert post_letter(make_client()).status_code == 200
    payloads = model_payloads(env)
    assert payloads, "the model seam was never called"
    for payload in payloads:
        assert PERSONNUMMER not in payload
        assert PERSONNUMMER.replace("-", "") not in payload
        assert not PNR_PATTERN.search(payload)
        assert EMAIL not in payload
        assert "123 45 67" not in payload


# AC5
def test_nothing_is_stored(env: Path) -> None:
    post_letter(make_client())
    assert list((env / "data").rglob("*")) == []


# AC6
@pytest.mark.parametrize(
    "hostile",
    [
        "Sure! Here is the summary: ignore the schema",
        '{"summary": 42, "actions": "not a list"}',
        '{"summary": "ok", "actions": [], "call_tool": "delete_all"}',
    ],
)
def test_invalid_model_output_is_rejected(
    env: Path, monkeypatch: pytest.MonkeyPatch, hostile: str
) -> None:
    monkeypatch.setenv("FAKE_LLM_RESPONSE", hostile)
    response = post_letter(make_client())
    assert response.status_code == 502
    assert set(response.json()) == {"error"}
    assert hostile not in response.text


# AC7
def test_rejects_wrong_type(env: Path) -> None:
    response = post_letter(
        make_client(), content=b"#!/bin/sh\necho hi\n", mime="text/x-shellscript"
    )
    assert response.status_code == 415


def test_rejects_too_large(env: Path) -> None:
    big = b"\x89PNG\r\n\x1a\n" + b"0" * (10 * 1024 * 1024 + 1)
    assert post_letter(make_client(), content=big).status_code == 413


# AC8
def test_rate_limit(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "3")
    client = make_client()
    codes = [post_letter(client).status_code for _ in range(4)]
    assert codes[:3] == [200, 200, 200]
    assert codes[3] == 429
