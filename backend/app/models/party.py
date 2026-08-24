"""SQLAlchemy models: Director and Shareholder registers (per Case / BVI entity).

Field sets mirror Triam's actual Vistra register templates (Director Register,
Shareholder Register) rather than the full bilingual Data Input Sheet — this is
a CRM register, not a data-entry clone of the Vistra form.
"""
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Boolean, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class PartyType(str, enum.Enum):
    INDIVIDUAL = "Individual"
    CORPORATE = "Corporate"


class ShareholderType(str, enum.Enum):
    INDIVIDUAL = "Individual"
    BC_COMPANY = "BC Company"
    NON_BVI_ENTITY = "Non-BVI Entity"
    LIMITED_PARTNERSHIP = "Limited Partnership"


class Director(Base):
    """One row per director on a Case's Register of Directors.

    director_type/party fields stored as plain strings (not DB enums) — matches
    the jurisdiction/service_type/aml_risk_rating precedent from migration 0003,
    which moved off Postgres enums after they proved painful to alter.
    """
    __tablename__ = "directors"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)

    director_type = Column(String(20), default=PartyType.INDIVIDUAL.value, nullable=False)

    # Individual director
    first_name = Column(String(150), nullable=True)
    middle_name = Column(String(150), nullable=True)
    last_name = Column(String(150), nullable=True)
    former_name = Column(String(255), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    place_of_birth = Column(String(150), nullable=True)
    nationality = Column(String(100), nullable=True)
    passport_number = Column(String(50), nullable=True)

    # Corporate director
    corporate_name = Column(String(255), nullable=True)
    corporate_number = Column(String(100), nullable=True)
    country_of_incorporation = Column(String(100), nullable=True)
    corporate_date_of_incorporation = Column(Date, nullable=True)

    # Service address
    service_address = Column(String(255), nullable=True)
    service_city = Column(String(100), nullable=True)
    service_country = Column(String(100), nullable=True)

    # Residential / registered office address
    residential_address = Column(String(255), nullable=True)
    residential_city = Column(String(100), nullable=True)
    residential_country = Column(String(100), nullable=True)

    appointment_date = Column(Date, nullable=True)
    cessation_date = Column(Date, nullable=True)

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    case = relationship("Case", back_populates="directors")


class Shareholder(Base):
    """One row per shareholder on a Case's Register of Members.

    shareholding_percent is stored directly (rather than derived) so the 10%+
    CDD threshold the BVI process manual calls out repeatedly can be queried
    without recomputing from total shares issued.
    """
    __tablename__ = "shareholders"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)

    identification_type = Column(String(30), default=ShareholderType.INDIVIDUAL.value, nullable=False)

    name = Column(String(255), nullable=False)  # individual full name or corporate name
    corporate_number = Column(String(100), nullable=True)
    country_of_incorporation = Column(String(100), nullable=True)

    registered_address = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)

    certificate_no = Column(String(50), nullable=True)
    number_of_shares = Column(Integer, nullable=True)
    share_class = Column(String(50), nullable=True)
    shareholding_percent = Column(Numeric(5, 2), nullable=True)

    is_joint_shareholder = Column(Boolean, default=False, nullable=False)
    is_nominee = Column(Boolean, default=False, nullable=False)
    nominee_holds_for = Column(String(255), nullable=True)  # beneficial owner the nominee holds shares for

    date_entered = Column(Date, nullable=True)
    date_ceased = Column(Date, nullable=True)

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    case = relationship("Case", back_populates="shareholders")
