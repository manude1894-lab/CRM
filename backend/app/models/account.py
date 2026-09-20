"""SQLAlchemy model: Account (client company)."""
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Numeric, Boolean, JSON, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class Priority(str, enum.Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    account_uid = Column(String(20), unique=True, index=True, nullable=False)  # ACC-0001

    account_type = Column(String(20), default="Corporate", nullable=False)  # Corporate / Individual

    company_name = Column(String(255), unique=True, nullable=False, index=True)  # full legal name, for Individuals too
    industry = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    company_size = Column(String(100), nullable=True)
    website = Column(String(255), nullable=True)

    strategic_priority = Column(SAEnum(Priority, name="priority", values_callable=lambda obj: [e.value for e in obj]), default=Priority.MEDIUM, nullable=False)
    existing_relationship = Column(String(10), default="No", nullable=False)
    key_contacts = Column(Text, nullable=True)
    tags = Column(String(500), nullable=True)

    # Compliance & risk — client-level (distinct from the per-case CDDRecord.aml_risk_rating)
    registration_number = Column(String(100), nullable=True)
    license_number = Column(String(100), nullable=True)
    risk_rating = Column(String(20), nullable=True)  # Low / Medium / High
    kyc_status = Column(String(30), default="Not Started", nullable=False)  # Not Started / Submitted / Under Review / Approved / Rejected

    # Licensing & regulatory (client-database spec §6.1-7.6)
    licensing_authority = Column(String(150), nullable=True)
    license_start_date = Column(Date, nullable=True)
    license_expiry_date = Column(Date, nullable=True)
    is_regulated = Column(Boolean, default=False, nullable=False)
    regulator_name = Column(String(50), nullable=True)  # DFSA / FSRA / CMA / UAECB / Other
    regulator_other = Column(String(100), nullable=True)
    license_category = Column(String(100), nullable=True)
    license_activities = Column(Text, nullable=True)

    # Addresses (§8.1/8.2) — {line1, line2, landmark, zip, po_box, city, country}
    registered_address = Column(JSON, nullable=True)
    operating_address = Column(JSON, nullable=True)

    # Tax (§9-10.1)
    trn_vat_number = Column(String(30), nullable=True)
    corp_tax_registered = Column(Boolean, default=False, nullable=False)
    corp_tax_registration_number = Column(String(30), nullable=True)

    financial_year_end = Column(String(5), nullable=True)  # "MM-DD"

    # Introducer (§12-13)
    has_introducer = Column(Boolean, default=False, nullable=False)
    introducer_name = Column(String(255), nullable=True)

    services_obtained = Column(JSON, nullable=True)  # list[str]

    # Profile status workflow (§25)
    profile_status = Column(String(30), default="New", nullable=False)

    # Engagement Letter — client-level (§26-27), distinct from Case's onboarding-pipeline dates
    engagement_letter_signed = Column(Boolean, default=False, nullable=False)
    engagement_letter_valid_until = Column(Date, nullable=True)

    # AML classification (§24.1, 24.3, 24.5-24.6) — distinct from risk_rating (High/Med/Low)
    aml_classification = Column(String(20), nullable=True)  # Standard / SDD / EDD
    edd_reason = Column(String(255), nullable=True)
    cdd_completion_date = Column(Date, nullable=True)
    next_aml_review_date = Column(Date, nullable=True)  # server-computed from risk_rating + cdd_completion_date

    # For Corporate accounts this is a server-computed rollup (any account_parties row is_pep=True).
    # For Individual accounts (no parties) it is directly user-editable — see account_service.
    is_pep = Column(Boolean, default=False, nullable=False)

    # Individual Details (Phase C) — populated only when account_type == "Individual"
    date_of_birth = Column(Date, nullable=True)
    nationality = Column(String(120), nullable=True)
    passport_number = Column(String(50), nullable=True)
    passport_expiry_date = Column(Date, nullable=True)
    occupation = Column(String(150), nullable=True)
    source_of_funds = Column(String(255), nullable=True)
    source_of_wealth = Column(String(255), nullable=True)
    country_of_residence = Column(String(120), nullable=True)
    residential_address = Column(JSON, nullable=True)  # AddressBlock shape, reused from Phase A
    individual_mobile = Column(String(50), nullable=True)
    individual_email = Column(String(255), nullable=True)
    uae_visa_number = Column(String(50), nullable=True)
    uae_visa_expiry = Column(Date, nullable=True)

    # Computed / denormalized
    total_cases = Column(Integer, default=0, nullable=False)
    total_invoiced_amount = Column(Numeric(14, 2), default=0, nullable=False)

    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # Single Point of Contact — the staff member who manages this client's section.
    spoc_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    owner = relationship("User", back_populates="accounts", foreign_keys=[owner_id])
    spoc = relationship("User", foreign_keys=[spoc_id])
    cases = relationship("Case", back_populates="account")
    parties = relationship("AccountParty", back_populates="account", cascade="all, delete-orphan")
