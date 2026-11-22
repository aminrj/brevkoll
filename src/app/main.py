import os
import time
from collections.abc import Awaitable, Callable
from datetime import date, datetime

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import FormData
from starlette.requests import Request as StarletteRequest

from app.config import ConfigError, Settings, load_settings
from app.decode import OcrEngine
from app.errors import AppError, InvalidRequest, RateLimited, TooLarge
from app.limits import BudgetedLLM, DailyBudget, SlidingWindowLimiter, client_ip
from app.llm import FakeLLM, LLMClient, OpenAICompatLLM, model_http_client
from app.ocr import TesseractOcr
from app.routes import build_router
from app.ui import STATIC_DIR, UI_DECODE_PATH, render_error
from app.upload import MAX_BYTES, MAX_PART_BYTES

# Re-export Request for type hints; the actual class is patched at module load.
Request = StarletteRequest


def _patch_request() -> None:
    """Patch StarletteRequest to allow files up to MAX_PART_BYTES."""
    original_get_form = StarletteRequest._get_form

    async def _get_form(
        self,
        *,
        max_files: int | float = 1000,
        max_fields: int | float = 1000,
        max_part_size: int = MAX_PART_BYTES,
    ) -> FormData:
        return await original_get_form(
            self,
            max_files=max_files,
            max_fields=max_fields,
            max_part_size=max_part_size,
        )

    StarletteRequest._get_form = _get_form


_patch_request()


_BODY_SLACK = 64 * 1024  # multipart overhead on top of the file limit
_DECODE_PATHS = ("/api/decode", UI_DECODE_PATH)
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)


def _error(request: Request, status: int, message: str) -> Response:
    if request.url.path == UI_DECODE_PATH:
        return render_error(request, status, message)
    return JSONResponse({"error": message}, status_code=status)


def _build_llm(settings: Settings) -> LLMClient:
    if settings.llm_provider == "fake":
        if settings.app_env == "prod":
            raise ConfigError("LLM_PROVIDER=fake is not allowed when APP_ENV=prod")
        return FakeLLM(settings.fake_llm_log, settings.fake_llm_response)
    if settings.llm_provider == "openai_compat":
        if not settings.llm_base_url or not settings.llm_model:
            raise ConfigError("LLM_BASE_URL and LLM_MODEL are required for openai_compat")
        http = model_http_client(settings)
        key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else None
        return OpenAICompatLLM(settings.llm_base_url, settings.llm_model, http, key)
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
            max_tokens=settings.model_max_tokens,
            timeout=settings.model_timeout_s,
        )
    )

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.middleware("http")
    async def limit_body(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method == "POST" and request.url.path in _DECODE_PATHS:
            peer = request.client.host if request.client else None
            forwarded = request.headers.get("x-forwarded-for")
            try:
                limiter.check(client_ip(peer, forwarded, settings.trusted_proxies))
            except RateLimited as exc:
                return _error(request, exc.status_code, exc.message)
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > MAX_BYTES + _BODY_SLACK:
            return _error(request, TooLarge.status_code, TooLarge.message)
        return await call_next(request)

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = CSP
        return response

    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError) -> Response:
        return _error(request, exc.status_code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError) -> Response:
        return _error(request, InvalidRequest.status_code, InvalidRequest.message)

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception) -> Response:
        return _error(request, 500, "Internal error")

    return app


app = create_app()
