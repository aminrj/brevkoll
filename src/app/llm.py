import json
from pathlib import Path
from typing import Annotated, Protocol

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from app.errors import BadModelOutput

DEFAULT_FAKE_RESPONSE = '{"summary": "Fake summary.", "actions": ["Fake action."]}'


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
