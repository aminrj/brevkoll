import logging
from collections.abc import Callable
from datetime import date, datetime, time
from typing import Protocol

from pydantic import BaseModel

from app.dates import find_dates
from app.ics import build_ics
from app.llm import LLMClient, parse_model_output
from app.prompt import build_prompt
from app.redact import redact
from app.upload import sniff_kind

log = logging.getLogger("app.decode")

MAX_TOKENS = 600
MODEL_TIMEOUT_S = 30.0


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


def decode_letter(
    data: bytes,
    language: str,
    *,
    ocr: OcrEngine,
    llm: LLMClient,
    clock: Callable[[], date],
    max_tokens: int = MAX_TOKENS,
    timeout: float = MODEL_TIMEOUT_S,
) -> DecodeResult:
    kind = sniff_kind(data)
    text = ocr.extract(data, kind)
    prompt = build_prompt(redact(text), language)  # also validates the language
    raw = llm.complete(prompt, max_tokens=max_tokens, timeout=timeout)
    output = parse_model_output(raw)
    log.info("decoded kind=%s ocr_chars=%d actions=%d", kind, len(text), len(output.actions))
    today = clock()
    found = find_dates(text, today)  # dates come from code, never from the model
    ics = build_ics(found, output.summary, output.actions, datetime.combine(today, time.min))
    dates = [DateItem(date=f.date.isoformat(), description=f.context) for f in found]
    return DecodeResult(summary=output.summary, actions=output.actions, dates=dates, ics=ics)
