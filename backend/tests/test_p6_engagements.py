"""P6 — engagement routes (Existing Entity, Transfer In) and bulk import of existing work."""
from datetime import date

import pytest
from fastapi import HTTPException

from app.models import AuditLog, Case, CaseDocument, CaseStage, CDDRecord, ComplianceSchedule, Instruction, UserRole
from app.schemas.case import CaseCreate
from app.services import case_approval_service as case_ok, case_service, engagement_service


@pytest.fixture()
def people(make_user, make_role, seed_master):
    seed_master("rejection_reason", ["Documents missing or incomplete"])
    return {"rm": make_user("Rita RM"), "mlro": make_user("Mia MLRO", business_role=make_role("MLRO", ["client.approve"])),
            "admin": make_user("Ada Admin", role=UserRole.ADMIN)}


def schedule(db, case):
    return db.query(ComplianceSchedule).filter(ComplianceSchedule.case_id == case.id).first()


# ─── Existing Entity ────────────────────────────────────────────────────────

def test_existing_entity_is_active_and_calendar_built_on_approval(db, people):
    rm, mlro = people["rm"], people["mlro"]
    case = case_service.create_case(db, CaseCreate(
        company_name="Old Harbour Ltd", engagement_route="Existing Entity", jurisdiction="BVI",
        incorporation_date=date(2018, 4, 10), company_number="1987654", registered_agent="Vistra",
        last_renewal_date=date(2025, 4, 10), last_ar_date=date(2024, 9, 30)), rm)
    assert case.stage == CaseStage.ACTIVE and case.engagement_route == "Existing Entity"
    assert case.compliance_status == "Pending Approval" and schedule(db, case) is None
    assert case.company_profile.company_number == "1987654"

    case_ok.approve(db, case, mlro)
    s = schedule(db, case)
    assert s.renewal_last_completed_date == date(2025, 4, 10)
    assert s.renewal_due_date == date(2026, 4, 10)  # next anniversary after the last renewal — overdue today
    assert s.ar_filing_last_completed_date == date(2024, 9, 30)
    assert s.ar_filing_due_date == date(2025, 9, 30)  # Annual Return missed last year: overdue


def test_route_requirements(db, people):
    rm = people["rm"]
    with pytest.raises(HTTPException) as e:
        case_service.create_case(db, CaseCreate(company_name="X", engagement_route="Existing Entity"), rm)
    assert "Jurisdiction" in e.value.detail and "Incorporation date" in e.value.detail
    with pytest.raises(HTTPException) as e:
        case_service.create_case(db, CaseCreate(company_name="X", engagement_route="Transfer In", jurisdiction="BVI",
                                                incorporation_date=date(2020, 1, 1)), rm)
    assert "Previous registered agent" in e.value.detail
    with pytest.raises(HTTPException) as e:
        case_service.create_case(db, CaseCreate(company_name="X", engagement_route="Existing Entity", jurisdiction="BVI",
                                                incorporation_date=date(2020, 1, 1), last_esr_date=date(2099, 1, 1)), rm)
    assert "future" in e.value.detail
    with pytest.raises(HTTPException):
        case_service.create_case(db, CaseCreate(company_name="X", engagement_route="Merger"), rm)


# ─── Transfer In ────────────────────────────────────────────────────────────

def test_transfer_in_gets_checklist_and_history_based_calendar(db, people):
    rm, mlro = people["rm"], people["mlro"]
    case = case_service.create_case(db, CaseCreate(
        company_name="Seabird Holdings", engagement_route="Transfer In", jurisdiction="BVI",
        previous_agent="ILS Fiduciary", incorporation_date=date(2015, 6, 1), last_renewal_date=date(2025, 6, 1)), rm)
    assert case.stage == CaseStage.NEW_INQUIRY and case.previous_agent == "ILS Fiduciary"
    cdd = db.query(CDDRecord).filter(CDDRecord.case_id == case.id).one()
    docs = {d.doc_type for d in db.query(CaseDocument).filter(CaseDocument.cdd_record_id == cdd.id)}
    assert "Recent Certificate of Good Standing" in docs and "Register of Members (ROM)" in docs

    case_ok.approve(db, case, mlro)
    case_service._create_compliance_schedule(db, case)  # what reaching "Transfer Completed" does
    s = schedule(db, case)
    assert s.renewal_last_completed_date == date(2025, 6, 1) and s.renewal_due_date == date(2026, 6, 1)


def test_formation_unchanged(db, people):
    case = case_service.create_case(db, CaseCreate(company_name="New Co"), people["rm"])
    assert case.engagement_route == "Formation" and case.stage == CaseStage.NEW_INQUIRY and case.prior_filing_dates is None


# ─── Bulk import ────────────────────────────────────────────────────────────

