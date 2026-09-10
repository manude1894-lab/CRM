"""Pydantic schemas: CompanyProfile (formation / statutory detail)."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

from app.models.company_profile import (
    RegisteredAgent, NameCheckStatus, SourceOfFunds, NatureOfBusiness, CompanySecretary,
)

_MMDD = r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$"


class CompanyProfileBase(BaseModel):
    chinese_name: Optional[str] = None
    company_number: Optional[str] = None
    registered_agent: Optional[RegisteredAgent] = None
    incorporation_date: Optional[date] = None

    proposed_name_1: Optional[str] = None
    proposed_name_2: Optional[str] = None
    proposed_name_3: Optional[str] = None
    name_check_status: Optional[NameCheckStatus] = None
    name_confirmed_date: Optional[date] = None

    authorised_shares: Optional[int] = Field(None, ge=0)
    par_value: Optional[Decimal] = Field(None, ge=0)
    share_currency: Optional[str] = None
    no_par_value: Optional[bool] = None

    source_of_funds: Optional[SourceOfFunds] = None
    source_of_funds_description: Optional[str] = None
    nature_of_business: Optional[NatureOfBusiness] = None
    business_description: Optional[str] = None
    business_countries: Optional[str] = None
    key_counterparties: Optional[str] = None
    asset_types: Optional[str] = None
    expected_annual_turnover: Optional[str] = None
    expected_active_transactions: Optional[str] = None
    company_secretary: Optional[CompanySecretary] = None

    es_financial_year_end: Optional[str] = Field(None, pattern=_MMDD)
    accounting_financial_year_end: Optional[str] = Field(None, pattern=_MMDD)

    act_certificate_of_incorporation: Optional[bool] = None
    act_memorandum_articles: Optional[bool] = None
    act_register_of_members: Optional[bool] = None
    act_register_of_directors_stamped: Optional[bool] = None
    act_company_stamp: Optional[bool] = None
    activation_docs_received_date: Optional[date] = None


class CompanyProfileUpdate(CompanyProfileBase):
    pass


class CompanyProfileRead(CompanyProfileBase):
    id: int
    case_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
