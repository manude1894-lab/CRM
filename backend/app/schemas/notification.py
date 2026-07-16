"""Pydantic schemas: Notification."""
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class NotificationRead(BaseModel):
    id: int
    case_id: Optional[int] = None
    notification_type: str
    message: str
    link: Optional[str] = None
    read_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
