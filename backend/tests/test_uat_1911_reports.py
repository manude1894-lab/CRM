"""Triam UAT 19-11-2026, rows 155-176: the new reports, their filters (Triam Anchor Entity, Department, Client Tag,
Anchor RM, date range) and who may run them (amendments: CO and Approver; invoices and service requests: the
Accountant and the Sales Manager)."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models import Department, Invoice, UserRole
from app.schemas.account import AccountUpdate
from app.schemas.instruction import InstructionCreate, InstructionUpdate
from app.schemas.invoice import OnboardingInvoiceSave
from app.services import account_service, amendment_service as amend, instruction_service as sr, onboarding_invoice_service as onb
from app.services import standard_reports_service as rpt
from tests import flow
from tests.helpers import rows_of


@pytest.fixture()
def desk(db, people, make_user, make_role, seed_master):
    seed_master("triam_entity", ["TCPL"])
    seed_master("service_request_type", ["Financial Audit", "Change of Directors"])
    return {**people,
            "admin": make_user("Ada", role=UserRole.ADMIN),
            "accountant": make_user("Ann Accounts", business_role=make_role("Accountant", ["invoice.manage", "view.all_clients"])),
            "sales": make_user("Sam Sales", business_role=make_role("Sales Manager", ["client.portfolio", "view.department_clients"]))}


def test_reports_are_offered_by_role(desk):
    rm, mlro, approver, acct, sales, admin = (desk[k] for k in ("maker", "checker", "approver", "accountant", "sales", "admin"))
    invoice_keys = {"invoices-onboarding", "invoices-service-requests", "invoices-pending", "service-requests-ageing"}
    assert not ({"amendments"} | invoice_keys) & set(rpt.available(rm))  # an RM sees the shared reports only
    assert "amendments" in rpt.available(mlro) and "amendments" in rpt.available(approver)
    assert not invoice_keys & set(rpt.available(mlro))
    assert invoice_keys <= set(rpt.available(acct)) and invoice_keys <= set(rpt.available(sales))
    assert "amendments" not in rpt.available(acct)
    assert set(rpt.REPORTS) == set(rpt.available(admin))


def test_a_report_outside_the_role_is_refused(db, desk):
    with pytest.raises(HTTPException) as e:
        rpt.run(db, desk["maker"], "invoices-pending")
    assert e.value.status_code == 403


def test_amendments_report_lists_each_field_before_and_after(db, desk, act_as):
    rm, mlro = desk["maker"], desk["checker"]
    acc = flow.approved_client(db, desk)
    amend.start(db, acc, rm)
    account_service.update_account(db, acc.id, AccountUpdate(nature_of_business="Banking", contact_email="new@x.example"), rm)
    amend.submit(db, acc, rm, "New business per licence")
    act_as(mlro)
    amend.approve(db, acc, mlro)
    rows = rows_of(rpt.run(db, mlro, "amendments"))
    changed = {r["Field"]: (r["Previous"], r["New"]) for r in rows}
    assert changed["Detailed Nature of Business"] == ("Fintech", "Banking")
    assert changed["Contact Email"] == ("info@complete.example", "new@x.example")
    first = rows[0]
    assert (first["Client Name"], first["Amended by"], first["Approved by"], first["Record"]) == ("Complete Co", "Rita RM", "Mia MLRO", "Client")
    today = rpt._today()
    assert rpt.run(db, mlro, "amendments", date_from=today + timedelta(days=1))["rows"] == []  # by approval date
    assert rpt.run(db, mlro, "amendments", entity="TABL")["rows"] == []  # the anchor entity filter


def _onboarding_invoice(db, desk):
    rm = desk["maker"]
    acc = flow.complete_client(db, rm)
    flow.submit(db, acc, rm)
    flow.approve_all(db, acc, desk["checker"], desk["approver"])
    onb.save(db, acc.id, OnboardingInvoiceSave(wanted=True, client_amount=Decimal("15000"), introducer_involved=False, submit=True), rm)
    return acc


def test_invoice_reports_and_pending(db, desk):
    acc = _onboarding_invoice(db, desk)
    inst = sr.create_instruction(db, InstructionCreate(account_id=acc.id, instruction_type="Financial Audit", triam_entity="TCPL",
                                                       charge_amount=Decimal("2500")), desk["maker"])
    sr.submit_instruction(db, inst.id, desk["maker"])
    acct = desk["accountant"]

    [o] = rows_of(rpt.run(db, acct, "invoices-onboarding"))
    assert (o["Client Name"], o["CUR"], o["AMOUNT"], o["Regn Authority"], o["Status"]) == ("Complete Co", "AED", 15000.0, "DMCC", "Requested")
    assert o["PROS ID"] == acc.temp_id and o["Invoice Raised on"] is None
    [s] = rows_of(rpt.run(db, acct, "invoices-service-requests"))
    assert s["AMOUNT"] == 2500.0

    pending = rows_of(rpt.run(db, acct, "invoices-pending"))
    assert {r["Request Type"] for r in pending} == {"Onboarding", "Service Request"}
    assert [r["Request Type"] for r in rows_of(rpt.run(db, acct, "invoices-pending", request_type="Onboarding"))] == ["Onboarding"]
    inv = db.query(Invoice).filter(Invoice.kind == "Onboarding").one()
    inv.status, inv.invoice_number, inv.raised_date = "Raised", "INV-1", date(2026, 11, 20)
    db.commit()
    assert [r["Request Type"] for r in rows_of(rpt.run(db, acct, "invoices-pending"))] == ["Service Request"]  # raised: no longer pending
    with pytest.raises(HTTPException):
        rpt.run(db, acct, "invoices-pending", request_type="Other")


def test_service_requests_ageing_and_filters(db, desk):
    rm = desk["maker"]
    dept = Department(name="Corporate Services")
    db.add(dept)
    db.commit()
    rm.department_id = desk["sales"].department_id = dept.id  # the Sales Manager sees their department's clients
    db.commit()
    acc = flow.approved_client(db, desk)
    done = sr.create_instruction(db, InstructionCreate(account_id=acc.id, instruction_type="Financial Audit", triam_entity="TCPL",
                                                       date_received=date(2026, 11, 1)), rm)
    sr.update_instruction(db, done.id, InstructionUpdate(date_completed=date(2026, 11, 11)), rm)
    sr.create_instruction(db, InstructionCreate(account_id=acc.id, instruction_type="Change of Directors", triam_entity="TCPL",
                                                date_received=rpt._today() - timedelta(days=4)), rm)
    rows = rows_of(rpt.run(db, desk["sales"], "service-requests-ageing"))
    ageing = {r["Request Type"]: r["Ageing (days)"] for r in rows}
    assert ageing == {"Financial Audit": 10, "Change of Directors": 4}
    assert rows[0]["Request Type"] == "Change of Directors"  # latest first
    only = rows_of(rpt.run(db, desk["sales"], "service-requests-ageing", sr_type="Financial Audit"))
    assert [r["Request Type"] for r in only] == ["Financial Audit"]
    assert rpt.run(db, desk["sales"], "service-requests-ageing", rm_id=desk["other_rm"].id)["rows"] == []


def test_department_and_tag_filters(db, desk, make_account):
    sales_dept = Department(name="Sales")
    db.add(sales_dept)
    db.commit()
    rita = desk["maker"]
    rita.department_id = sales_dept.id
    db.commit()
    a = make_account(name="Tagged Co", spoc=rita, anchor_entity="TCPL", tags="FZ", profile_status="Active")
    db.add(Invoice(account_id=a.id, kind="Onboarding", amount=Decimal("100"), currency="AED", status="Requested",
                   requested_at=rpt.datetime.now(rpt.timezone.utc), description="Onboarding services"))
    db.commit()
    admin = desk["admin"]
    assert len(rpt.run(db, admin, "invoices-pending", tag="FZ")["rows"]) == 1
    assert rpt.run(db, admin, "invoices-pending", tag="ONSHORE")["rows"] == []
    assert len(rpt.run(db, admin, "invoices-pending", department_id=sales_dept.id)["rows"]) == 1
    assert len(rpt.run(db, admin, "invoices-pending", rm_id=rita.id, entity="TCPL")["rows"]) == 1
