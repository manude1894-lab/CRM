"""Pydantic schemas: ServiceFeedback (staff-logged client feedback)."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import date, datetime


class ServiceFeedbackBase(BaseModel):
    instruction_id: Optional[int] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    comments: Optional[str] = None
    received_via: Optional[str] = None
    feedback_date: Optional[date] = None


class ServiceFeedbackCreate(ServiceFeedbackBase):
    pass


class ServiceFeedbackRead(ServiceFeedbackBase):
    id: int
    case_id: int
    recorded_by_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
