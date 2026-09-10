"""SQLAlchemy model: FormationRecord — the pre-incorporation compliance file.

1:1 with Case (same pattern as CompanyProfile / EntityLifecycle), lazy
get-or-create. Covers the parts of the Process Manual §V formation flow that
previously happened outside the CRM:

  - name / World-Check screening of the entity and its parties (sanctions / PEP /
    adverse media) — distinct from the name *availability* check on CompanyProfile
  - the MLRO's second-line sign-off, distinct from the internal screening reviewer
    on CDDRecord
  - the Vistra compliance loop: sent to Vistra -> query raised -> Vistra approved
  - the §V milestone dates (KYC pack out, DIS sent, incorporation submitted,
    ROD filed, registers completed, formation done)

Enum-like fields are plain String columns — same precedent as
Case.jurisdiction / CompanyProfile.registered_agent (migration 0003).
"""
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class ScreeningStatus(str, enum.Enum):
    NOT_STARTED = "Not Started"
    IN_PROGRESS = "In Progress"
    CLEARED = "Cleared"
    ADVERSE_FINDINGS = "Adverse Findings"


class MLROSignoffStatus(str, enum.Enum):
    PENDING = "Pending"
    SIGNED_OFF = "Signed Off"
    REJECTED = "Rejected"


class VistraStatus(str, enum.Enum):
    NOT_SUBMITTED = "Not Submitted"
    SUBMITTED = "Submitted"
    QUERY_RAISED = "Query Raised"
    APPROVED = "Approved"
    REJECTED = "Rejected"


class FormationRecord(Base):
    __tablename__ = "formation_records"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), unique=True, nullable=False)

    # ─── Name / World-Check screening ──────────────────────────────────
    screening_status = Column(String(20), default=ScreeningStatus.NOT_STARTED.value, nullable=False)
    screening_date = Column(Date, nullable=True)
    screened_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    screening_tool = Column(String(60), nullable=True)
    world_check_reference = Column(String(120), nullable=True)
    sanctions_hit = Column(Boolean, default=False, nullable=False)
    pep_hit = Column(Boolean, default=False, nullable=False)
    adverse_media_hit = Column(Boolean, default=False, nullable=False)
    screening_findings = Column(Text, nullable=True)

    # ─── MLRO sign-off (distinct from CDDRecord.screening_reviewer) ────
    mlro_signoff_status = Column(String(20), default=MLROSignoffStatus.PENDING.value, nullable=False)
    mlro_signoff_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    mlro_signoff_at = Column(DateTime(timezone=True), nullable=True)
    mlro_signoff_notes = Column(Text, nullable=True)

    # ─── Vistra compliance loop ───────────────────────────────────────
    vistra_status = Column(String(30), default=VistraStatus.NOT_SUBMITTED.value, nullable=False)
    vistra_submitted_date = Column(Date, nullable=True)
    vistra_query_text = Column(Text, nullable=True)
    vistra_query_raised_date = Column(Date, nullable=True)
    vistra_query_resolved_date = Column(Date, nullable=True)
    vistra_approved_date = Column(Date, nullable=True)
    vistra_officer = Column(String(120), nullable=True)

    # ─── §V formation milestones ──────────────────────────────────────
    kyc_pack_sent_date = Column(Date, nullable=True)
    data_input_sheet_sent_date = Column(Date, nullable=True)
    incorporation_submitted_date = Column(Date, nullable=True)
    rod_filed_date = Column(Date, nullable=True)  # Register of Directors — filed within 21 days
    registers_completed_date = Column(Date, nullable=True)  # VIRRGIN upload done
    formation_completed_date = Column(Date, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    case = relationship("Case", back_populates="formation")
    screened_by = relationship("User", foreign_keys=[screened_by_id])
    mlro_signoff_by = relationship("User", foreign_keys=[mlro_signoff_by_id])