ROWS = [
    {"company_name": "Alpha BVI Ltd", "jurisdiction": "BVI", "incorporation_date": "14/03/2019", "company_number": "200001",
     "registered_agent": "Vistra", "last_renewal_date": "14/03/2026", "last_ar_date": "30/09/2025", "rm_email": ""},
    {"company_name": "Beta BVI Ltd", "jurisdiction": "bvi", "incorporation_date": "2020-01-05", "company_number": "200002"},
    {"company_name": "Alpha BVI Ltd", "jurisdiction": "BVI", "incorporation_date": "01/01/2020"},  # duplicate in file
    {"company_name": "Gamma Ltd", "jurisdiction": "Atlantis", "incorporation_date": "01/01/2020"},
    {"company_name": "Delta Ltd", "jurisdiction": "BVI", "incorporation_date": "31/02/2020"},
    {"company_name": "", "jurisdiction": "BVI", "incorporation_date": "01/01/2020"},
]


def test_import_entities_dry_run_then_import(db, people, make_account):
    admin = people["admin"]
    preview = engagement_service.import_entities(db, admin, ROWS, dry_run=True)
    assert [r["status"] for r in preview] == ["ok", "ok", "duplicate", "error", "error", "error"]
    assert "Atlantis" in preview[3]["message"] and "not a date" in preview[4]["message"]
    assert db.query(Case).count() == 0  # dry run writes nothing

    results = engagement_service.import_entities(db, admin, ROWS, dry_run=False)
    alpha = db.get(Case, results[0]["case_id"])
    assert alpha.stage == CaseStage.ACTIVE and alpha.compliance_status == "Approved" and alpha.engagement_route == "Existing Entity"
    s = schedule(db, alpha)
    assert s.renewal_due_date == date(2027, 3, 14) and s.ar_filing_due_date == date(2026, 9, 30)
    assert db.query(AuditLog).filter(AuditLog.action == "import").count() == 2
    # Running the same file again finds nothing new.
    again = engagement_service.import_entities(db, admin, ROWS[:2], dry_run=True)
    assert [r["status"] for r in again] == ["duplicate", "duplicate"]


def test_import_entity_links_client_and_rm(db, people, make_account):
    admin, rm = people["admin"], people["rm"]
    acc = make_account(name="Alpha Group", spoc=rm, client_id="TCPL/00009")
    [r] = engagement_service.import_entities(db, admin, [{"company_name": "Alpha Sub Ltd", "jurisdiction": "BVI",
                                                          "incorporation_date": "01/01/2021", "client_id": "tcpl/00009"}], dry_run=False)
    case = db.get(Case, r["case_id"])
    assert case.account_id == acc.id and case.rm_id == rm.id
    db.refresh(acc)
    assert acc.total_cases == 1  # the Clients table count follows the import
    [bad] = engagement_service.import_entities(db, admin, [{"company_name": "Z", "jurisdiction": "BVI", "incorporation_date": "01/01/2021",
                                                            "client_id": "TCPL/99999"}], dry_run=True)
    assert bad["status"] == "error" and "No client" in bad["message"]


def test_import_service_requests(db, people, make_account, seed_master):
    seed_master("service_request_type", ["AR Filing", "Change of Address"])
    admin, rm = people["admin"], people["rm"]
    acc = make_account(name="Falcon Trading LLC", spoc=rm, client_id="TCPL/00001")
    rows = [
        {"client_id": "TCPL/00001", "request_type": "Change of Address", "status": "in progress", "date_received": "01/10/2026",
         "charge_amount": "1,500", "comments": "JLT office"},
        {"company_name": "falcon trading llc", "request_type": "AR Filing", "status": "Pending"},
        {"company_name": "Unknown Co", "request_type": "AR Filing"},
        {"client_id": "TCPL/00001", "request_type": "Teleportation"},
        {"client_id": "TCPL/00001", "request_type": "AR Filing", "status": "Done"},
    ]
    preview = engagement_service.import_service_requests(db, admin, rows, dry_run=True)
    assert [r["status"] for r in preview] == ["ok", "ok", "error", "error", "error"]
    engagement_service.import_service_requests(db, admin, rows, dry_run=False)
    reqs = db.query(Instruction).filter(Instruction.account_id == acc.id).all()
    assert len(reqs) == 2
    first = next(r for r in reqs if r.instruction_type == "Change of Address")
    assert first.status == "In Progress" and str(first.charge_amount) == "1500.00" and first.date_received == date(2026, 10, 1)


def test_import_is_admin_only_via_api(db, people):
    from app.auth.dependencies import require_admin
    from app.routers import cases_router, instructions_router
    deps = {r.path: r.dependant for r in cases_router.router.routes if r.path.endswith("/import")}
    deps.update({r.path: r.dependant for r in instructions_router.router.routes if r.path.endswith("/import")})
    assert len(deps) == 2
    for d in deps.values():
        assert any(sub.call is require_admin for sub in d.dependencies)


def test_unknown_last_filing_is_not_shown_as_years_overdue(db, people):
    # Regression: an established company with no "last ESR" date got an ESR due date one year
    # after incorporation (e.g. 2020), i.e. thousands of days overdue.
    [r] = engagement_service.import_entities(db, people["admin"], [{"company_name": "Northwind Holdings Ltd", "jurisdiction": "BVI",
                                                                     "incorporation_date": "05/01/2020"}], dry_run=False)
    s = schedule(db, db.get(Case, r["case_id"]))
    assert s.esr_filing_due_date >= date.today() and s.esr_filing_last_completed_date is None
