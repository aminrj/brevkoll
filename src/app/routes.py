from collections.abc import Callable
from datetime import date
from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from starlette.concurrency import run_in_threadpool

from app.config import SUPPORTED_LANGUAGES
from app.decode import MAX_TOKENS, MODEL_TIMEOUT_S, DecodeResult, OcrEngine, decode_letter
from app.errors import BadLanguage
from app.llm import LLMClient
from app.ui import render_index, render_result
from app.upload import read_limited


def build_router(
    *,
    ocr: OcrEngine,
    llm: LLMClient,
    clock: Callable[[], date],
    max_tokens: int = MAX_TOKENS,
    timeout: float = MODEL_TIMEOUT_S,
) -> APIRouter:
    router = APIRouter()

    async def run(file: UploadFile, language: str) -> DecodeResult:
        if language not in SUPPORTED_LANGUAGES:
            raise BadLanguage()
        data = await read_limited(file)
        return await run_in_threadpool(
            decode_letter,
            data,
            language,
            ocr=ocr,
            llm=llm,
            clock=clock,
            max_tokens=max_tokens,
            timeout=timeout,
        )

    @router.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return render_index(request)

    @router.post("/api/decode")
    async def decode(
        file: Annotated[UploadFile, File()],
        language: Annotated[str, Form()] = "en",
    ) -> DecodeResult:
        return await run(file, language)

    @router.post("/ui/decode", response_class=HTMLResponse)
    async def decode_ui(
        request: Request,
        file: Annotated[UploadFile, File()],
        language: Annotated[str, Form()] = "en",
    ) -> HTMLResponse:
        return render_result(request, await run(file, language), language)

    return router
