"""Pydantic schemas: Department (org-structure master table)."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class DepartmentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    is_active: bool = True


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_active: Optional[bool] = None


class DepartmentRead(DepartmentBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
