"""Triam UAT 25-11-2026 rows 190 and 194: calls / visits recorded in a period, and clients with none."""
from datetime import date, timedelta

from app.schemas.activity import ActivityCreate
from app.services import activity_service, standard_reports_service as rpt


def _report(db, acc, rm, days_ago, kind="Call Report", final=True):
    """A report made today, then dated `days_ago` back (older ones stand for history entered before row 188)."""
    act = activity_service.create_activity(db, ActivityCreate(
        account_id=acc.id, activity_date=date.today(), activity_type=kind, summary="Renewal",
        client_contact="Omar", location="JLT", final=final), rm)
    act.activity_date = date.today() - timedelta(days=days_ago)
    db.commit()
    return act


def test_recorded_lists_final_reports_in_the_period(db, make_user, make_account):
    rm = make_user("Rita RM")
    a = make_account(name="Alpha Ltd", spoc=rm, profile_status="Active", client_id="TCPL/00001")
    b = make_account(name="Beta Ltd", spoc=rm, profile_status="Active", client_id="TCPL/00002")
    _report(db, a, rm, 2, "Visit Report")
    _report(db, b, rm, 40)
    _report(db, a, rm, 1, final=False)  # a draft is not "recorded"
    rep = rpt.run(db, rm, "visits-recorded", date_from=date.today() - timedelta(days=7))
    assert rep["columns"] == ["Date of Report", "Call / Visit", "Client ID", "Client Name", "Client Tag", "RM Name"]
    assert [(r[1], r[3], r[5]) for r in rep["rows"]] == [("Visit", "Alpha Ltd", "Rita RM")]
    only_b = rpt.run(db, rm, "visits-recorded", account_id=b.id)
    assert [r[3] for r in only_b["rows"]] == ["Beta Ltd"]


def test_not_done_lists_clients_without_a_call_or_visit(db, make_user, make_account):
    rm = make_user("Rita RM")
    a = make_account(name="Alpha Ltd", spoc=rm, profile_status="Active")
    b = make_account(name="Beta Ltd", spoc=rm, profile_status="Active")
    make_account(name="Never Called Ltd", spoc=rm, profile_status="Active")
    make_account(name="Still Onboarding Ltd", spoc=rm, profile_status="WIP")  # not yet serviced: left out
    _report(db, a, rm, 3)
    _report(db, b, rm, 120)
    rep = rpt.run(db, rm, "visits-not-done")  # the last 90 days
    rows = {r[3]: r for r in rep["rows"]}
    assert set(rows) == {"Beta Ltd", "Never Called Ltd"}
    assert rows["Never Called Ltd"][1] == "None yet" and rows["Beta Ltd"][1] == "Call"
    assert [r[3] for r in rep["rows"]][0] == "Never Called Ltd"  # longest without a call first
