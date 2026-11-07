"""UAT 05/06-11-2026 (UAT-06, 24): screening date on the client, screening reports on any client."""
import io
from datetime import date, timedelta

import pytest
from fastapi import HTTPException, UploadFile

from app.schemas.account import AccountUpdate
from app.services import account_service, amendment_service as amend, document_service
from tests import flow


def test_screening_date_is_saved_and_can_not_be_in_the_future(db, real_user):
    rm = real_user("Rel. Manager")
    acc = flow.complete_client(db, rm)
    account_service.update_account(db, acc.id, AccountUpdate(screening_date=date.today()), rm)
    db.refresh(acc)
    assert acc.screening_date == date.today()
    with pytest.raises(HTTPException):
        account_service.update_account(db, acc.id, AccountUpdate(screening_date=date.today() + timedelta(days=1)), rm)


def test_screening_date_is_not_mandatory(db, real_user):
    acc = flow.complete_client(db, real_user("Rel. Manager"))
    assert acc.screening_date is None and account_service.missing_mandatory(acc) == []


def test_changing_it_on_an_approved_client_shows_in_the_amendment(db, real_user):
    rm, mlro, approver = real_user("Rel. Manager"), real_user("MLRO"), real_user("Approver")
    acc = flow.approved_client(db, {"maker": rm, "checker": mlro, "approver": approver})
    amend.start(db, acc, rm)
    account_service.update_account(db, acc.id, AccountUpdate(screening_date=date.today()), rm)
    req = amend.submit(db, acc, rm, "Screening repeated")
    assert [c["label"] for c in req.changes["account"]] == ["Screening Date"]


@pytest.mark.parametrize("on_a_person", [False, True], ids=["company", "person"])
def test_a_screening_report_files_on_a_non_individual_client(db, real_user, seed_master, on_a_person):
    seed_master("document_category", ["Sanctions Screening Result"])
    rm = real_user("Rel. Manager")
    acc = flow.complete_client(db, rm)
    f = UploadFile(file=io.BytesIO(b"%PDF-1.4"), filename="screening.pdf", headers={"content-type": "application/pdf"})
    doc = document_service.create_for_account(db, acc.id, f, "Sanctions Screening Result", rm, party_id=acc.parties[0].id if on_a_person else None)
    assert doc.category == "Sanctions Screening Result"
