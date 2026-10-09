"""Triam BRD mark-up §20a — standard reports."""
from datetime import date, timedelta

from app.schemas.prospect import ProspectCreate
from app.services import prospect_service, standard_reports_service as rpt
from app.services import client_workflow_service as wf
from tests import flow
from tests.test_p2_workflow import complete_client, people  # noqa: F401  (fixture)


def test_document_expiry_reports(db, make_user, make_account):
    rm = make_user("Rita RM")
    today = date.today()
    make_account(name="Soon Ltd", spoc=rm, license_expiry_date=today + timedelta(days=10), lei_expiry_date=today + timedelta(days=90))
    make_account(name="Late Ltd", spoc=rm, license_expiry_date=today - timedelta(days=5))
    make_account(name="Hidden Ltd", spoc=make_user("Otto RM"), license_expiry_date=today + timedelta(days=3))
    expiring = rpt.documents_expiring(db, rm)
    assert [(r[0], r[3], r[5]) for r in expiring["rows"]] == [("Soon Ltd", "Trade / Commercial Licence", 10)]  # Hidden Ltd isn't Rita's
    expired = rpt.documents_expired(db, rm)
    assert [(r[0], r[5]) for r in expired["rows"]] == [("Late Ltd", 5)]


def test_prospect_reports(db, make_user, make_role):
    coord = make_user("Pia", business_role=make_role("Prospecting Coordinator", ["prospect.assign"]))
    rm = make_user("Rita RM")
    a = prospect_service.create_prospect(db, ProspectCreate(company_name="Assigned Ltd"), coord)
    prospect_service.assign_prospect(db, a.id, rm.id, None, coord)
    prospect_service.create_prospect(db, ProspectCreate(company_name="Waiting Ltd"), coord)
    assigned = rpt.prospects_assigned(db, coord, date.today(), date.today())
    assert [r[1] for r in assigned["rows"]] == ["Assigned Ltd"] and assigned["rows"][0][2] == "Rita RM"
    assert rpt.prospects_assigned(db, coord, date.today() + timedelta(days=1), None)["rows"] == []
    assert [r[1] for r in rpt.prospects_unassigned(db, coord)["rows"]] == ["Waiting Ltd"]


def test_rejected_cases_pending_with_rm(db, people):
    maker, checker = people["maker"], people["checker"]
    acc = complete_client(db, maker)
    flow.submit(db, acc, maker)
    wf.reject(db, acc, checker, "Documents missing or incomplete", "Passport copy for Jane has expired")
    [row] = rpt.rejected_with_rm(db, maker)["rows"]
    assert row[0] == "Complete Co" and row[3] == "Mia MLRO" and "Passport copy" in row[5] and row[6] == 0
    flow.submit(db, acc, maker)  # resubmitted — no longer pending with the RM
    assert rpt.rejected_with_rm(db, maker)["rows"] == []
