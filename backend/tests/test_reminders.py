"""Daily reminders added 29-10-2026: other expiring documents, overdue invoices, prospects with no client,
approvals waiting; and alerts clearing once the work is done."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.orm import sessionmaker

from app.models import AccountParty, ApprovalRequest, Invoice, Notification, Prospect
from app.services import scheduler_jobs
from app.services import client_workflow_service as wf
from tests import flow
from tests.test_p2_workflow import complete_client, people  # noqa: F401  (fixture)


@pytest.fixture()
def sweep_db(engine, monkeypatch):
    monkeypatch.setattr(scheduler_jobs, "SessionLocal", sessionmaker(bind=engine, autoflush=False, autocommit=False))


def _days_ago(n):
    return datetime.now(timezone.utc) - timedelta(days=n)


def test_other_documents_and_peoples_ids_remind_the_rm(db, sweep_db, make_user, make_account):
    rm = make_user("Rita RM")
    acc = make_account(name="Expiry Co", spoc=rm, profile_status="Active",
                       engagement_letter_valid_until=date.today() + timedelta(days=7), lei_expiry_date=date.today() + timedelta(days=45))
    db.add(AccountParty(account_id=acc.id, party_role="Director", full_name="Dina Director", constitution="Individual",
                        id_or_license_expiry=date.today() + timedelta(days=30)))
    db.commit()
    scheduler_jobs.check_documents_expiring()
    scheduler_jobs.check_documents_expiring()  # deduped while unread
    messages = sorted(n.message for n in db.query(Notification).filter(Notification.user_id == rm.id))
    assert len(messages) == 2
    assert any("Engagement letter expires in 7 days" in m for m in messages)
    assert any("Passport of Dina Director (Director) expires in 30 days" in m for m in messages)


def test_raised_invoice_past_due_becomes_overdue(db, sweep_db, make_user, make_account, make_role):
    rm = make_user("Rita RM")
    accountant = make_user("Ann Accounts", business_role=make_role("Accountant", ["invoice.manage"]))
    acc = make_account(name="Late Payer", spoc=rm, profile_status="Active")
    inv = Invoice(account_id=acc.id, description="Fee", amount=Decimal("100"), currency="AED", status="Raised",
                  invoice_number="INV-1", requested_by_id=rm.id, due_date=date.today() - timedelta(days=1))
    db.add(inv)
    db.commit()
    scheduler_jobs.check_invoices_overdue()
    db.expire_all()
    assert db.get(Invoice, inv.id).status == "Overdue"
    assert {n.user_id for n in db.query(Notification).filter(Notification.notification_type == "invoice_overdue")} == {rm.id, accountant.id}


def test_prospect_with_no_client_reminds_the_rm(db, sweep_db, make_user):
    rm = make_user("Rita RM")
    db.add_all([
        Prospect(prospect_uid="PROS-1", company_name="Stale Ltd", owner_id=rm.id, assigned_at=_days_ago(20)),
        Prospect(prospect_uid="PROS-2", company_name="Fresh Ltd", owner_id=rm.id, assigned_at=_days_ago(2)),
    ])
    db.commit()
    scheduler_jobs.check_prospects_waiting()
    scheduler_jobs.check_prospects_waiting()
    [n] = db.query(Notification).all()
    assert n.user_id == rm.id and "Stale Ltd" in n.message


def test_waiting_approval_reminds_checkers_and_clears_when_decided(db, sweep_db, people):
    acc = complete_client(db, people["maker"])
    flow.submit(db, acc, people["maker"])
    req = db.query(ApprovalRequest).filter(ApprovalRequest.account_id == acc.id).one()
    req.submitted_at = _days_ago(5)
    db.commit()
    scheduler_jobs.check_approvals_waiting()
    waiting = db.query(Notification).filter(Notification.notification_type == "approval_waiting").all()
    assert {n.user_id for n in waiting} == {people["checker"].id, people["checker2"].id}
    flow.compliance_approve(db, acc, people["checker"])
    db.expire_all()
    # the "submitted" and "waiting" alerts to Compliance are done once Compliance decides
    unread = db.query(Notification).filter(Notification.account_id == acc.id, Notification.read_at.is_(None),
                                           Notification.notification_type.in_(["client_submitted", "approval_waiting"])).all()
    assert {n.user_id for n in unread} == {people["approver"].id}  # only the new "needs final approval" alert
