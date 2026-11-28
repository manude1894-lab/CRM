"""Triam UAT 26/27-11-2026: Biz Rationale meeting by the user's own clock and at most 30 days back; supporting
documents for an amendment of an approved client."""
import io
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException, UploadFile

from app.models import Document
from app.request_context import client_timezone
from app.schemas.account import AccountUpdate
from app.services import account_service, amendment_service as amend, document_service
from tests.flow import approved_client, complete_client


def _pdf(name="lei-certificate.pdf"):
    return UploadFile(file=io.BytesIO(b"%PDF-1.4 test"), filename=name, headers={"content-type": "application/pdf"})


def test_meeting_at_most_30_days_back(db, people):
    acc = complete_client(db, people["maker"])
    today = datetime.now(ZoneInfo("Asia/Dubai")).date()
    with pytest.raises(HTTPException) as e:
        account_service.update_account(db, acc.id, AccountUpdate(br_meeting_date=today - timedelta(days=31)), people["maker"])
    assert "30 days back" in e.value.detail
    db.rollback()
    account_service.update_account(db, acc.id, AccountUpdate(br_meeting_date=today - timedelta(days=30), br_meeting_time="09:00"), people["maker"])


def test_meeting_time_by_the_users_own_clock(db, people):
    """India is 1:30 ahead of the UAE: a meeting an India user just had is accepted, though it is later than UAE time."""
    acc = complete_client(db, people["maker"])
    india = datetime.now(ZoneInfo("Asia/Kolkata"))
    uae = datetime.now(ZoneInfo("Asia/Dubai"))
    if india.date() != uae.date() or india.hour < 2:
        pytest.skip("near midnight the two dates differ")
    just_now = (india - timedelta(minutes=10)).strftime("%H:%M")
    assert just_now > uae.strftime("%H:%M")  # later than UAE time
    token = client_timezone.set("Asia/Kolkata")
    try:
        account_service.update_account(db, acc.id, AccountUpdate(br_meeting_date=india.date(), br_meeting_time=just_now), people["maker"])
    finally:
        client_timezone.reset(token)
    # The same time from a UAE user is still later than now.
    with pytest.raises(HTTPException) as e:
        account_service.update_account(db, acc.id, AccountUpdate(br_meeting_time="23:59"), people["maker"])
    assert "Time of Meeting" in e.value.detail


def test_engagement_letter_past_date_accepted(db, people):
    acc = complete_client(db, people["maker"])
    today = datetime.now(ZoneInfo("Asia/Dubai")).date()
    saved = account_service.update_account(db, acc.id, AccountUpdate(engagement_letter_signed=True,
                                                                    engagement_letter_valid_until=today - timedelta(days=200)), people["maker"])
    assert saved.engagement_letter_valid_until == today - timedelta(days=200)


def test_amendment_supporting_documents(db, people, act_as):
    maker, checker = people["maker"], people["checker"]
    acc = approved_client(db, people)
    req = amend.start(db, acc, maker)
    doc = document_service.create_for_account(db, acc.id, _pdf(), "Other", maker, approval_request_id=req.id)
    assert doc.approval_request_id == req.id
    view = amend.view(db, acc, maker)
    assert [d["filename"] for d in view["documents"]] == ["lei-certificate.pdf"] and view["documents"][0]["can_delete"]
    # Someone else can't attach to the maker's draft.
    with pytest.raises(HTTPException):
        document_service.create_for_account(db, acc.id, _pdf("x.pdf"), "Other", checker, approval_request_id=req.id)
    db.rollback()
    account_service.update_account(db, acc.id, AccountUpdate(lei_number="5493001KJTIIGC8Y1R12"), maker)
    amend.submit(db, acc, maker, "New LEI")
    # Compliance sees the document with the amendment; it can no longer be taken out.
    act_as(checker)
    seen = amend.view(db, acc, checker)["documents"]
    assert [d["filename"] for d in seen] == ["lei-certificate.pdf"] and not seen[0]["can_delete"]


def test_discarded_amendment_takes_its_documents_out(db, people):
    maker = people["maker"]
    acc = approved_client(db, people)
    req = amend.start(db, acc, maker)
    doc = document_service.create_for_account(db, acc.id, _pdf(), "Other", maker, approval_request_id=req.id)
    amend.discard(db, acc, maker)
    db.expire_all()
    assert db.get(Document, doc.id).removed_reason == "Amendment discarded"


def test_amendment_api_lists_its_documents(client, db, people):
    """The client screen and Compliance read the documents through the API."""
    from tests.helpers import auth
    maker = people["maker"]
    acc = approved_client(db, people)
    req = amend.start(db, acc, maker)
    document_service.create_for_account(db, acc.id, _pdf(), "Other", maker, approval_request_id=req.id)
    body = client.get(f"/api/v1/accounts/{acc.id}/amendment", headers=auth(maker)).json()
    assert [d["filename"] for d in body["documents"]] == ["lei-certificate.pdf"]
