"""Pydantic schemas: ActionPoint (shared WIP task board)."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import date, datetime

from app.models.action_point import ActionPointStatus


class ActionPointBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    detail: Optional[str] = None
    case_id: Optional[int] = None
    owner_id: Optional[int] = None
    status: ActionPointStatus = ActionPointStatus.OPEN
    priority: str = "Medium"
    due_date: Optional[date] = None


class ActionPointCreate(ActionPointBase):
    pass


class ActionPointUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    detail: Optional[str] = None
    case_id: Optional[int] = None
    owner_id: Optional[int] = None
    status: Optional[ActionPointStatus] = None
    priority: Optional[str] = None
    due_date: Optional[date] = None


class ActionPointRead(ActionPointBase):
    id: int
    created_by_id: Optional[int] = None
    completed_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
