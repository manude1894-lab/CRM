"""Date wording for anything the system writes (PDFs, letters, reminders, messages).

BRD §14: dates display as DD MM YYYY unless a field says otherwise. Legal documents use the long
form (09 October 2026), as on the letterhead. File names keep YYYY-MM-DD so they sort in order.
"""
from __future__ import annotations

from datetime import date, datetime


def _as_date(value) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def dmy(value, empty: str = "—") -> str:
    """09 10 2026"""
    d = _as_date(value)
    return d.strftime("%d %m %Y") if d else (empty if value in (None, "") else str(value))


def long_date(value) -> str:
    """09 October 2026 — for letters and resolutions."""
    d = _as_date(value)
    return d.strftime("%d %B %Y") if d else str(value or "")
