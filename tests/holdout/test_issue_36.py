"""Holdout tests for issue #36: strip markdown code fences from model responses."""

import pytest

from app.errors import BadModelOutput
from app.llm import parse_model_output


# AC1: markdown fences with "json" language tag are stripped and parsed
def test_ac1_markdown_json_fences_are_stripped() -> None:
    raw = '```json\n{"summary": "Hej!", "actions": ["Gå på möte"]}\n```'
    out = parse_model_output(raw)
    assert out.summary == "Hej!"
    assert out.actions == ["Gå på möte"]


# AC2: markdown fences without a language tag are stripped and parsed
def test_ac2_markdown_fences_without_language_tag() -> None:
    raw = '```\n{"summary": "Mötet", "actions": ["Svara senast"]}  \n```'
    out = parse_model_output(raw)
    assert out.summary == "Mötet"
    assert out.actions == ["Svara senast"]


# AC3: plain JSON without fences still works (backward compatibility)
def test_ac3_plain_json_still_works() -> None:
    raw = '{"summary": "Plain", "actions": []}'
    out = parse_model_output(raw)
    assert out.summary == "Plain"
    assert out.actions == []


# AC4: invalid JSON inside fences still raises BadModelOutput
def test_ac4_invalid_json_inside_fences_raises() -> None:
    raw = "```json\n{not valid json}\n```"
    with pytest.raises(BadModelOutput):
        parse_model_output(raw)
