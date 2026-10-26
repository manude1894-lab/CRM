"""SQLAlchemy model: Account — a Triam client, Corporate or Individual (BRD §3–§9)."""
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    account_uid = Column(String(20), unique=True, index=True, nullable=False)  # ACC-0001 — internal key
    # BRD §18 Unique Client ID — {ENTITY}/{00000}, per-entity counter, issued at Compliance approval.
    client_id = Column(String(20), unique=True, index=True, nullable=True)
    # BRD §3 Unique Search Name — short, unique (case-insensitive), prefilled from the legal name.
    search_name = Column(String(120), unique=True, index=True, nullable=True)

    account_type = Column(String(20), default="Corporate", nullable=False)  # Corporate / Individual

    # Full legal name (also for Individuals). Not unique since BRD §3: duplicates are blocked in the
    # service unless an approver records an exception (duplicate_override_reason).
    company_name = Column(String(255), nullable=False, index=True)
    duplicate_override_reason = Column(String(255), nullable=True)
    country = Column(String(100), nullable=True)  # country of incorporation / registration

    tags = Column(String(500), nullable=True)
    single_point_of_contact = Column(String(255), nullable=True)  # client-side contact, free text (BRD §22 item 9)

    # Triam entities (BRD §4)
    anchor_entity = Column(String(10), nullable=True)  # triam_entity master list
    non_anchor_entities = Column(JSON, nullable=True)  # list[str], excludes the anchor entity

    # Corporate profile (BRD §5)
    registration_number = Column(String(100), nullable=True)  # Incorporation Certificate No.
    incorporation_date = Column(Date, nullable=True)
    license_number = Column(String(100), nullable=True)
    licensing_authority = Column(String(150), nullable=True)
    licensing_authority_other = Column(String(100), nullable=True)  # free text when "Other"
    license_start_date = Column(Date, nullable=True)
    license_expiry_date = Column(Date, nullable=True)
    regulatory_license_expiry_date = Column(Date, nullable=True)  # mandatory when regulated
    # Mandatory Yes/No: None = not answered yet (required before submission).
    is_regulated = Column(Boolean, nullable=True)
    regulator_name = Column(String(50), nullable=True)  # DFSA / FSRA / CMA / UAECB / Other
    regulator_other = Column(String(100), nullable=True)
    license_category = Column(String(100), nullable=True)
    license_activities = Column(Text, nullable=True)

    # Addresses — {line1, line2, landmark, zip, po_box, city, country}
    registered_address = Column(JSON, nullable=True)
    operating_address = Column(JSON, nullable=True)

    trn_vat_number = Column(String(30), nullable=True)
    corp_tax_registered = Column(Boolean, nullable=True)
    corp_tax_registration_number = Column(String(30), nullable=True)
    financial_year_end = Column(String(5), nullable=True)  # "MM-DD", shown as DD-MMM

    has_introducer = Column(Boolean, nullable=True)
    introducer_name = Column(String(255), nullable=True)

    services_obtained = Column(JSON, nullable=True)  # list[str], service master list (BRD §4)

    # Status (BRD §9)
    profile_status = Column(String(30), default="New", nullable=False)
    # "Status last updated on" — set by the service whenever profile_status changes.
    status_updated_at = Column(DateTime(timezone=True), nullable=True)
    status_updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Engagement Letter (BRD §9): mandatory Yes / No — None = not answered
    engagement_letter_signed = Column(Boolean, nullable=True)
    engagement_letter_valid_until = Column(Date, nullable=True)

    # Customer risk assessment / KYC & AML (BRD §8) — completed by Compliance (MLRO)
    risk_rating = Column(String(20), nullable=True)  # CDD/AML risk level: High / Medium / Low
    aml_classification = Column(String(20), nullable=True)  # AML risk level: Standard / SDD / EDD
    edd_reason = Column(String(255), nullable=True)
    cdd_completion_date = Column(Date, nullable=True)
    kyc_verified_by = Column(String(150), nullable=True)  # full name of the RM who verified KYC
    next_aml_review_date = Column(Date, nullable=True)  # server-computed from risk_rating + cdd_completion_date

    # Corporate: computed from the parties (any party is a PEP). Individual: entered directly.
    is_pep = Column(Boolean, default=False, nullable=False)

    # Individual client (BRD §6)
    date_of_birth = Column(Date, nullable=True)
    country_of_birth = Column(String(120), nullable=True)
    nationality = Column(String(120), nullable=True)
    passport_expiry_date = Column(Date, nullable=True)
    country_of_residence = Column(String(120), nullable=True)
    residential_address = Column(JSON, nullable=True)  # same shape as the corporate addresses
    individual_mobile_country_code = Column(String(6), nullable=True)
    individual_mobile_number = Column(String(12), nullable=True)
    individual_email = Column(String(255), nullable=True)
    uae_visa_number = Column(String(50), nullable=True)
    uae_visa_expiry = Column(Date, nullable=True)

    client_category = Column(String(20), nullable=True)  # "Under Formation" | "Existing" (BRD §5)
    contact_mobile_country_code = Column(String(6), nullable=True)  # company contact
    contact_mobile_number = Column(String(12), nullable=True)
    contact_email = Column(String(255), nullable=True)
    nature_of_business = Column(Text, nullable=True)  # detailed nature of business / profession
    lei_number = Column(String(20), nullable=True)
    lei_expiry_date = Column(Date, nullable=True)
    is_one_time_service = Column(Boolean, nullable=True)
    nature_of_services_sought = Column(JSON, nullable=True)  # list[str]
    # Biz Rationale Report (Triam UAT 26-10-2026): the RM's meeting with the client and why Triam takes it on.
    br_person_met = Column(String(255), nullable=True)
    br_meeting_date = Column(Date, nullable=True)
    br_meeting_time = Column(String(5), nullable=True)  # HH:MM
    br_meeting_place = Column(String(255), nullable=True)
    br_meeting_mode = Column(String(20), nullable=True)  # Face to Face / Video Call
    br_rationale = Column(Text, nullable=True)

    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # who created the client
    prospect_id = Column(Integer, ForeignKey("prospects.id", ondelete="SET NULL"), nullable=True)  # BRD §4A
    # Anchor RM — the staff member who owns this client; drives RM-scoped access (access_control.py).
    spoc_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    non_anchor_rm_ids = Column(JSON, nullable=True)  # list[int] of User ids, excludes spoc_id

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    owner = relationship("User", back_populates="accounts", foreign_keys=[owner_id])
    spoc = relationship("User", foreign_keys=[spoc_id])
    prospect = relationship("Prospect", foreign_keys=[prospect_id])

    @property
    def temp_id(self):
        """Shown until the Client ID is issued at Compliance approval: the Prospect ID the client came
        from, or the internal record number for clients loaded by import."""
        return self.prospect.prospect_uid if self.prospect is not None else self.account_uid

    # Current parties only; removed ones stay in the table (removed_at set) and are listed by removed_parties.
    parties = relationship("AccountParty", primaryjoin="and_(Account.id == AccountParty.account_id, AccountParty.removed_at.is_(None))",
                           cascade="all, delete-orphan", order_by="AccountParty.id", overlaps="removed_parties")
    removed_parties = relationship("AccountParty", primaryjoin="and_(Account.id == AccountParty.account_id, AccountParty.removed_at.isnot(None))",
                                   viewonly=True, order_by="AccountParty.removed_at")
    documents = relationship("Document", back_populates="account", cascade="all, delete-orphan")
