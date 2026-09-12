"""SQLAlchemy model: CompanyProfile — formation / statutory detail for a Case.

1:1 with Case (same pattern as CDDRecord / ComplianceSchedule). Holds the fields
from Vistra KYC Part I + the BVI Data Input Sheet that the CRM previously dropped:
proposed names + availability check, registered agent, incorporation date, share
capital, source of funds, nature of business, company secretary, the ES + accounting
financial year-ends (which anchor the compliance calendar), and the activation
documents received on incorporation.

Enum-like fields are stored as plain String columns — same precedent as
Case.jurisdiction / Case.service_type (migration 0003).
"""
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Boolean, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class RegisteredAgent(str, enum.Enum):
    VISTRA = "Vistra"
    ILS_FIDUCIARY = "ILS Fiduciary"
    PATTON_MORENO_ASVAT = "Patton, Moreno & Asvat"
    ROSEMONT = "Rosemont"
    OTHER = "Other"


class NameCheckStatus(str, enum.Enum):
    NOT_SUBMITTED = "Not Submitted"
    SUBMITTED = "Submitted to Vistra"
    CONFIRMED = "Name Confirmed"
    REJECTED = "Rejected"


class SourceOfFunds(str, enum.Enum):
    SHAREHOLDER = "Shareholder"
    UBO = "Ultimate Beneficial Owner"
    CAPITAL_INJECTION = "Capital injection"
    LOAN = "Loan"
    THIRD_PARTY = "Third party"


class NatureOfBusiness(str, enum.Enum):
    IHV_REAL_ESTATE = "Investment holding - real estate"
    IHV_FINANCIAL = "Investment holding - financial assets"
    IHV_OTHER_ASSETS = "Investment holding - other assets"
    TRADING = "Services or product trading"
    OTHER = "Other"


class CompanySecretary(str, enum.Enum):
    NONE = "None"
    VISTRA = "Vistra entity"
    SAME_AS_DIRECTOR = "Same as a director"
    SAME_AS_UBO = "Same as the UBO"
    INDIVIDUAL = "Individual (third party)"
    CORPORATE = "Corporate (third party)"


class CompanyProfile(Base):
    __tablename__ = "company_profiles"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), unique=True, nullable=False)

    chinese_name = Column(String(255), nullable=True)
    company_number = Column(String(100), nullable=True)
    registered_agent = Column(String(50), nullable=True)
    incorporation_date = Column(Date, nullable=True)
    # Entity category is orthogonal to Jurisdiction — e.g. "Foundation" can exist in
    # several jurisdictions; "ADGM/DIFC Regulated" carries its own filing obligations.
    entity_category = Column(String(60), nullable=True)
    regulator = Column(String(60), nullable=True)  # e.g. "DFSA", "FSRA" — free text

    proposed_name_1 = Column(String(255), nullable=True)
    proposed_name_2 = Column(String(255), nullable=True)
    proposed_name_3 = Column(String(255), nullable=True)
    name_check_status = Column(String(30), default=NameCheckStatus.NOT_SUBMITTED.value, nullable=False)
    name_confirmed_date = Column(Date, nullable=True)

    authorised_shares = Column(Integer, nullable=True)
    par_value = Column(Numeric(12, 4), nullable=True)
    share_currency = Column(String(10), default="USD", nullable=True)
    no_par_value = Column(Boolean, default=False, nullable=False)

    source_of_funds = Column(String(50), nullable=True)
    source_of_funds_description = Column(Text, nullable=True)
    nature_of_business = Column(String(60), nullable=True)
    business_description = Column(Text, nullable=True)
    # Nature-of-business detail (Vistra KYC Part I)
    business_countries = Column(Text, nullable=True)
    key_counterparties = Column(Text, nullable=True)
    asset_types = Column(Text, nullable=True)
    expected_annual_turnover = Column(String(60), nullable=True)
    expected_active_transactions = Column(String(60), nullable=True)
    company_secretary = Column(String(40), nullable=True)

    # "MM-DD" — e.g. "12-31". Anchors the compliance calendar.
    es_financial_year_end = Column(String(5), nullable=True)
    accounting_financial_year_end = Column(String(5), nullable=True)

    act_certificate_of_incorporation = Column(Boolean, default=False, nullable=False)
    act_memorandum_articles = Column(Boolean, default=False, nullable=False)
    act_register_of_members = Column(Boolean, default=False, nullable=False)
    act_register_of_directors_stamped = Column(Boolean, default=False, nullable=False)
    act_company_stamp = Column(Boolean, default=False, nullable=False)
    activation_docs_received_date = Column(Date, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    case = relationship("Case", back_populates="company_profile")
