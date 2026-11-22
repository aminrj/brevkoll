import json
from pathlib import Path
from typing import Annotated, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from app.config import Settings
from app.errors import BadModelOutput, ModelUnavailable
from app.tls import model_ssl_context

DEFAULT_FAKE_RESPONSE = '{"summary": "Fake summary.", "actions": ["Fake action."]}'


def model_http_client(settings: Settings) -> httpx.Client:
    """The HTTP client for the model: no redirects, no proxy env, mTLS context when configured."""
    ctx = model_ssl_context(settings)
    return httpx.Client(follow_redirects=False, trust_env=False, verify=ctx or True)


class LLMClient(Protocol):
    def complete(self, prompt: str, *, max_tokens: int, timeout: float) -> str: ...


class FakeLLM:
    def __init__(self, log: Path | None, response: str | None) -> None:
        self._log = log
        self._response = DEFAULT_FAKE_RESPONSE if response is None else response

    def complete(self, prompt: str, *, max_tokens: int, timeout: float) -> str:
        if self._log is not None:
            with self._log.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"payload": prompt}) + "\n")
        return self._response


class OpenAICompatLLM:
    """Chat-completions client for a local server. No tools, no redirects."""

    def __init__(
        self, base_url: str, model: str, http: httpx.Client, api_key: str | None = None
    ) -> None:
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._model = model
        self._http = http
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def complete(self, prompt: str, *, max_tokens: int, timeout: float) -> str:
        body = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "stream": False,
        }
        try:
            response = self._http.post(self._url, json=body, headers=self._headers, timeout=timeout)
            response.raise_for_status()
            return _extract_content(response.json())
        except (httpx.HTTPError, ValueError):
            raise ModelUnavailable() from None


def _extract_content(envelope: object) -> str:
    if isinstance(envelope, dict):
        choices = envelope.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            message = choices[0].get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
    raise ValueError("malformed envelope")


class ModelOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: Annotated[str, StringConstraints(max_length=2000)]
    actions: Annotated[
        list[Annotated[str, StringConstraints(max_length=300)]], Field(max_length=10)
    ]


def parse_model_output(raw: str) -> ModelOutput:
    try:
        return ModelOutput.model_validate_json(raw)
    except ValidationError:
        raise BadModelOutput() from None
