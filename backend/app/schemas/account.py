"""Pydantic schemas: Account."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

from app.models.account import Priority


class AddressBlock(BaseModel):
    line1: Optional[str] = None
    line2: Optional[str] = None
    landmark: Optional[str] = None
    zip: Optional[str] = None
    po_box: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None


class AccountImportRow(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    industry: Optional[str] = None
    country: Optional[str] = None
    company_size: Optional[str] = None
    website: Optional[str] = None
    strategic_priority: Optional[str] = None
    existing_relationship: Optional[str] = None
    key_contacts: Optional[str] = None
    tags: Optional[str] = None
    registration_number: Optional[str] = None
    license_number: Optional[str] = None
    risk_rating: Optional[str] = None
    kyc_status: Optional[str] = None


class DuplicateMatch(BaseModel):
    id: int
    company_name: str
    score: int


class AccountBulkUpdateRequest(BaseModel):
    ids: list[int] = Field(..., min_length=1)
    spoc_id: Optional[int] = None
    risk_rating: Optional[str] = None
    kyc_status: Optional[str] = None


class BulkUpdateResult(BaseModel):
    id: int
    status: str  # "ok" | "error"
    message: Optional[str] = None


class AccountImportRequest(BaseModel):
    rows: list[AccountImportRow]
    dry_run: bool = True


class AccountImportRowResult(BaseModel):
    row_index: int
    company_name: str
    status: str  # "ok" | "duplicate" | "error"
    message: Optional[str] = None
    account_id: Optional[int] = None


class AccountImportResponse(BaseModel):
    dry_run: bool
    created: int
    skipped: int
    results: list[AccountImportRowResult]


class AccountBase(BaseModel):
    account_type: str = "Corporate"  # Corporate / Individual
    company_name: str = Field(..., min_length=1, max_length=255)
    industry: Optional[str] = None
    country: Optional[str] = None
    company_size: Optional[str] = None
    website: Optional[str] = None
    strategic_priority: Priority = Priority.MEDIUM
    existing_relationship: str = "No"
    key_contacts: Optional[str] = None
    tags: Optional[str] = None
    registration_number: Optional[str] = None
    license_number: Optional[str] = None
    risk_rating: Optional[str] = None
    kyc_status: str = "Not Started"
    owner_id: Optional[int] = None
    spoc_id: Optional[int] = None

    licensing_authority: Optional[str] = None
    license_start_date: Optional[date] = None
    license_expiry_date: Optional[date] = None
    is_regulated: bool = False
    regulator_name: Optional[str] = None
    regulator_other: Optional[str] = None
    license_category: Optional[str] = None
    license_activities: Optional[str] = None

    registered_address: Optional[AddressBlock] = None
    operating_address: Optional[AddressBlock] = None

    trn_vat_number: Optional[str] = None
    corp_tax_registered: bool = False
    corp_tax_registration_number: Optional[str] = None

    financial_year_end: Optional[str] = None

    has_introducer: bool = False
    introducer_name: Optional[str] = None

    services_obtained: Optional[list[str]] = None

    profile_status: str = "New"

    engagement_letter_signed: bool = False
    engagement_letter_valid_until: Optional[date] = None

    aml_classification: Optional[str] = None
    edd_reason: Optional[str] = None
    cdd_completion_date: Optional[date] = None

    is_pep: Optional[bool] = None  # direct-editable only for Individual accounts (no parties to roll up from)

    # Individual Details (Phase C)
    date_of_birth: Optional[date] = None
    nationality: Optional[str] = None
    passport_number: Optional[str] = None
    passport_expiry_date: Optional[date] = None
    occupation: Optional[str] = None
    source_of_funds: Optional[str] = None
    source_of_wealth: Optional[str] = None
    country_of_residence: Optional[str] = None
    residential_address: Optional[AddressBlock] = None
    individual_mobile: Optional[str] = None
    individual_email: Optional[str] = None
    uae_visa_number: Optional[str] = None
    uae_visa_expiry: Optional[date] = None


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    account_type: Optional[str] = None
    company_name: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    company_size: Optional[str] = None
    website: Optional[str] = None
    strategic_priority: Optional[Priority] = None
    existing_relationship: Optional[str] = None
    key_contacts: Optional[str] = None
    tags: Optional[str] = None
    registration_number: Optional[str] = None
    license_number: Optional[str] = None
    risk_rating: Optional[str] = None
    kyc_status: Optional[str] = None
    owner_id: Optional[int] = None
    spoc_id: Optional[int] = None

    licensing_authority: Optional[str] = None
    license_start_date: Optional[date] = None
    license_expiry_date: Optional[date] = None
    is_regulated: Optional[bool] = None
    regulator_name: Optional[str] = None
    regulator_other: Optional[str] = None
    license_category: Optional[str] = None
    license_activities: Optional[str] = None

    registered_address: Optional[AddressBlock] = None
    operating_address: Optional[AddressBlock] = None

    trn_vat_number: Optional[str] = None
    corp_tax_registered: Optional[bool] = None
    corp_tax_registration_number: Optional[str] = None

    financial_year_end: Optional[str] = None

    has_introducer: Optional[bool] = None
    introducer_name: Optional[str] = None

    services_obtained: Optional[list[str]] = None

    profile_status: Optional[str] = None

    engagement_letter_signed: Optional[bool] = None
    engagement_letter_valid_until: Optional[date] = None

    aml_classification: Optional[str] = None
    edd_reason: Optional[str] = None
    cdd_completion_date: Optional[date] = None

    is_pep: Optional[bool] = None

    date_of_birth: Optional[date] = None
    nationality: Optional[str] = None
    passport_number: Optional[str] = None
    passport_expiry_date: Optional[date] = None
    occupation: Optional[str] = None
    source_of_funds: Optional[str] = None
    source_of_wealth: Optional[str] = None
    country_of_residence: Optional[str] = None
    residential_address: Optional[AddressBlock] = None
    individual_mobile: Optional[str] = None
    individual_email: Optional[str] = None
    uae_visa_number: Optional[str] = None
    uae_visa_expiry: Optional[date] = None


class AccountRead(AccountBase):
    id: int
    account_uid: str
    total_cases: int
    total_invoiced_amount: Decimal
    next_aml_review_date: Optional[date] = None
    is_pep: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
