"""Pydantic schemas: client workflow / maker-checker (BRD §11, §12, §15)."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SubmitRequest(BaseModel):
    comment: Optional[str] = Field(None, max_length=1000)


class ApproveRequest(BaseModel):
    comment: Optional[str] = Field(None, max_length=1000)


class RejectRequest(BaseModel):
    reason_code: str = Field(..., min_length=1, max_length=60)
    reason_text: str = Field(..., max_length=2000)


class StatusActionRequest(BaseModel):
    action: str  # activate | deactivate | reactivate | mark_exit | cancel_exit | confirm_exit
    reason: Optional[str] = Field(None, max_length=500)


class ApprovalRead(BaseModel):
    id: int
    account_id: int
    request_type: str
    status: str
    maker_id: Optional[int] = None
    maker_name: Optional[str] = None
    submitted_at: datetime
    maker_comment: Optional[str] = None
    checker_id: Optional[int] = None
    checker_name: Optional[str] = None
    decided_at: Optional[datetime] = None
    reason_code: Optional[str] = None
    reason_text: Optional[str] = None
    # Inbox convenience
    company_name: Optional[str] = None
    client_id: Optional[str] = None
    account_type: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_row(cls, r) -> "ApprovalRead":
        out = cls.model_validate(r)
        out.maker_name = r.maker.name if r.maker else None
        out.checker_name = r.checker.name if r.checker else None
        if r.account is not None:
            out.company_name, out.client_id, out.account_type = r.account.company_name, r.account.client_id, r.account.account_type
        return out


class WorkflowAction(BaseModel):
    action: str
    label: str
    allowed: bool
    reason: Optional[str] = None


class WorkflowState(BaseModel):
    status: str
    status_updated_at: Optional[datetime] = None
    status_updated_by: Optional[str] = None
    locked: bool
    actions: list[WorkflowAction]
    history: list[ApprovalRead]
