from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import SUPPORTED_LANGUAGES

APP_DIR = Path(__file__).parent
STATIC_DIR = APP_DIR / "static"
UI_DECODE_PATH = "/ui/decode"

LANGUAGE_NAMES = {"en": "English", "sv": "Svenska", "ar": "العربية", "uk": "Українська"}

# Jinja2Templates autoescapes .html templates; no template uses |safe.
_templates = Jinja2Templates(directory=str(APP_DIR / "templates"))


def _render(request: Request, name: str, status: int, context: dict[str, Any]) -> HTMLResponse:
    return _templates.TemplateResponse(request, name, context, status_code=status)


def render_index(request: Request) -> HTMLResponse:
    languages = [(code, LANGUAGE_NAMES.get(code, code)) for code in sorted(SUPPORTED_LANGUAGES)]
    return _render(request, "index.html", 200, {"languages": languages})


def render_result(request: Request, result: Any) -> HTMLResponse:
    return _render(request, "result.html", 200, {"result": result})


def render_error(request: Request, status: int, message: str) -> HTMLResponse:
    return _render(request, "error.html", status, {"message": message})
