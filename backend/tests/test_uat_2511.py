"""Triam UAT 25-11-2026: the bugs found in the sheet."""
from datetime import date, datetime, timedelta

import pytest
from fastapi import HTTPException

from app.models import AccountParty
from app.schemas.account import AccountUpdate
from app.schemas.account_party import AccountPartyCreate
from app.schemas.activity import ActivityCreate, ActivityUpdate
from app.services import account_party_service, account_service, activity_service, standard_reports_service as rpt
from app.services.standard_reports_service import BUSINESS_TZ
from tests.flow import complete_client


def _report(acc, **kw):
    base = dict(account_id=acc.id, activity_date=date.today(), activity_type="Call Report", summary="Renewal", client_contact="Omar")
    base.update(kw)
    return ActivityCreate(**base)


def test_row_200_next_action_cannot_be_due_in_the_past(db, make_user, make_account):
    rm = make_user("Rita RM")
    acc = make_account(spoc=rm, profile_status="Active")
    with pytest.raises(HTTPException) as e:
        activity_service.create_activity(db, _report(acc, due_date=date.today() - timedelta(days=3)), rm)
    assert "Next action due" in e.value.detail
    act = activity_service.create_activity(db, _report(acc, due_date=date.today() + timedelta(days=7)), rm)
    with pytest.raises(HTTPException):
        activity_service.update_activity(db, act.id, ActivityUpdate(due_date=date.today() - timedelta(days=1)), rm)


def test_row_202_meeting_not_later_than_now(db, people):
    acc = complete_client(db, people["maker"])
    now = datetime.now(BUSINESS_TZ)
    with pytest.raises(HTTPException) as e:
        account_service.update_account(db, acc.id, AccountUpdate(br_meeting_date=now.date() + timedelta(days=1)), people["maker"])
    assert "Date of Meeting" in e.value.detail
    if now.hour < 23:  # a later time today
        with pytest.raises(HTTPException) as e:
            account_service.update_account(db, acc.id, AccountUpdate(br_meeting_date=now.date(), br_meeting_time="23:59"), people["maker"])
        assert "Time of Meeting" in e.value.detail
    account_service.update_account(db, acc.id, AccountUpdate(br_meeting_date=now.date() - timedelta(days=1), br_meeting_time="23:59"), people["maker"])


def test_a_persons_long_expired_visa_is_refused(db, people):
    maker = people["maker"]
    acc = complete_client(db, maker)
    with pytest.raises(HTTPException) as e:
        account_party_service.create_party(db, acc.id, AccountPartyCreate(
            party_role="Director", full_name="Old Visa", nationality="India", country_of_incorp_or_birth="India",
            mobile_country_code="+971", mobile_number="501234567", email="ov@example.com", country_of_residence="India",
            uae_visa_expiry=date(1980, 7, 11)), maker)
    assert "UAE visa of Old Visa" in e.value.detail


def test_documents_report_lists_a_persons_document_once(db, make_user, make_account):
    admin = make_user("Ada Admin", role="admin")
    acc = make_account(name="Silverstone Advisory Ltd", profile_status="Active", anchor_entity="TCPL")
    expiry = date.today() + timedelta(days=5)
    for role in ("Shareholder", "Authorised Signatory"):
        db.add(AccountParty(account_id=acc.id, party_role=role, full_name="Widaan", dob_or_incorp_date=date(1985, 1, 1),
                            uae_visa_number="1234567", uae_visa_expiry=expiry))
    db.commit()
    rows = [r for r in rpt.documents_expiring(db, admin, 30)["rows"] if r[6] == "UAE Visa"]
    assert len(rows) == 1 and rows[0][5] == "Widaan (Shareholder, Authorised Signatory)"
