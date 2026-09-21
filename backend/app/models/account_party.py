"""SQLAlchemy model: AccountParty — Shareholders, Directors, and Authorised
Signatories captured on the Client itself (client-database spec §14/21/22),
as distinct from the per-Case Director/Shareholder/UBO registers in party.py.

One discriminated table rather than three near-duplicate ones: the spec's
three sections overlap heavily and differ only in a couple of role-specific
fields (ownership % for Shareholders, nominee-director name for Directors).
"""
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Boolean, Numeric, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class AccountPartyRole(str, enum.Enum):
    SHAREHOLDER = "Shareholder"
    DIRECTOR = "Director"
    AUTHORISED_SIGNATORY = "Authorised Signatory"


class AccountPartyConstitution(str, enum.Enum):
    INDIVIDUAL = "Individual"
    ENTITY = "Entity"


class AccountParty(Base):
    __tablename__ = "account_parties"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)

    # role/constitution stored as plain strings — same precedent as Case.jurisdiction
    # and Account.kyc_status (Postgres enums proved painful to alter later).
    party_role = Column(String(30), nullable=False)  # Shareholder / Director / Authorised Signatory
    constitution = Column(String(20), default=AccountPartyConstitution.INDIVIDUAL.value, nullable=False)

    full_name = Column(String(255), nullable=False)
    # Spec's own dual-purpose fields (§14.3/21.3, §14.4/21.4) — label switches by constitution.
    dob_or_incorp_date = Column(Date, nullable=True)
    id_or_license_expiry = Column(Date, nullable=True)
    country_of_incorp_or_birth = Column(String(120), nullable=True)

    mobile = Column(String(50), nullable=True)  # superseded by mobile_country_code/mobile_number below (client spec §15)
    mobile_country_code = Column(String(6), nullable=True)
    mobile_number = Column(String(12), nullable=True)
    email = Column(String(255), nullable=True)

    country_of_residence = Column(String(120), nullable=True)
    residential_address = Column(JSON, nullable=True)  # AddressBlock shape (see schemas/account.py)

    uae_visa_number = Column(String(50), nullable=True)
    uae_visa_expiry = Column(Date, nullable=True)

    is_pep = Column(Boolean, default=False, nullable=False)

    effective_ownership_percent = Column(Numeric(5, 2), nullable=True)  # Shareholder only
    nominee_director_name = Column(String(255), nullable=True)  # Director only

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    account = relationship("Account", back_populates="parties")
