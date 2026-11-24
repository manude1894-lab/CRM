"""Pydantic schemas: Activity (Visit / Call Reports)."""
from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional
from datetime import date, datetime

from app.models.activity import ActivityType, ActivityStatus


class ActivityBase(BaseModel):
    account_id: Optional[int] = None  # required on create (the service checks it)
    company_name: Optional[str] = Field(None, max_length=255)  # defaults to the client's name
    activity_date: date
    activity_type: ActivityType
    summary: Optional[str] = None  # required for the final report; a draft may be unfinished
    outcome: Optional[str] = None
    next_action: Optional[str] = None
    due_date: Optional[date] = None
    owner_id: Optional[int] = None
    # Visit / Call Report details
    client_contact: Optional[str] = Field(None, max_length=150)
    attendees: Optional[str] = None
    location: Optional[str] = Field(None, max_length=200)
    purpose: Optional[str] = Field(None, max_length=200)


class ActivityCreate(ActivityBase):
    # Triam 23-11-2026: "Save Draft" (False) or "Save the Report" (True).
    final: bool = False


class ActivityUpdate(BaseModel):
    company_name: Optional[str] = None
    activity_date: Optional[date] = None
    activity_type: Optional[ActivityType] = None
    summary: Optional[str] = None
    outcome: Optional[str] = None
    next_action: Optional[str] = None
    due_date: Optional[date] = None
    owner_id: Optional[int] = None
    client_contact: Optional[str] = Field(None, max_length=150)
    attendees: Optional[str] = None
    location: Optional[str] = Field(None, max_length=200)
    purpose: Optional[str] = Field(None, max_length=200)
    final: bool = False


class CorrectionCreate(BaseModel):
    text: str = Field(..., min_length=2, max_length=2000)


class CorrectionRead(BaseModel):
    id: int
    text: str
    author_name: Optional[str] = None
    created_at: Optional[datetime] = None


class ActivityRead(ActivityBase):
    id: int
    activity_uid: str
    status: ActivityStatus
    cancel_reason: Optional[str] = None
    owner_name: Optional[str] = None
    finalised_at: Optional[datetime] = None
    finalised_by_name: Optional[str] = None
    corrections: list[CorrectionRead] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def _names(cls, obj):
        """Who wrote, finalised and corrected the report, read from the database object."""
        if hasattr(obj, "__table__"):
            data = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
            data["owner_name"] = obj.owner.name if obj.owner else None
            data["finalised_by_name"] = obj.finalised_by.name if obj.finalised_by else None
            data["corrections"] = [{"id": c.id, "text": c.text, "author_name": c.author.name if c.author else None,
                                    "created_at": c.created_at} for c in obj.corrections]
            return data
        return obj
