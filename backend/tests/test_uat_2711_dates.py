"""Triam UAT 27-11-2026: dates that can't be in the future (CDD Completion, a service request's Date Received)."""
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.schemas.account import AccountUpdate
from app.schemas.instruction import InstructionCreate, InstructionUpdate
from app.services import account_service, instruction_service
from app.services.standard_reports_service import BUSINESS_TZ
from tests.flow import complete_client


def test_cdd_completion_date_not_in_the_future(db, people):
    acc = complete_client(db, people["maker"])
    today = datetime.now(BUSINESS_TZ).date()
    with pytest.raises(HTTPException) as e:
        account_service.update_account(db, acc.id, AccountUpdate(cdd_completion_date=today + timedelta(days=730)), people["checker"])
    assert "CDD Completion Date" in e.value.detail
    saved = account_service.update_account(db, acc.id, AccountUpdate(cdd_completion_date=today), people["checker"])
    assert saved.cdd_completion_date == today


def test_service_request_not_received_in_the_future(db, make_user, make_account, seed_master):
    seed_master("service_request_type", ["Change of Address"])
    rm = make_user()
    acc = make_account(spoc=rm, profile_status="Active")
    today = datetime.now(BUSINESS_TZ).date()
    with pytest.raises(HTTPException) as e:
        instruction_service.create_instruction(db, InstructionCreate(account_id=acc.id, instruction_type="Change of Address",
                                                                     date_received=today + timedelta(days=2)), rm)
    assert "Date Received" in e.value.detail
    sr = instruction_service.create_instruction(db, InstructionCreate(account_id=acc.id, instruction_type="Change of Address",
                                                                      date_received=today), rm)
    with pytest.raises(HTTPException):
        instruction_service.update_instruction(db, sr.id, InstructionUpdate(date_received=today + timedelta(days=1)), rm)
