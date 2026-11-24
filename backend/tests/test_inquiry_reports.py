"""Triam 24-11-2026: Inquiry & Reports (read only) sees every report, as BRD §13 says; an RM still does not see the
desk-only ones."""
from app.services import standard_reports_service as rpt


def test_inquiry_sees_every_report_and_can_run_them(db, make_user, make_role):
    inquiry = make_user("Ian Inquiry", business_role=make_role("Inquiry", ["read_only", "view.all_clients"]))
    assert set(rpt.available(inquiry)) == set(rpt.REPORTS)
    for key in rpt.RESTRICTED:
        rpt.run(db, inquiry, key)  # no "isn't available to your role"


def test_an_rm_still_does_not_see_desk_reports(make_user):
    rm = make_user("Rita RM")
    assert not set(rpt.RESTRICTED) & set(rpt.available(rm))
