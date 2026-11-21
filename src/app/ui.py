from datetime import date
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict

from app.config import SUPPORTED_LANGUAGES
from app.decode import DateItem, DecodeResult

APP_DIR = Path(__file__).parent
STATIC_DIR = APP_DIR / "static"
UI_DECODE_PATH = "/ui/decode"

LANGUAGE_NAMES = {"en": "English", "sv": "Svenska", "ar": "العربية", "uk": "Українська"}

_Week = tuple[str, str, str, str, str, str, str]

# Monday..Sunday, in the answer language. Computed in code, never by the model.
WEEKDAYS: dict[str, _Week] = {
    "en": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
    "sv": ("måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag", "söndag"),
    "ar": ("الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"),
    "uk": ("понеділок", "вівторок", "середа", "четвер", "пʼятниця", "субота", "неділя"),
}


class DateView(BaseModel):
    model_config = ConfigDict(frozen=True)

    iso: str
    weekday: str
    description: str


def weekday_name(iso: str, language: str) -> str:
    names = WEEKDAYS.get(language, WEEKDAYS["en"])
    return names[date.fromisoformat(iso).weekday()]


def date_views(dates: list[DateItem], language: str) -> list[DateView]:
    return [
        DateView(iso=d.date, weekday=weekday_name(d.date, language), description=d.description)
        for d in dates
    ]


# Jinja2Templates autoescapes .html templates; no template uses |safe.
_templates = Jinja2Templates(directory=str(APP_DIR / "templates"))


def _render(request: Request, name: str, status: int, context: dict[str, Any]) -> HTMLResponse:
    return _templates.TemplateResponse(request, name, context, status_code=status)


def render_index(request: Request) -> HTMLResponse:
    languages = [(code, LANGUAGE_NAMES.get(code, code)) for code in sorted(SUPPORTED_LANGUAGES)]
    return _render(request, "index.html", 200, {"languages": languages})


def render_result(request: Request, result: DecodeResult, language: str) -> HTMLResponse:
    context = {
        "result": result,
        "dates": date_views(result.dates, language),
        "lang": language,
        "dir": "rtl" if language == "ar" else "ltr",
    }
    return _render(request, "result.html", 200, context)


def render_error(request: Request, status: int, message: str) -> HTMLResponse:
    return _render(request, "error.html", status, {"message": message})
