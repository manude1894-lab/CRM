"""Pydantic schemas: Account."""
import re

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

from app.models.account import Priority


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_FYE_RE = re.compile(r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")


class _ClientFieldRules(BaseModel):
    """BRD §5/§9/§10 field formats, shared by create and update so they can't drift apart.

    Formats only — whether a field is *mandatory* is checked by account_service.missing_mandatory()
    at Submit (BRD §12 step 11), because each section is saved on its own before the profile is complete.
    """

    @field_validator("trn_vat_number", "corp_tax_registration_number", mode="before", check_fields=False)
    @classmethod
    def _numeric_15(cls, v):
        if v in (None, ""):
            return v
        v = str(v).strip()
        if not v.isdigit():
            raise ValueError("must contain digits only")
        return v

    @field_validator("individual_email", mode="before", check_fields=False)
    @classmethod
    def _email(cls, v):
        if v in (None, ""):
            return v
        v = str(v).strip()
        if not _EMAIL_RE.match(v):
            raise ValueError("is not a valid email address")
        return v

    @field_validator("financial_year_end", mode="before", check_fields=False)
    @classmethod
    def _fye(cls, v):
        # Stored as MM-DD (sorts and compares cleanly); displayed as DD-MMM per BRD §14.
        if v in (None, ""):
            return v
        v = str(v).strip()
        if not _FYE_RE.match(v):
            raise ValueError("must be a month and day (MM-DD)")
        return v

    @field_validator("search_name", mode="before", check_fields=False)
    @classmethod
    def _search_name(cls, v):
        if v is None:
            return v
        v = " ".join(str(v).split())
        return v or None


class AddressBlock(BaseModel):
    line1: Optional[str] = None
    line2: Optional[str] = None
    landmark: Optional[str] = None
    zip: Optional[str] = None
    po_box: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None


class AccountImportRow(BaseModel):
    account_type: Optional[str] = None
    search_name: Optional[str] = Field(None, max_length=120)
    company_name: str = Field(..., min_length=1, max_length=255)
    industry: Optional[str] = None
    country: Optional[str] = None
    company_size: Optional[str] = None
    website: Optional[str] = None
    strategic_priority: Optional[str] = None
    existing_relationship: Optional[str] = None
    key_contacts: Optional[str] = None
    tags: Optional[str] = None
    single_point_of_contact: Optional[str] = None
    anchor_entity: Optional[str] = None
    non_anchor_entities: Optional[list[str]] = None
    registration_number: Optional[str] = Field(None, max_length=30)
    incorporation_date: Optional[date] = None
    license_number: Optional[str] = None
    risk_rating: Optional[str] = None
    kyc_status: Optional[str] = None
    spoc_id: Optional[int] = None
    non_anchor_rm_ids: Optional[list[int]] = None

    licensing_authority: Optional[str] = None
    license_start_date: Optional[date] = None
    license_expiry_date: Optional[date] = None
    regulatory_license_expiry_date: Optional[date] = None
    is_regulated: Optional[bool] = None
    regulator_name: Optional[str] = None
    regulator_other: Optional[str] = None
    license_category: Optional[str] = None
    license_activities: Optional[str] = None

    registered_address: Optional[AddressBlock] = None
    operating_address: Optional[AddressBlock] = None

    trn_vat_number: Optional[str] = Field(None, max_length=15)
    corp_tax_registered: Optional[bool] = None
    corp_tax_registration_number: Optional[str] = Field(None, max_length=15)

    financial_year_end: Optional[str] = None

    has_introducer: Optional[bool] = None
    introducer_name: Optional[str] = None

    services_obtained: Optional[list[str]] = None

    profile_status: Optional[str] = None

    engagement_letter_signed: Optional[bool] = None
    engagement_letter_valid_until: Optional[date] = None

    aml_classification: Optional[str] = None
    edd_reason: Optional[str] = Field(None, max_length=25)
    cdd_completion_date: Optional[date] = None

    date_of_birth: Optional[date] = None
    country_of_birth: Optional[str] = None
    nationality: Optional[str] = None
    passport_number: Optional[str] = None
    passport_expiry_date: Optional[date] = None
    occupation: Optional[str] = None
    source_of_funds: Optional[str] = None
    source_of_wealth: Optional[str] = None
    country_of_residence: Optional[str] = None
    residential_address: Optional[AddressBlock] = None
    individual_mobile: Optional[str] = None
    individual_mobile_country_code: Optional[str] = None
    individual_mobile_number: Optional[str] = Field(None, max_length=12)
    individual_email: Optional[str] = None
    uae_visa_number: Optional[str] = None
    uae_visa_expiry: Optional[date] = None
    nature_of_services_sought: Optional[list[str]] = None


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


class AccountBase(_ClientFieldRules):
    account_type: str = "Corporate"  # Corporate / Individual
    search_name: Optional[str] = Field(None, max_length=120)
    licensing_authority_other: Optional[str] = Field(None, max_length=100)
    kyc_verified_by: Optional[str] = Field(None, max_length=150)
    company_name: str = Field(..., min_length=1, max_length=255)
    industry: Optional[str] = None
    country: Optional[str] = None
    company_size: Optional[str] = None
    website: Optional[str] = None
    strategic_priority: Priority = Priority.MEDIUM
    existing_relationship: str = "No"
    key_contacts: Optional[str] = None
    tags: Optional[str] = None
    single_point_of_contact: Optional[str] = None
    anchor_entity: Optional[str] = None
    non_anchor_entities: Optional[list[str]] = None
    registration_number: Optional[str] = Field(None, max_length=30)
    incorporation_date: Optional[date] = None
    license_number: Optional[str] = Field(None, max_length=30)
    risk_rating: Optional[str] = None
    kyc_status: str = "Not Started"
    owner_id: Optional[int] = None
    spoc_id: Optional[int] = None
    non_anchor_rm_ids: Optional[list[int]] = None

    licensing_authority: Optional[str] = None
    license_start_date: Optional[date] = None
    license_expiry_date: Optional[date] = None
    regulatory_license_expiry_date: Optional[date] = None
    is_regulated: Optional[bool] = None
    regulator_name: Optional[str] = None
    regulator_other: Optional[str] = Field(None, max_length=100)
    license_category: Optional[str] = Field(None, max_length=25)
    license_activities: Optional[str] = Field(None, max_length=250)

    registered_address: Optional[AddressBlock] = None
    operating_address: Optional[AddressBlock] = None

    trn_vat_number: Optional[str] = Field(None, max_length=15)
    corp_tax_registered: Optional[bool] = None
    corp_tax_registration_number: Optional[str] = Field(None, max_length=15)

    financial_year_end: Optional[str] = None

    has_introducer: Optional[bool] = None
    introducer_name: Optional[str] = None

    services_obtained: Optional[list[str]] = None

    profile_status: str = "New"

    engagement_letter_signed: bool = False
    engagement_letter_valid_until: Optional[date] = None

    aml_classification: Optional[str] = None
    edd_reason: Optional[str] = Field(None, max_length=25)
    cdd_completion_date: Optional[date] = None

    is_pep: Optional[bool] = None  # direct-editable only for Individual accounts (no parties to roll up from)

    # Individual Details (Phase C)
    date_of_birth: Optional[date] = None
    country_of_birth: Optional[str] = None
    nationality: Optional[str] = None
    passport_number: Optional[str] = None
    passport_expiry_date: Optional[date] = None
    occupation: Optional[str] = None
    source_of_funds: Optional[str] = None
    source_of_wealth: Optional[str] = None
    country_of_residence: Optional[str] = None
    residential_address: Optional[AddressBlock] = None
    individual_mobile: Optional[str] = None
    individual_mobile_country_code: Optional[str] = None
    individual_mobile_number: Optional[str] = Field(None, max_length=12)
    individual_email: Optional[str] = None
    uae_visa_number: Optional[str] = None
    uae_visa_expiry: Optional[date] = None
    nature_of_services_sought: Optional[list[str]] = None


class AccountCreate(AccountBase):
    prospect_id: Optional[int] = None  # Triam mark-up §4A — the prospect this client is created from
    # BRD §3 duplicate exception — only honoured for users with client.approve.
    allow_duplicate: bool = False
    duplicate_reason: Optional[str] = Field(None, max_length=255)


class AccountUpdate(_ClientFieldRules):
    account_type: Optional[str] = None
    search_name: Optional[str] = Field(None, max_length=120)
    licensing_authority_other: Optional[str] = Field(None, max_length=100)
    kyc_verified_by: Optional[str] = Field(None, max_length=150)
    company_name: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    company_size: Optional[str] = None
    website: Optional[str] = None
    strategic_priority: Optional[Priority] = None
    existing_relationship: Optional[str] = None
    key_contacts: Optional[str] = None
    tags: Optional[str] = None
    single_point_of_contact: Optional[str] = None
    anchor_entity: Optional[str] = None
    non_anchor_entities: Optional[list[str]] = None
    registration_number: Optional[str] = Field(None, max_length=30)
    incorporation_date: Optional[date] = None
    license_number: Optional[str] = Field(None, max_length=30)
    risk_rating: Optional[str] = None
    kyc_status: Optional[str] = None
    owner_id: Optional[int] = None
    spoc_id: Optional[int] = None
    non_anchor_rm_ids: Optional[list[int]] = None

    licensing_authority: Optional[str] = None
    license_start_date: Optional[date] = None
    license_expiry_date: Optional[date] = None
    regulatory_license_expiry_date: Optional[date] = None
    is_regulated: Optional[bool] = None
    regulator_name: Optional[str] = None
    regulator_other: Optional[str] = Field(None, max_length=100)
    license_category: Optional[str] = Field(None, max_length=25)
    license_activities: Optional[str] = Field(None, max_length=250)

    registered_address: Optional[AddressBlock] = None
    operating_address: Optional[AddressBlock] = None

    trn_vat_number: Optional[str] = Field(None, max_length=15)
    corp_tax_registered: Optional[bool] = None
    corp_tax_registration_number: Optional[str] = Field(None, max_length=15)

    financial_year_end: Optional[str] = None

    has_introducer: Optional[bool] = None
    introducer_name: Optional[str] = None

    services_obtained: Optional[list[str]] = None

    profile_status: Optional[str] = None

    engagement_letter_signed: Optional[bool] = None
    engagement_letter_valid_until: Optional[date] = None

    aml_classification: Optional[str] = None
    edd_reason: Optional[str] = Field(None, max_length=25)
    cdd_completion_date: Optional[date] = None

    is_pep: Optional[bool] = None

    date_of_birth: Optional[date] = None
    country_of_birth: Optional[str] = None
    nationality: Optional[str] = None
    passport_number: Optional[str] = None
    passport_expiry_date: Optional[date] = None
    occupation: Optional[str] = None
    source_of_funds: Optional[str] = None
    source_of_wealth: Optional[str] = None
    country_of_residence: Optional[str] = None
    residential_address: Optional[AddressBlock] = None
    individual_mobile: Optional[str] = None
    individual_mobile_country_code: Optional[str] = None
    individual_mobile_number: Optional[str] = Field(None, max_length=12)
    individual_email: Optional[str] = None
    uae_visa_number: Optional[str] = None
    uae_visa_expiry: Optional[date] = None
    nature_of_services_sought: Optional[list[str]] = None


class AccountRead(AccountBase):
    id: int
    account_uid: str
    client_id: Optional[str] = None
    temp_id: Optional[str] = None
    prospect_id: Optional[int] = None
    status_updated_at: Optional[datetime] = None
    status_updated_by_id: Optional[int] = None
    duplicate_override_reason: Optional[str] = None
    total_cases: int
    total_invoiced_amount: Decimal
    next_aml_review_date: Optional[date] = None
    is_pep: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
