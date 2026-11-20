"""BRD §20a — standard reports."""
from datetime import timedelta

from app.schemas.prospect import ProspectCreate
from app.services import prospect_service, standard_reports_service as rpt
from app.services import client_workflow_service as wf
from tests import flow
from tests.helpers import rows_of
from tests.flow import complete_client


def test_document_expiry_reports(db, make_user, make_account):
    rm = make_user("Rita RM")
    today = rpt._today()
    make_account(name="Soon Ltd", spoc=rm, license_expiry_date=today + timedelta(days=10), lei_expiry_date=today + timedelta(days=90))
    make_account(name="Late Ltd", spoc=rm, license_expiry_date=today - timedelta(days=5))
    make_account(name="Hidden Ltd", spoc=make_user("Otto RM"), license_expiry_date=today + timedelta(days=3))
    expiring = rpt.documents_expiring(db, rm)
    assert [(r["Client Name"], r["Doc Type"], r["Days left"]) for r in rows_of(expiring)] == [("Soon Ltd", "Trade / Commercial Licence", 10)]  # Hidden Ltd isn't Rita's
    assert rows_of(expiring)[0]["Anchor RM"] == "Rita RM"
    expired = rpt.documents_expired(db, rm)
    assert [(r["Client Name"], r["Days overdue"]) for r in rows_of(expired)] == [("Late Ltd", 5)]


def test_prospect_reports(db, make_user, make_role):
    coord = make_user("Pia", business_role=make_role("Prospecting Coordinator", ["prospect.assign"]))
    rm = make_user("Rita RM")
    a = prospect_service.create_prospect(db, ProspectCreate(company_name="Assigned Ltd"), coord)
    prospect_service.assign_prospect(db, a.id, rm.id, None, coord)
    prospect_service.create_prospect(db, ProspectCreate(company_name="Waiting Ltd"), coord)
    assigned = rpt.prospects_assigned(db, coord, rpt._today(), rpt._today())
    assert [r[1] for r in assigned["rows"]] == ["Assigned Ltd"] and assigned["rows"][0][2] == "Rita RM"
    assert rpt.prospects_assigned(db, coord, rpt._today() + timedelta(days=1), None)["rows"] == []
    assert [r["Prospect Name"] for r in rows_of(rpt.prospects_unassigned(db, coord))] == ["Waiting Ltd"]


def test_rejected_cases_pending_with_rm(db, people):
    maker, checker = people["maker"], people["checker"]
    acc = complete_client(db, maker)
    flow.submit(db, acc, maker)
    wf.reject(db, acc, checker, "Documents missing or incomplete", "Passport copy for Jane has expired")
    [row] = rows_of(rpt.rejected_with_rm(db, maker))
    assert (row["Anchor Triam Entity"], row["Client Name"], row["Rejected by"], row["Ageing (days)"]) == ("TCPL", "Complete Co", "Mia MLRO", 0)
    assert "Passport copy" in row["Reason for Rejection"]
    flow.submit(db, acc, maker)  # resubmitted — no longer pending with the RM
    assert rpt.rejected_with_rm(db, maker)["rows"] == []


def test_under_formation_report_lists_clients_and_what_is_missing(db, make_user, make_account):
    """Triam UAT 10-11-2026 (row 24) and 18-11-2026 (rows 93, 147): approved Under Formation clients, ageing from
    the approval, oldest first, with the details still to come; the user picks the period."""
    from datetime import datetime, timezone
    rm = make_user("Rita RM")
    now = datetime.now(timezone.utc)
    make_account(name="Old Forming Ltd", spoc=rm, client_category="Under Formation", registration_number="CI-1",
                 incorporation_date=rpt._today(), registered_address={"line1": "Unit 1", "city": "Dubai"},
                 profile_status="Approved", approved_at=now - timedelta(days=40), anchor_entity="TCPL")
    make_account(name="New Forming Ltd", spoc=rm, client_category="Under Formation", profile_status="Active",
                 approved_at=now - timedelta(days=5))
    make_account(name="Not Approved Yet", spoc=rm, client_category="Under Formation", profile_status="WIP")
    make_account(name="Existing Ltd", spoc=rm, client_category="Existing", profile_status="Approved", approved_at=now)
    make_account(name="Other RM Forming", spoc=make_user("Otto RM"), client_category="Under Formation",
                 profile_status="Approved", approved_at=now - timedelta(days=60))
    report = rpt.run(db, rm, "under-formation")  # 30 days by default
    assert [r["Client Name"] for r in rows_of(report)] == ["Old Forming Ltd"]
    first = rows_of(report)[0]
    assert (first["Anchor Triam Entity"], first["Anchor RM"], first["Ageing from approval (days)"]) == ("TCPL", "Rita RM", 40)
    missing = first["Missing Details"]
    assert "Incorporation Certificate No." not in missing and "Registered Address" not in missing
    assert "Licence No." in missing and "Operating Address" in missing
    assert [r["Client Name"] for r in rows_of(rpt.run(db, rm, "under-formation", days=0))] == ["Old Forming Ltd", "New Forming Ltd"]
    assert "under-formation" in rpt.REPORTS
