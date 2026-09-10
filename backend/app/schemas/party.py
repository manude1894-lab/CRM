"""Pydantic schemas: Director and Shareholder registers."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Any
from datetime import date, datetime
from decimal import Decimal

from app.models.party import PartyType, ShareholderType, OwnershipNature, SourceOfWealthCategory


class _AppendixAMixin(BaseModel):
    """Vistra KYC Appendix A — individual KYC detail. Shared by Director + Shareholder."""
    email: Optional[str] = None
    mobile: Optional[str] = None
    occupation: Optional[str] = None
    employer_name: Optional[str] = None
    tax_residency_country: Optional[str] = None
    tax_id_number: Optional[str] = None
    source_of_funds: Optional[str] = None
    source_of_wealth: Optional[str] = None
    is_pep: Optional[bool] = None
    pep_notes: Optional[str] = None


class DirectorBase(_AppendixAMixin):
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
    entity_details: Optional[dict[str, Any]] = None

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


class DirectorUpdate(_AppendixAMixin):
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
    entity_details: Optional[dict[str, Any]] = None
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


class ShareholderBase(_AppendixAMixin):
    identification_type: ShareholderType = ShareholderType.INDIVIDUAL
    name: str = Field(..., min_length=1, max_length=255)
    corporate_number: Optional[str] = None
    country_of_incorporation: Optional[str] = None
    entity_details: Optional[dict[str, Any]] = None

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
    nominator_name: Optional[str] = None
    nominator_address: Optional[str] = None
    nominator_relationship: Optional[str] = None
    nominee_agreement_date: Optional[date] = None

    charges: Optional[list[dict[str, Any]]] = None

    date_entered: Optional[date] = None
    date_ceased: Optional[date] = None
    notes: Optional[str] = None


class ShareholderCreate(ShareholderBase):
    pass


class ShareholderUpdate(_AppendixAMixin):
    identification_type: Optional[ShareholderType] = None
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    corporate_number: Optional[str] = None
    country_of_incorporation: Optional[str] = None
    entity_details: Optional[dict[str, Any]] = None
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
    nominator_name: Optional[str] = None
    nominator_address: Optional[str] = None
    nominator_relationship: Optional[str] = None
    nominee_agreement_date: Optional[date] = None
    charges: Optional[list[dict[str, Any]]] = None
    date_entered: Optional[date] = None
    date_ceased: Optional[date] = None
    notes: Optional[str] = None


class ShareholderRead(ShareholderBase):
    id: int
    case_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ─── UBO ─────────────────────────────────────────────────────────────────
class UBOBase(BaseModel):
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    former_name: Optional[str] = None

    date_of_birth: Optional[date] = None
    place_of_birth: Optional[str] = None
    nationality: Optional[str] = None
    country_of_residence: Optional[str] = None
    passport_number: Optional[str] = None
    passport_expiry: Optional[date] = None
    national_id: Optional[str] = None

    residential_address: Optional[str] = None
    residential_city: Optional[str] = None
    residential_country: Optional[str] = None
    email: Optional[str] = None
    mobile: Optional[str] = None

    percentage_interest: Optional[Decimal] = Field(None, ge=0, le=100)
    ownership_nature: OwnershipNature = OwnershipNature.DIRECT
    nature_of_control: Optional[str] = None
    held_via_shareholder_id: Optional[int] = None

    is_pep: bool = False
    pep_notes: Optional[str] = None

    employer_name: Optional[str] = None
    job_title: Optional[str] = None
    sector: Optional[str] = None
    years_employed: Optional[str] = None

    source_of_wealth_category: Optional[SourceOfWealthCategory] = None
    source_of_wealth_details: Optional[str] = None

    appointment_date: Optional[date] = None
    cessation_date: Optional[date] = None
    notes: Optional[str] = None


class UBOCreate(UBOBase):
    pass


class UBOUpdate(BaseModel):
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    former_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    place_of_birth: Optional[str] = None
    nationality: Optional[str] = None
    country_of_residence: Optional[str] = None
    passport_number: Optional[str] = None
    passport_expiry: Optional[date] = None
    national_id: Optional[str] = None
    residential_address: Optional[str] = None
    residential_city: Optional[str] = None
    residential_country: Optional[str] = None
    email: Optional[str] = None
    mobile: Optional[str] = None
    percentage_interest: Optional[Decimal] = Field(None, ge=0, le=100)
    ownership_nature: Optional[OwnershipNature] = None
    nature_of_control: Optional[str] = None
    held_via_shareholder_id: Optional[int] = None
    is_pep: Optional[bool] = None
    pep_notes: Optional[str] = None
    employer_name: Optional[str] = None
    job_title: Optional[str] = None
    sector: Optional[str] = None
    years_employed: Optional[str] = None
    source_of_wealth_category: Optional[SourceOfWealthCategory] = None
    source_of_wealth_details: Optional[str] = None
    appointment_date: Optional[date] = None
    cessation_date: Optional[date] = None
    notes: Optional[str] = None


class UBORead(UBOBase):
    id: int
    case_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
