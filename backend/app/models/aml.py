"""SQLAlchemy model: AMLRiskAssessment — a completed AML Risk Rating Matrix run.

Mirrors Triam's AML Risk Rating Matrix (Annexure 6, v8.0/6-25): a weighted-scoring
instrument run per customer. Two variants:
  - "Entity"     — 14 factors, run for the company being onboarded / periodically reviewed
  - "Individual" — 11 factors, run for each UBO / director as a person

Many per Case (an entity assessment plus one per individual, and re-runs over time for
periodic CDD review). The latest Entity assessment's effective rating is synced back to
CDDRecord.aml_risk_rating so the existing CDD workflow gate keeps working.
"""
from sqlalchemy import (
    Column, Integer, String, Text, Date, DateTime, Numeric, Boolean, ForeignKey, JSON,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class AMLSubjectType(str, enum.Enum):
    ENTITY = "Entity"
    INDIVIDUAL = "Individual"


class AMLRiskAssessment(Base):
    __tablename__ = "aml_risk_assessments"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)

    subject_type = Column(String(20), default=AMLSubjectType.ENTITY.value, nullable=False)
    subject_name = Column(String(255), nullable=False)

    # Optional link when subject_type == "Individual".
    director_id = Column(Integer, ForeignKey("directors.id", ondelete="SET NULL"), nullable=True)
    shareholder_id = Column(Integer, ForeignKey("shareholders.id", ondelete="SET NULL"), nullable=True)
    ubo_id = Column(Integer, ForeignKey("ubos.id", ondelete="SET NULL"), nullable=True)

    assessment_date = Column(Date, nullable=True)
    completed_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    matrix_version = Column(String(20), nullable=True)

    # The filled matrix rows, as computed by aml_matrix.calculate():
    # [{key, label, input, rating, score, weight, weighted_score}, ...]
    factors = Column(JSON, nullable=True)

    total_weighted_score = Column(Numeric(5, 2), nullable=True)
    calculated_rating = Column(String(20), nullable=True)  # Low | Medium | High
    override_reason = Column(String(500), nullable=True)  # why the band was overridden to High
    onboarding_blocked = Column(Boolean, default=False, nullable=False)  # a Prohibited jurisdiction was selected

    # MLRO manual override ("Amended Overall Customer Risk" on the paper form).
    amended_rating = Column(String(20), nullable=True)
    mlro_notes = Column(Text, nullable=True)
    mlro_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    mlro_reviewed_at = Column(DateTime(timezone=True), nullable=True)

    remarks = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    case = relationship("Case", back_populates="aml_assessments")
    completed_by = relationship("User", foreign_keys=[completed_by_id])
    mlro = relationship("User", foreign_keys=[mlro_id])
    director = relationship("Director")
    shareholder = relationship("Shareholder")
    ubo = relationship("UBO")

    @property
    def effective_rating(self) -> str | None:
        return self.amended_rating or self.calculated_rating
