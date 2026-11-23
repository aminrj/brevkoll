import inspect
import json

import pytest

from app.errors import BadModelOutput
from app.llm import FakeLLM, LLMClient, parse_model_output


def test_valid_output_parses() -> None:
    out = parse_model_output('{"summary": "s", "actions": ["a"]}')
    assert out.summary == "s"
    assert out.actions == ["a"]


# I4
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


def test_invalid_output_error_contains_details() -> None:
    """The error message must include the validation reason so the user
    (or operator) can understand *why* the model output was unusable."""
    try:
        parse_model_output("not json")
    except BadModelOutput as exc:
        assert exc.message.startswith("The model returned an unusable answer.")
        # Detail must be present and must NOT contain the raw input text.
        assert exc.message != "The model returned an unusable answer."
        assert "not json" not in exc.message
        return
    pytest.fail("Expected BadModelOutput")


def test_model_client_has_no_tool_parameter() -> None:
    for cls in (LLMClient, FakeLLM):
        params = set(inspect.signature(cls.complete).parameters)
        assert params == {"self", "prompt", "max_tokens", "timeout"}


# ── Fence-stripping tests ──────────────────────────────────────────────

_FENCE_JSON = '```\n{"summary": "Hej världen.", "actions": ["Läsa brevet"]} ```\n````'


def test_fenced_with_json_tag_parses() -> None:
    """AC1: response wrapped in ```json … ``` parses successfully."""
    raw = '```json\n{"summary": "Hej världen.", "actions": ["Läsa brevet"]}\n```\n'
    out = parse_model_output(raw)
    assert out.summary == "Hej världen."
    assert out.actions == ["Läsa brevet"]


def test_fenced_without_language_tag_parses() -> None:
    """AC2: response wrapped in ``` … ``` (no language tag) parses successfully."""
    raw = '```\n{"summary": "Hej världen.", "actions": ["Läsa brevet"]}\n```\n'
    out = parse_model_output(raw)
    assert out.summary == "Hej världen."
    assert out.actions == ["Läsa brevet"]


def test_plain_json_still_works() -> None:
    """AC3: plain JSON with no fences must still pass (regression guard)."""
    out = parse_model_output('{"summary": "s", "actions": ["a"]}')
    assert out.summary == "s"
    assert out.actions == ["a"]


def test_fenced_with_invalid_inner_json_raises() -> None:
    """AC4: fenced but invalid JSON inside must still raise BadModelOutput."""
    raw = "```\n{invalid json}\n```\n"
    with pytest.raises(BadModelOutput):
        parse_model_output(raw)


def test_fenced_with_four_backticks_closing_parses() -> None:
    """Some models use four backticks at the closing fence. The regex must
    handle both 3 and 4 backticks at the closing marker."""
    raw = '````json\n{"summary": "Hej", "actions": ["Läsa"]}\n````\n'
    out = parse_model_output(raw)
    assert out.summary == "Hej"
    assert out.actions == ["Läsa"]


def test_fenced_backticks_inside_json_preserved() -> None:
    """Threat model LLM05: backticks embedded in JSON content are preserved.

    The regex only strips fences at string boundaries (anchored with $).
    Backticks inside the JSON payload do not match the closing fence
    pattern, so the full JSON is captured and parses correctly.
    """
    raw = '```\n{"summary": "use `code`", "actions": ["a"]}\n```\n'
    out = parse_model_output(raw)
    assert out.summary == "use `code`"
    assert out.actions == ["a"]


def test_fence_after_preamble_and_uppercase_tag_parses() -> None:
    """Models often add a sentence before the fence and write ```JSON."""
    raw = 'Here is the result:\n\n```JSON\n{"summary": "Hej", "actions": ["Läsa"]}\n```'
    assert parse_model_output(raw).summary == "Hej"


def test_leading_whitespace_before_fence_parses() -> None:
    raw = '\n  ```json\r\n{"summary": "Hej", "actions": []}\r\n```  \n'
    assert parse_model_output(raw).actions == []


def test_reasoning_block_before_json_is_ignored() -> None:
    raw = '<think>The letter says {pay} soon.</think>\n{"summary": "Hej", "actions": ["a"]}'
    assert parse_model_output(raw).summary == "Hej"


def test_prose_around_bare_json_is_ignored() -> None:
    raw = 'Sure! Here is the JSON:\n{"summary": "Hej", "actions": []}\nHope that helps.'
    assert parse_model_output(raw).summary == "Hej"


def test_bare_json_with_extra_field_still_rejected() -> None:
    raw = 'Result: {"summary": "Hej", "actions": [], "tool": "rm"}'
    with pytest.raises(BadModelOutput):
        parse_model_output(raw)


def test_no_closing_fence_rejected() -> None:
    """Threat model: truncated output with opening fence but no closing fence."""
    raw = '```\n{"summary": "truncated'
    with pytest.raises(BadModelOutput):
        parse_model_output(raw)


def test_catastrophic_backtracking_does_not_hang() -> None:
    """Threat model LLM10: 10 000 backticks followed by valid JSON must not hang."""
    import time

    long_backticks = "`" * 10_000
    raw = long_backticks + '\n{"summary": "s", "actions": ["a"]}\n```\n'
    start = time.monotonic()
    with pytest.raises(BadModelOutput):
        parse_model_output(raw)
    elapsed = time.monotonic() - start
    msg = f"Fence stripping took {elapsed:.1f}s — possible catastrophic backtracking"
    assert elapsed < 1.0, msg
