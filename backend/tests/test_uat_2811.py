"""Triam UAT 28-11-2026: dashboard wording and Portfolio by RM, next actions of call / visit reports (reminder and
Due soon), and the Screening Date at most 30 days old (25-11-2026 row 202)."""
from datetime import date, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from app.models import Activity, Notification
from app.schemas.account import AccountUpdate
from app.services import account_service, dashboard_service, my_work_service, scheduler_jobs
from app.services.standard_reports_service import BUSINESS_TZ
from tests.flow import complete_client


@pytest.fixture()
def sweep_db(engine, monkeypatch):
    monkeypatch.setattr(scheduler_jobs, "SessionLocal", sessionmaker(bind=engine, autoflush=False, autocommit=False))


def _report(db, owner, acc, due, uid, status="Completed", action="Send the revised proposal"):
    act = Activity(activity_uid=uid, company_name=acc.company_name, account_id=acc.id, owner_id=owner.id,
                   activity_date=date.today() - timedelta(days=2), activity_type="Call Report", status=status,
                   summary="Discussed fees", next_action=action, due_date=due)
    db.add(act)
    db.commit()
    return act


def test_amendments_tile_says_compliance_approval(db, make_user, make_role):
    co = make_user(business_role=make_role("Compliance Officer", ["client.approve"]))
    labels = {w["key"]: w["label"] for w in my_work_service.my_work(db, co)}
    assert labels["compliance_changes"] == "Client amendments waiting for Compliance Approval"


def test_portfolio_by_rm_lists_only_rms(db, make_user, make_role, make_account):
    rm = make_user("Rita RM", business_role=make_role("Rel. Manager", ["client.portfolio", "prospect.assign"]))
    sales = make_user("Sam Sales", business_role=make_role("Sales Manager", ["client.portfolio", "read_only", "view.department_clients"]))
    co = make_user("Cora CO", business_role=make_role("Compliance Officer", ["client.approve", "view.all_clients"]))
    make_account(spoc=co, profile_status="Active")  # a CO set as a client's RM is still not listed
    names = {p["name"] for p in dashboard_service.build_dashboard(db, make_user(role="admin"))["portfolio_by_rm"]}
    assert rm.name in names
    assert sales.name not in names and co.name not in names


def test_next_actions_show_in_due_soon(db, make_user, make_account):
    rm = make_user("Rita RM")
    acc = make_account(name="Next Co", spoc=rm, profile_status="Active")
    _report(db, rm, acc, date.today() + timedelta(days=3), "ACT-9101")
    _report(db, rm, acc, date.today() + timedelta(days=5), "ACT-9102", status="Cancelled")
    _report(db, rm, acc, date.today() - timedelta(days=90), "ACT-9103")  # long overdue: dropped from the list
    due = [d for d in dashboard_service.build_dashboard(db, rm)["due_soon"] if d.get("kind") == "next_action"]
    assert len(due) == 1
    assert due[0]["days"] == 3 and "Send the revised proposal" in due[0]["what"]
    assert dashboard_service.build_dashboard(db, make_user("Other RM"))["due_soon"] == []


def test_rm_is_reminded_of_a_next_action_the_day_before_and_on_the_day(db, sweep_db, make_user, make_account):
    rm = make_user("Rita RM")
    acc = make_account(name="Remind Co", spoc=rm, profile_status="Active")
    _report(db, rm, acc, date.today() + timedelta(days=1), "ACT-9201")
    _report(db, rm, acc, date.today(), "ACT-9202")
    _report(db, rm, acc, date.today() + timedelta(days=4), "ACT-9203")
    _report(db, rm, acc, date.today(), "ACT-9204", status="Cancelled")
    scheduler_jobs.check_next_actions_due()
    scheduler_jobs.check_next_actions_due()  # once each, not every run
    db.expire_all()
    notes = db.query(Notification).filter(Notification.user_id == rm.id, Notification.notification_type.like("next_action_%")).all()
    assert len(notes) == 2
    texts = " | ".join(n.message for n in notes)
    assert "due tomorrow" in texts and "due today" in texts and "Remind Co" in texts


def test_screening_date_at_most_30_days_old(db, people):
    acc = complete_client(db, people["maker"])
    today = datetime.now(BUSINESS_TZ).date()
    with pytest.raises(HTTPException) as e:
        account_service.update_account(db, acc.id, AccountUpdate(screening_date=today - timedelta(days=31)), people["maker"])
    assert "30 days" in e.value.detail
    saved = account_service.update_account(db, acc.id, AccountUpdate(screening_date=today - timedelta(days=30)), people["maker"])
    assert saved.screening_date == today - timedelta(days=30)
