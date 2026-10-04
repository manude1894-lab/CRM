"""Pydantic schemas: business roles (BRD §15 / §18)."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    department_id: Optional[int] = None
    permissions: list[str] = []
    is_active: bool = True


class RoleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    department_id: Optional[int] = None
    permissions: Optional[list[str]] = None
    is_active: Optional[bool] = None


class RoleRead(RoleCreate):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PermissionInfo(BaseModel):
    key: str
    description: str
