"""Pydantic schemas: AccountParty (Shareholders/Directors/Authorised Signatories on a Client)."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

from app.schemas.account import AddressBlock


class AccountPartyBase(BaseModel):
    party_role: str  # Shareholder / Director / Authorised Signatory
    constitution: str = "Individual"  # Individual / Entity

    full_name: str = Field(..., min_length=1, max_length=255)
    dob_or_incorp_date: Optional[date] = None
    id_or_license_expiry: Optional[date] = None
    country_of_incorp_or_birth: Optional[str] = None

    mobile: Optional[str] = None  # superseded by mobile_country_code/mobile_number
    mobile_country_code: Optional[str] = None
    mobile_number: Optional[str] = Field(None, max_length=12)
    email: Optional[str] = None

    country_of_residence: Optional[str] = None
    residential_address: Optional[AddressBlock] = None

    uae_visa_number: Optional[str] = None
    uae_visa_expiry: Optional[date] = None

    is_pep: bool = False

    effective_ownership_percent: Optional[Decimal] = None
    nominee_director_name: Optional[str] = None

    notes: Optional[str] = None


class AccountPartyCreate(AccountPartyBase):
    pass


class AccountPartyUpdate(BaseModel):
    party_role: Optional[str] = None
    constitution: Optional[str] = None
    full_name: Optional[str] = None
    dob_or_incorp_date: Optional[date] = None
    id_or_license_expiry: Optional[date] = None
    country_of_incorp_or_birth: Optional[str] = None
    mobile: Optional[str] = None
    mobile_country_code: Optional[str] = None
    mobile_number: Optional[str] = Field(None, max_length=12)
    email: Optional[str] = None
    country_of_residence: Optional[str] = None
    residential_address: Optional[AddressBlock] = None
    uae_visa_number: Optional[str] = None
    uae_visa_expiry: Optional[date] = None
    is_pep: Optional[bool] = None
    effective_ownership_percent: Optional[Decimal] = None
    nominee_director_name: Optional[str] = None
    notes: Optional[str] = None


class AccountPartyRead(AccountPartyBase):
    id: int
    account_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
