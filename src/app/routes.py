from collections.abc import Callable
from datetime import date
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from starlette.concurrency import run_in_threadpool

from app.config import SUPPORTED_LANGUAGES
from app.decode import DecodeResult, OcrEngine, decode_letter
from app.errors import BadLanguage
from app.llm import LLMClient
from app.upload import read_limited


def build_router(*, ocr: OcrEngine, llm: LLMClient, clock: Callable[[], date]) -> APIRouter:
    router = APIRouter()

    @router.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @router.post("/api/decode")
    async def decode(
        file: Annotated[UploadFile, File()],
        language: Annotated[str, Form()] = "en",
    ) -> DecodeResult:
        if language not in SUPPORTED_LANGUAGES:
            raise BadLanguage()
        data = await read_limited(file)
        return await run_in_threadpool(decode_letter, data, language, ocr=ocr, llm=llm, clock=clock)

    return router
