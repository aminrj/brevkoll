import logging
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from helpers import FakeOcr, post

Make = Callable[..., TestClient]


def test_logs_contain_no_letter_ocr_or_model_text(
    make_client: Make, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(
        "FAKE_LLM_RESPONSE", '{"summary": "MODEL-SECRET-SUMMARY", "actions": ["MODEL-ACTION"]}'
    )
    ocr = FakeOcr("OCR-SECRET-WORDS 2026-12-04 anna@example.se")
    with caplog.at_level(logging.DEBUG):
        assert post(make_client(ocr)).status_code == 200
    text = caplog.text
    assert "decoded" in text  # something is logged
    for secret in ("OCR-SECRET-WORDS", "anna@example.se", "MODEL-SECRET-SUMMARY", "MODEL-ACTION"):
        assert secret not in text


def test_logs_contain_no_model_text_on_error(
    make_client: Make, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_LLM_RESPONSE", "MODEL-SECRET-GARBAGE")
    with caplog.at_level(logging.DEBUG):
        assert post(make_client(FakeOcr("OCR-SECRET-WORDS"))).status_code == 502
    assert "MODEL-SECRET-GARBAGE" not in caplog.text
    assert "OCR-SECRET-WORDS" not in caplog.text
