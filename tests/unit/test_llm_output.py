import inspect
import json

import pytest

from app.errors import BadModelOutput
from app.llm import FakeLLM, LLMClient, parse_model_output


def test_valid_output_parses() -> None:
    out = parse_model_output('{"summary": "s", "actions": ["a"]}')
    assert out.summary == "s"
    assert out.actions == ["a"]


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "",
        '{"summary": "s"}',
        '{"summary": "s", "actions": ["a"], "dates": ["2026-01-01"]}',
        json.dumps({"summary": "x" * 2001, "actions": []}),
        json.dumps({"summary": "s", "actions": ["x" * 301]}),
        json.dumps({"summary": "s", "actions": ["a"] * 11}),
        '{"summary": 5, "actions": []}',
        '["summary"]',
    ],
)
def test_invalid_output_rejected(raw: str) -> None:
    with pytest.raises(BadModelOutput):
        parse_model_output(raw)


def test_model_client_has_no_tool_parameter() -> None:
    for cls in (LLMClient, FakeLLM):
        params = set(inspect.signature(cls.complete).parameters)
        assert params == {"self", "prompt", "max_tokens", "timeout"}
