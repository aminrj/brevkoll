import hashlib
from collections.abc import Sequence
from datetime import datetime

from app.dates import FoundDate

_FOLD_OCTETS = 75


def escape_text(value: str) -> str:
    """RFC 5545 TEXT escaping. CR and other control characters are dropped."""
    out: list[str] = []
    for ch in value:
        if ch == "\\":
            out.append("\\\\")
        elif ch == ";":
            out.append("\\;")
        elif ch == ",":
            out.append("\\,")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t" or ch >= " " and ch != "\x7f":
            out.append(ch)
    return "".join(out)


def _fold(line: str) -> str:
    parts: list[str] = []
    current = ""
    limit = _FOLD_OCTETS
    for ch in line:
        if len((current + ch).encode()) > limit:
            parts.append(current)
            current, limit = ch, _FOLD_OCTETS - 1  # continuation lines start with a space
        else:
            current += ch
    parts.append(current)
    return "\r\n ".join(parts)


def _event(item: FoundDate, description: str, stamp: str) -> list[str]:
    day = item.date.strftime("%Y%m%d")
    digest = hashlib.sha256(f"{day}|{item.context}".encode()).hexdigest()[:24]
    return [
        "BEGIN:VEVENT",
        f"UID:{digest}@brevkoll",
        f"DTSTAMP:{stamp}",
        f"DTSTART;VALUE=DATE:{day}",
        f"SUMMARY:{escape_text(item.context)}",
        f"DESCRIPTION:{escape_text(description)}",
        "END:VEVENT",
    ]


def build_ics(
    dates: Sequence[FoundDate], summary: str, actions: Sequence[str], now: datetime
) -> str:
    description = "\n".join([summary, *actions])
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//brevkoll//EN"]
    for item in dates:
        lines += _event(item, description, stamp)
    lines.append("END:VCALENDAR")
    return "".join(_fold(line) + "\r\n" for line in lines)
