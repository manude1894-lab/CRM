"""Pydantic schemas: Account."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from decimal import Decimal

from app.models.account import Priority


class AccountBase(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    industry: Optional[str] = None
    country: Optional[str] = None
    company_size: Optional[str] = None
    website: Optional[str] = None
    strategic_priority: Priority = Priority.MEDIUM
    existing_relationship: str = "No"
    key_contacts: Optional[str] = None
    tags: Optional[str] = None
    owner_id: Optional[int] = None


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    company_name: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    company_size: Optional[str] = None
    website: Optional[str] = None
    strategic_priority: Optional[Priority] = None
    existing_relationship: Optional[str] = None
    key_contacts: Optional[str] = None
    tags: Optional[str] = None
    owner_id: Optional[int] = None


class AccountRead(AccountBase):
    id: int
    account_uid: str
    total_cases: int
    total_invoiced_amount: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
