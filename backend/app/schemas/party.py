"""Pydantic schemas: Director and Shareholder registers."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

from app.models.party import PartyType, ShareholderType


class DirectorBase(BaseModel):
    director_type: PartyType = PartyType.INDIVIDUAL

    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    former_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    place_of_birth: Optional[str] = None
    nationality: Optional[str] = None
    passport_number: Optional[str] = None

    corporate_name: Optional[str] = None
    corporate_number: Optional[str] = None
    country_of_incorporation: Optional[str] = None
    corporate_date_of_incorporation: Optional[date] = None

    service_address: Optional[str] = None
    service_city: Optional[str] = None
    service_country: Optional[str] = None

    residential_address: Optional[str] = None
    residential_city: Optional[str] = None
    residential_country: Optional[str] = None

    appointment_date: Optional[date] = None
    cessation_date: Optional[date] = None
    notes: Optional[str] = None


class DirectorCreate(DirectorBase):
    pass


class DirectorUpdate(BaseModel):
    director_type: Optional[PartyType] = None
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    former_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    place_of_birth: Optional[str] = None
    nationality: Optional[str] = None
    passport_number: Optional[str] = None
    corporate_name: Optional[str] = None
    corporate_number: Optional[str] = None
    country_of_incorporation: Optional[str] = None
    corporate_date_of_incorporation: Optional[date] = None
    service_address: Optional[str] = None
    service_city: Optional[str] = None
    service_country: Optional[str] = None
    residential_address: Optional[str] = None
    residential_city: Optional[str] = None
    residential_country: Optional[str] = None
    appointment_date: Optional[date] = None
    cessation_date: Optional[date] = None
    notes: Optional[str] = None


class DirectorRead(DirectorBase):
    id: int
    case_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ShareholderBase(BaseModel):
    identification_type: ShareholderType = ShareholderType.INDIVIDUAL
    name: str = Field(..., min_length=1, max_length=255)
    corporate_number: Optional[str] = None
    country_of_incorporation: Optional[str] = None

    registered_address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None

    certificate_no: Optional[str] = None
    number_of_shares: Optional[int] = Field(None, ge=0)
    share_class: Optional[str] = None
    shareholding_percent: Optional[Decimal] = Field(None, ge=0, le=100)

    is_joint_shareholder: bool = False
    is_nominee: bool = False
    nominee_holds_for: Optional[str] = None

    date_entered: Optional[date] = None
    date_ceased: Optional[date] = None
    notes: Optional[str] = None


class ShareholderCreate(ShareholderBase):
    pass


class ShareholderUpdate(BaseModel):
    identification_type: Optional[ShareholderType] = None
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    corporate_number: Optional[str] = None
    country_of_incorporation: Optional[str] = None
    registered_address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    certificate_no: Optional[str] = None
    number_of_shares: Optional[int] = Field(None, ge=0)
    share_class: Optional[str] = None
    shareholding_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    is_joint_shareholder: Optional[bool] = None
    is_nominee: Optional[bool] = None
    nominee_holds_for: Optional[str] = None
    date_entered: Optional[date] = None
    date_ceased: Optional[date] = None
    notes: Optional[str] = None


class ShareholderRead(ShareholderBase):
    id: int
    case_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
