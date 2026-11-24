"""Triam 23-11-2026 (S T Krishna): Visit / Call Reports have Cancel, Save Draft and Save the Report. The saved
report is final and stays as written for later review; a correction is a note beside it."""
from datetime import date

import pytest
from fastapi import HTTPException

from app.schemas.activity import ActivityCreate, ActivityUpdate
from app.services import activity_service as svc


def report(acc, **kw):
    base = dict(account_id=acc.id, activity_date=date(2026, 11, 23), activity_type="Call Report",
                summary="Renewal discussed", client_contact="Omar")
    base.update(kw)
    return ActivityCreate(**base)


def test_draft_then_final_then_locked(db, make_user, make_account):
    rm = make_user("Rita RM")
    acc = make_account(spoc=rm, profile_status="Active")
    d = svc.create_activity(db, report(acc, summary="", client_contact=None), rm)
    assert d.status.value == "Draft" and d.finalised_at is None
    d = svc.update_activity(db, d.id, ActivityUpdate(summary="Renewal discussed", client_contact="Omar", final=True), rm)
    assert d.status.value == "Completed" and d.finalised_at and d.finalised_by_id == rm.id
    with pytest.raises(HTTPException) as e:
        svc.update_activity(db, d.id, ActivityUpdate(summary="rewritten"), rm)
    assert e.value.status_code == 409


def test_corrections_are_notes_beside_the_final_report(db, make_user, make_account):
    rm = make_user("Rita RM")
    acc = make_account(spoc=rm, profile_status="Active")
    r = svc.create_activity(db, report(acc, final=True), rm)
    r = svc.add_correction(db, r.id, "The contact was Omar Haddad, not Omar Khan", rm)
    assert r.summary == "Renewal discussed" and [c.text for c in r.corrections] == ["The contact was Omar Haddad, not Omar Khan"]
    draft = svc.create_activity(db, report(acc), rm)
    with pytest.raises(HTTPException):
        svc.add_correction(db, draft.id, "a note", rm)  # a draft is simply edited


def test_only_the_writer_or_supervisor_changes_a_report(db, make_user, make_account):
    rm, other = make_user("Rita RM"), make_user("Otto RM")
    acc = make_account(spoc=rm, non_anchor=[other], profile_status="Active")
    d = svc.create_activity(db, report(acc), rm)
    with pytest.raises(HTTPException) as e:
        svc.update_activity(db, d.id, ActivityUpdate(summary="mine now"), other)
    assert e.value.status_code == 403


def test_history_filters_by_status_and_dates(db, make_user, make_account):
    rm = make_user("Rita RM")
    acc = make_account(spoc=rm, profile_status="Active")
    svc.create_activity(db, report(acc, activity_date=date(2025, 1, 10), final=True), rm)
    svc.create_activity(db, report(acc, activity_date=date(2026, 6, 1)), rm)
    finals, total = svc.list_activities(db, rm, status="Final")
    assert total == 1 and finals[0].activity_date == date(2025, 1, 10)  # an old report is still there
    in_2026, _ = svc.list_activities(db, rm, date_from=date(2026, 1, 1))
    assert [a.activity_date for a in in_2026] == [date(2026, 6, 1)]


def test_route_lists_pages_and_corrects(client, db, make_user, make_account):
    from tests.helpers import auth
    rm = make_user("Rita RM")
    acc = make_account(spoc=rm, profile_status="Active")
    r = client.post("/api/v1/activities", json={**report(acc).model_dump(mode="json"), "final": True}, headers=auth(rm))
    assert r.status_code == 201 and r.json()["status"] == "Completed" and r.json()["owner_name"] == "Rita RM"
    c = client.post(f"/api/v1/activities/{r.json()['id']}/corrections", json={"text": "Date was the 22nd"}, headers=auth(rm))
    assert c.status_code == 200 and c.json()["corrections"][0]["author_name"] == "Rita RM"
    page = client.get("/api/v1/activities", params={"status": "Final", "limit": 10}, headers=auth(rm)).json()
    assert page["total"] == 1
    assert client.get("/api/v1/activities", params={"limit": 5000}, headers=auth(rm)).status_code == 422
