import logging
from collections.abc import Callable
from datetime import date
from typing import Protocol

from pydantic import BaseModel

from app.errors import OcrFailed
from app.llm import LLMClient, parse_model_output
from app.prompt import build_prompt
from app.redact import redact
from app.upload import sniff_kind

log = logging.getLogger("app.decode")

MAX_TOKENS = 600
MODEL_TIMEOUT_S = 30.0
EMPTY_ICS = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//brevkoll//EN\r\nEND:VCALENDAR\r\n"


class DateItem(BaseModel):
    date: str
    description: str


class DecodeResult(BaseModel):
    summary: str
    actions: list[str]
    dates: list[DateItem]
    ics: str


class OcrEngine(Protocol):
    def extract(self, data: bytes, kind: str) -> str: ...


class UnwiredOcr:
    """Default until real OCR is wired in (phase 2)."""

    def extract(self, data: bytes, kind: str) -> str:
        raise OcrFailed()


def decode_letter(
    data: bytes,
    language: str,
    *,
    ocr: OcrEngine,
    llm: LLMClient,
    clock: Callable[[], date],
) -> DecodeResult:
    kind = sniff_kind(data)
    text = ocr.extract(data, kind)
    prompt = build_prompt(redact(text), language)  # also validates the language
    raw = llm.complete(prompt, max_tokens=MAX_TOKENS, timeout=MODEL_TIMEOUT_S)
    output = parse_model_output(raw)
    log.info("decoded kind=%s ocr_chars=%d actions=%d", kind, len(text), len(output.actions))
    return DecodeResult(summary=output.summary, actions=output.actions, dates=[], ics=EMPTY_ICS)
