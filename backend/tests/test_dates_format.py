"""Date wording in what the system writes (DD MM YYYY, BRD §12)."""
from datetime import date, datetime

from app.utils.dates import dmy, long_date


def test_dmy_and_long_date():
    assert dmy(date(2026, 10, 9)) == "09 10 2026"
    assert dmy("2026-10-09") == "09 10 2026"
    assert dmy(datetime(2026, 10, 9, 14, 30)) == "09 10 2026"
    assert dmy(None) == "—"
    assert long_date("2026-10-09") == "09 October 2026"
