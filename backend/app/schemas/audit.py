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
    def from_row(cls, row, viewer=None) -> "AuditEntryRead":
        out = cls.model_validate(row)
        out.user_name = support_name(row.user, viewer)
        return out


def support_name(user, viewer=None):
    """Who did it, as shown to the viewer: the support account appears as "System support" to others."""
    if user is None:
        return None
    if user.is_super_admin and not (viewer is not None and viewer.is_super_admin):
        return "System support"
    return user.name
