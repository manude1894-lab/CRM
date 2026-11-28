"""The time zone of the person making the request (Triam UAT 26-11-2026).

A Biz Rationale meeting can't be later than "now" by the time of whoever is entering it, in the UAE or in India. The
browser sends its IANA time zone in the X-Timezone header; a missing or unknown zone falls back to UAE time.
"""
from contextvars import ContextVar
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

client_timezone: ContextVar[Optional[str]] = ContextVar("client_timezone", default=None)
FALLBACK_TZ = ZoneInfo("Asia/Dubai")


def user_tz() -> ZoneInfo:
    name = client_timezone.get()
    if name and len(name) <= 64:
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return FALLBACK_TZ


def user_now() -> datetime:
    """Now, by the clock of the person making the request."""
    return datetime.now(user_tz())
