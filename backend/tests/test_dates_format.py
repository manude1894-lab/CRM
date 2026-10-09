"""BRD §14 date wording in what the system writes (PDFs, letters, reminders)."""
from datetime import date, datetime

from app.utils.dates import dmy, long_date


def test_dmy_and_long_date():
    assert dmy(date(2026, 10, 9)) == "09 10 2026"
    assert dmy("2026-10-09") == "09 10 2026"
    assert dmy(datetime(2026, 10, 9, 14, 30)) == "09 10 2026"
    assert dmy(None) == "—"
    assert long_date("2026-10-09") == "09 October 2026"


def test_resolution_wording_uses_long_dates():
    from app.services import generation_service
    import inspect
    src = inspect.getsource(generation_service)
    assert 'eff = long_date(p.get("effective_date") or date.today())' in src
