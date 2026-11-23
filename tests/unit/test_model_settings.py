import logging

import httpx
import pytest
from conftest import Env
from fastapi.testclient import TestClient
from helpers import FakeOcr, post

from app.config import ConfigError, load_settings
from app.errors import ModelUnavailable
from app.llm import OpenAICompatLLM
from app.main import create_app

BASE = "http://model.local:8080/v1"
KEY = "a" * 24  # dummy, low entropy on purpose (gitleaks scans history)
REPLY = '{"summary": "Real summary.", "actions": ["Do it."]}'


def test_defaults_keep_the_old_behaviour() -> None:
    s = load_settings({})
    assert s.model_timeout_s == 120.0
    assert s.model_max_tokens == 3000
    assert s.llm_api_key is None


def test_values_are_read_from_env() -> None:
    s = load_settings({"MODEL_TIMEOUT_S": "120.5", "MODEL_MAX_TOKENS": "2000", "LLM_API_KEY": KEY})
    assert s.model_timeout_s == 120.5
    assert s.model_max_tokens == 2000
    assert s.llm_api_key is not None and s.llm_api_key.get_secret_value() == KEY


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("MODEL_TIMEOUT_S", "abc"),
        ("MODEL_TIMEOUT_S", "0"),
        ("MODEL_TIMEOUT_S", "601"),
        ("MODEL_MAX_TOKENS", "ten"),
        ("MODEL_MAX_TOKENS", "10"),
        ("MODEL_MAX_TOKENS", "8001"),
    ],
)
def test_bad_values_fail_at_startup(key: str, value: str) -> None:
    with pytest.raises(ConfigError):
        load_settings({key: value})


def test_key_is_masked_in_settings_repr() -> None:
    assert KEY not in repr(load_settings({"LLM_API_KEY": KEY}))


def _ok(seen: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": REPLY}}]})

    return httpx.MockTransport(handler)


def test_authorization_header_is_sent_only_when_a_key_is_set() -> None:
    seen: list[httpx.Request] = []
    with_key = OpenAICompatLLM(BASE, "m", httpx.Client(transport=_ok(seen)), KEY)
    without = OpenAICompatLLM(BASE, "m", httpx.Client(transport=_ok(seen)))
    with_key.complete("x", max_tokens=10, timeout=5.0)
    without.complete("x", max_tokens=10, timeout=5.0)
    assert seen[0].headers["authorization"] == f"Bearer {KEY}"
    assert "authorization" not in seen[1].headers


def test_key_never_reaches_a_response_or_a_log(env: Env, caplog: pytest.LogCaptureFixture) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text=f"upstream said {request.headers['authorization']}")

    llm = OpenAICompatLLM(BASE, "m", httpx.Client(transport=httpx.MockTransport(handler)), KEY)
    app = create_app(ocr=FakeOcr(), llm=llm)
    with caplog.at_level(logging.DEBUG):
        response = post(TestClient(app, raise_server_exceptions=False))
    assert response.status_code == 502
    assert response.json() == {"error": ModelUnavailable.message}
    assert KEY not in response.text
    assert KEY not in caplog.text


class RecordingLLM:
    def __init__(self) -> None:
        self.calls: list[tuple[int, float]] = []

    def complete(self, prompt: str, *, max_tokens: int, timeout: float) -> str:
        self.calls.append((max_tokens, timeout))
        return REPLY


def test_settings_reach_the_model_call(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_TIMEOUT_S", "90")
    monkeypatch.setenv("MODEL_MAX_TOKENS", "1500")
    llm = RecordingLLM()
    response = post(TestClient(create_app(ocr=FakeOcr(), llm=llm)))
    assert response.status_code == 200
    assert llm.calls == [(1500, 90.0)]


def test_unset_settings_use_the_old_constants(env: Env) -> None:
    llm = RecordingLLM()
    post(TestClient(create_app(ocr=FakeOcr(), llm=llm)))
    assert llm.calls == [(3000, 120.0)]
