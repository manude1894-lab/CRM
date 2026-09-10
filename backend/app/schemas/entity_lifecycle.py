"""Pydantic schemas: EntityLifecycle (closure / restoration / RA transfer)."""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import date, datetime

from app.models.entity_lifecycle import ClosureMethod, RestorationStatus, StrikeOffCause


class ChecklistItem(BaseModel):
    key: str
    label: str
    status: str = "Pending"  # Pending | Received | N/A
    note: Optional[str] = None


class EntityLifecycleBase(BaseModel):
    # Closure / strike-off / lapse
    closure_method: Optional[ClosureMethod] = None
    closure_initiated_date: Optional[date] = None
    closure_reason: Optional[str] = None
    client_acknowledgement_received: Optional[bool] = None
    client_acknowledgement_date: Optional[date] = None
    outstanding_filings_cleared: Optional[bool] = None
    strike_off_date: Optional[date] = None
    strike_off_in_good_standing: Optional[bool] = None
    expected_dissolution_date: Optional[date] = None
    dissolution_confirmed: Optional[bool] = None
    dissolution_date: Optional[date] = None

    # Restoration
    restoration_status: Optional[RestorationStatus] = None
    restoration_initiated_date: Optional[date] = None
    restoration_completed_date: Optional[date] = None
    strike_off_cause: Optional[StrikeOffCause] = None
    restoration_checklist: Optional[List[ChecklistItem]] = None

    # Registered-agent transfer
    transfer_from_agent: Optional[str] = None
    transfer_to_agent: Optional[str] = None
    transfer_initiated_date: Optional[date] = None
    transfer_completed_date: Optional[date] = None
    transfer_ends_administration: Optional[bool] = None
    transfer_notes: Optional[str] = None


class EntityLifecycleUpdate(EntityLifecycleBase):
    pass


class EntityLifecycleRead(EntityLifecycleBase):
    id: int
    case_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
