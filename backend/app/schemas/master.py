"""Pydantic schemas: master data lists (BRD §18)."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MasterItemCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=150)
    code: Optional[str] = Field(None, max_length=60)  # defaults to the label
    sort_order: Optional[int] = None
    is_active: bool = True
    meta: Optional[dict] = None


class MasterItemUpdate(BaseModel):
    label: Optional[str] = Field(None, min_length=1, max_length=150)
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    meta: Optional[dict] = None


class MasterItemRead(BaseModel):
    id: int
    list_type: str
    code: str
    label: str
    sort_order: int
    is_active: bool
    meta: Optional[dict] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class MasterListType(BaseModel):
    list_type: str
    title: str
