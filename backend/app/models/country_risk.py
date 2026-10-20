"""SQLAlchemy model: the Countries master (BRD §17), table country_risk.

Only the name is used by the CRM (every country drop-down). The risk columns are the reference data
the list was first loaded from and are not shown or used.
"""
from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime
from sqlalchemy.sql import func

from app.database import Base


class CountryRisk(Base):
    __tablename__ = "country_risk"

    id = Column(Integer, primary_key=True, index=True)
    # Country name exactly as spelled in the AML Risk Matrix document — this string
    # is what the assessment stores as the factor input, so the two must match.
    name = Column(String(120), unique=True, nullable=False, index=True)

    kyc_score = Column(Numeric(5, 2), nullable=True)  # KnowYourCountry score, e.g. 54.58
    # risk_level already reflects the FATF override (a KYC-Medium country on the grey
    # list is stored as "High" here, matching the document's own Risk Level column).
    risk_level = Column(String(20), nullable=False)  # Low | Medium | High | Prohibited
    score = Column(Integer, nullable=False)  # 1 | 3 | 5

    # True when the country is FATF-listed — the calc forces overall rating to High.
    default_to_high = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
