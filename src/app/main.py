import os
import time
from collections.abc import Awaitable, Callable
from datetime import date, datetime

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

from app.config import ConfigError, Settings, load_settings
from app.decode import OcrEngine
from app.errors import AppError, InvalidRequest, RateLimited, TooLarge
from app.limits import BudgetedLLM, DailyBudget, SlidingWindowLimiter, client_ip
from app.llm import FakeLLM, LLMClient, OpenAICompatLLM
from app.ocr import TesseractOcr
from app.routes import build_router
from app.upload import MAX_BYTES

_BODY_SLACK = 64 * 1024  # multipart overhead on top of the file limit


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


def _build_llm(settings: Settings) -> LLMClient:
    if settings.llm_provider == "fake":
        if settings.app_env == "prod":
            raise ConfigError("LLM_PROVIDER=fake is not allowed when APP_ENV=prod")
        return FakeLLM(settings.fake_llm_log, settings.fake_llm_response)
    if settings.llm_provider == "openai_compat":
        if not settings.llm_base_url or not settings.llm_model:
            raise ConfigError("LLM_BASE_URL and LLM_MODEL are required for openai_compat")
        http = httpx.Client(follow_redirects=False, trust_env=False)
        return OpenAICompatLLM(settings.llm_base_url, settings.llm_model, http)
    raise ConfigError("Unknown LLM_PROVIDER")


def create_app(
    *,
    ocr: OcrEngine | None = None,
    llm: LLMClient | None = None,
    clock: Callable[[], date] | None = None,
) -> FastAPI:
    settings = load_settings(os.environ)
    budget = DailyBudget(settings.daily_model_call_budget, datetime.now)
    llm_client = BudgetedLLM(llm if llm is not None else _build_llm(settings), budget)
    limiter = SlidingWindowLimiter(settings.rate_limit_per_minute, time.monotonic)
    app = FastAPI(title="app", docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(
        build_router(
            ocr=ocr if ocr is not None else TesseractOcr(concurrency=settings.ocr_concurrency),
            llm=llm_client,
            clock=clock if clock is not None else date.today,
        )
    )

    @app.middleware("http")
    async def limit_body(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method == "POST" and request.url.path == "/api/decode":
            peer = request.client.host if request.client else None
            forwarded = request.headers.get("x-forwarded-for")
            try:
                limiter.check(client_ip(peer, forwarded, settings.trusted_proxies))
            except RateLimited as exc:
                return _error(exc.status_code, exc.message)
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > MAX_BYTES + _BODY_SLACK:
            return _error(TooLarge.status_code, TooLarge.message)
        return await call_next(request)

    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError) -> JSONResponse:
        return _error(exc.status_code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _error(InvalidRequest.status_code, InvalidRequest.message)

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception) -> JSONResponse:
        return _error(500, "Internal error")

    return app


app = create_app()
