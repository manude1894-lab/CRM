"""Pydantic schemas: Activity."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import date, datetime

from app.models.activity import ActivityType, ActivityStatus


class ActivityBase(BaseModel):
    case_id: int
    company_name: str = Field(..., min_length=1, max_length=255)
    activity_date: date
    activity_type: ActivityType
    status: ActivityStatus = ActivityStatus.PLANNED
    summary: str = Field(..., min_length=1)
    outcome: Optional[str] = None
    next_action: Optional[str] = None
    due_date: Optional[date] = None
    owner_id: Optional[int] = None


class ActivityCreate(ActivityBase):
    pass


class ActivityUpdate(BaseModel):
    company_name: Optional[str] = None
    activity_date: Optional[date] = None
    activity_type: Optional[ActivityType] = None
    status: Optional[ActivityStatus] = None
    summary: Optional[str] = None
    outcome: Optional[str] = None
    next_action: Optional[str] = None
    due_date: Optional[date] = None
    owner_id: Optional[int] = None


class ActivityRead(ActivityBase):
    id: int
    activity_uid: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
