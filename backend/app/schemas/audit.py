"""Pydantic schemas: audit log entries (read-only)."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AuditEntryRead(BaseModel):
    id: int
    occurred_at: datetime
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    action: str
    subject_type: str
    subject_id: Optional[int] = None
    account_id: Optional[int] = None
    changes: Optional[dict] = None
    summary: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_row(cls, row) -> "AuditEntryRead":
        out = cls.model_validate(row)
        out.user_name = row.user.name if row.user else None
        return out
