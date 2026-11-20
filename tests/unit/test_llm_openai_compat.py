import json
from collections.abc import Callable

import httpx
import pytest
from conftest import Env
from fastapi.testclient import TestClient
from helpers import FakeOcr, post

from app.config import ConfigError
from app.errors import ModelUnavailable
from app.llm import OpenAICompatLLM
from app.main import create_app

BASE = "http://model.local:8080/v1"
REPLY = '{"summary": "Real summary.", "actions": ["Do it."]}'


def make_llm(handler: Callable[[httpx.Request], httpx.Response]) -> OpenAICompatLLM:
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return OpenAICompatLLM(BASE, "test-model", http)


def ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": REPLY}}]})


def test_request_has_token_cap_timeout_and_no_tools() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return ok(request)

    assert make_llm(handler).complete("hello", max_tokens=123, timeout=7.0) == REPLY
    (request,) = seen
    assert str(request.url) == f"{BASE}/chat/completions"
    body = json.loads(request.content)
    assert body["max_tokens"] == 123
    assert body["model"] == "test-model"
    assert body["messages"] == [{"role": "user", "content": "hello"}]
    assert not {"tools", "tool_choice", "functions", "function_call"} & body.keys()
    assert request.extensions["timeout"]["read"] == 7.0


def test_timeout_is_model_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(ModelUnavailable):
        make_llm(handler).complete("x", max_tokens=1, timeout=1.0)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, text="boom"),
        httpx.Response(302, headers={"location": "http://evil.example/"}),
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json={"choices": [{"message": {"content": 5}}]}),
        httpx.Response(200, json=["x"]),
    ],
)
def test_bad_envelope_is_model_unavailable(response: httpx.Response) -> None:
    with pytest.raises(ModelUnavailable):
        make_llm(lambda request: response).complete("x", max_tokens=1, timeout=1.0)


def test_letter_url_causes_one_request_to_configured_endpoint(env: Env) -> None:
    hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hosts.append(request.url.host)
        return ok(request)

    letter = "Se http://evil.example/steal och 2026-12-04."
    app = create_app(ocr=FakeOcr(letter), llm=make_llm(handler))
    response = post(TestClient(app, raise_server_exceptions=False))
    assert response.status_code == 200
    assert response.json()["summary"] == "Real summary."
    assert hosts == ["model.local"]


def test_model_timeout_gives_generic_502(env: Env) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("t", request=request)

    app = create_app(ocr=FakeOcr(), llm=make_llm(handler))
    response = post(TestClient(app, raise_server_exceptions=False))
    assert response.status_code == 502
    assert response.json() == {"error": ModelUnavailable.message}


def test_provider_is_selected_from_env(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai_compat")
    monkeypatch.setenv("LLM_BASE_URL", BASE)
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setenv("APP_ENV", "prod")
    create_app(ocr=FakeOcr())


@pytest.mark.parametrize("missing", ["LLM_BASE_URL", "LLM_MODEL"])
def test_openai_compat_needs_url_and_model(
    env: Env, monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai_compat")
    monkeypatch.setenv("LLM_BASE_URL", BASE)
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.delenv(missing)
    with pytest.raises(ConfigError):
        create_app(ocr=FakeOcr())
