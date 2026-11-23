import json
import logging
import re
from pathlib import Path
from typing import Annotated, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from app.config import Settings
from app.envelope import extract_content, finish_reason
from app.errors import BadModelOutput, ModelOutOfTokens, ModelUnavailable
from app.tls import model_ssl_context

log = logging.getLogger("app.llm")

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
            envelope = response.json()
            content = extract_content(envelope)
        except (httpx.HTTPError, ValueError):
            raise ModelUnavailable() from None
        if finish_reason(envelope) == "length":
            # Cut off at the cap: the JSON is incomplete or, for a thinking model, empty.
            # Say so, never the text.
            log.warning(
                "model_out_of_tokens max_tokens=%d content_chars=%d", max_tokens, len(content)
            )
            raise ModelOutOfTokens()
        return content


class ModelOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: Annotated[str, StringConstraints(max_length=2000)]
    actions: Annotated[
        list[Annotated[str, StringConstraints(max_length=300)]], Field(max_length=10)
    ]


_FENCE_RE = re.compile(
    r"^[ \t]*````?[A-Za-z]*[ \t]*\r?\n(.*?)\s*````?[ \t]*$", re.DOTALL | re.MULTILINE
)


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _strip_markdown_fence(raw: str) -> str:
    """Strip an optional markdown code fence from *raw* and return the inner content.

    If *raw* is not wrapped in a fence the string is returned unchanged
    (backward compatible).
    """
    text = _THINK_RE.sub("", raw).strip().lstrip("﻿")
    m = _FENCE_RE.search(text)
    if m:
        return m.group(1)
    return _bare_object(text)


def _bare_object(text: str) -> str:
    """Return the first JSON object in unfenced *text* (prose around it is dropped).

    Text containing backticks is left alone: a malformed fence is rejected, not guessed at.
    """
    start = text.find("{")
    if start <= 0 or "`" in text:
        return text
    try:
        _, end = json.JSONDecoder().raw_decode(text, start)
    except ValueError:
        return text
    return text[start:end]


def parse_model_output(raw: str) -> ModelOutput:
    try:
        return ModelOutput.model_validate_json(_strip_markdown_fence(raw))
    except ValidationError as exc:
        raise BadModelOutput(exc) from None
