import datetime as dt
import re

from pydantic import BaseModel

from app.redact import redact

MAX_CONTEXT = 120

_MONTHS: dict[str, int] = {
    "januari": 1,
    "jan": 1,
    "februari": 2,
    "feb": 2,
    "mars": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "maj": 5,
    "juni": 6,
    "jun": 6,
    "juli": 7,
    "jul": 7,
    "augusti": 8,
    "aug": 8,
    "september": 9,
    "sept": 9,
    "sep": 9,
    "oktober": 10,
    "okt": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}
_MONTH_ALT = "|".join(sorted(_MONTHS, key=len, reverse=True))

_ISO = re.compile(r"(?<![\d-])(20\d{2})-(\d{2})-(\d{2})(?!\d)")
_NAMED = re.compile(
    rf"(?<!\d)(\d{{1,2}})(?::[ae])?\s+({_MONTH_ALT})(?![^\W\d_])\.?(?:\s+(20\d{{2}})(?!\d))?",
    re.IGNORECASE,
)
_SLASH = re.compile(r"(?<![\d/.])(\d{1,2})/(\d{1,2})(?:/(20\d{2}))?(?![\d/])")


class FoundDate(BaseModel):
    date: dt.date
    context: str


def _resolve(year: int | None, month: int, day: int, today: dt.date) -> dt.date | None:
    if year is not None:
        return _valid(year, month, day)
    for candidate_year in range(today.year, today.year + 9):
        found = _valid(candidate_year, month, day)
        if found is not None and found >= today:
            return found
    return None


def _valid(year: int, month: int, day: int) -> dt.date | None:
    try:
        return dt.date(year, month, day)
    except ValueError:
        return None


def _raw_matches(text: str, today: dt.date) -> list[tuple[dt.date, int, str]]:
    """(date, start offset, original wording) for every valid date mention."""
    out: list[tuple[dt.date, int, str]] = []
    for m in _ISO.finditer(text):
        found = _valid(int(m[1]), int(m[2]), int(m[3]))
        if found:
            out.append((found, m.start(), m[0]))
    for m in _NAMED.finditer(text):
        year = int(m[3]) if m[3] else None
        found = _resolve(year, _MONTHS[m[2].lower()], int(m[1]), today)
        if found:
            out.append((found, m.start(), m[0]))
    for m in _SLASH.finditer(text):
        year = int(m[3]) if m[3] else None
        found = _resolve(year, int(m[2]), int(m[1]), today)
        if found:
            out.append((found, m.start(), m[0]))
    return out


def _context(text: str, start: int, wording: str) -> str:
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    line = text[line_start : len(text) if line_end < 0 else line_end]
    # Redact the whole line first so a cut can never leave half an identifier.
    clean = " ".join(redact(line).split())
    if len(clean) <= MAX_CONTEXT:
        return clean
    at = max(clean.find(wording), 0)
    begin = max(0, min(at - (MAX_CONTEXT - len(wording)) // 2, len(clean) - MAX_CONTEXT))
    return clean[begin : begin + MAX_CONTEXT]


def find_dates(text: str, today: dt.date) -> list[FoundDate]:
    by_date: dict[dt.date, FoundDate] = {}
    for found, start, wording in sorted(_raw_matches(text, today), key=lambda t: t[1]):
        if found not in by_date:
            by_date[found] = FoundDate(date=found, context=_context(text, start, wording))
    return [by_date[d] for d in sorted(by_date)]
