"""SQLAlchemy model: EntityLifecycle — the end of a Case's life.

1:1 with Case (same pattern as CompanyProfile / ComplianceSchedule), lazy
get-or-create. Holds the three things the CRM previously tracked only in the
Instruction Tracker spreadsheet:

  - closure / strike-off / lapse (Process Manual §X) — method, dates, the written
    client acknowledgement, the strike-off date and the +7-year dissolution horizon
  - restoration (§XI) — status, the strike-off cause, and the 15-item document
    checklist (stored as JSON on this row)
  - registered-agent transfer — from/to agent, dates, and whether the transfer
    ends Triam's administration entirely

The derived Case.status ("In Closure" / "Struck Off" / "Dissolved" /
"Transferred Out") is set by lifecycle_service.update() from these fields.

Enum-like fields are plain String columns — same precedent as
Case.jurisdiction / CompanyProfile.registered_agent (migration 0003).
"""
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class ClosureMethod(str, enum.Enum):
    VOLUNTARY_LIQUIDATION = "Voluntary Liquidation"
    VOLUNTARY_STRIKE_OFF = "Voluntary Strike Off"
    LAPSE_NON_PAYMENT = "Lapse by Non-Payment"


class RestorationStatus(str, enum.Enum):
    NOT_APPLICABLE = "Not Applicable"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"


class StrikeOffCause(str, enum.Enum):
    CLIENT_RELATED = "Client-related"
    AGENT_RELATED = "Agent-related"
    OTHER = "Other"


class ChecklistItemStatus(str, enum.Enum):
    PENDING = "Pending"
    RECEIVED = "Received"
    NOT_APPLICABLE = "N/A"


# Process Manual §XI — documents to collect for a restoration application.
# (key, label) — the key is stable; the label is what the UI shows.
RESTORATION_CHECKLIST_TEMPLATE: list[tuple[str, str]] = [
    ("ci", "Certificate of Incorporation (CI)"),
    ("rom", "Register of Members (ROM)"),
    ("rod", "Register of Directors (ROD)"),
    ("rod_stamped", "Register of Directors — stamped (ROD Stamped)"),
    ("moa", "Memorandum & Articles of Association (M&A)"),
    ("resolution_carrying_business", "Resolution on carrying on business"),
    ("es_fy_start_confirmation", "ES financial year start-date confirmation"),
    ("es_filing_2020_2024", "2020–2024 Economic Substance filing status"),
    ("ar_2023_form", "2023 Annual Return submission form"),
    ("ar_2024_form", "2024 Annual Return submission form"),
    ("bo_form", "BO / ROM-RBO form"),
    ("indemnity_letter", "Indemnity letter"),
    ("resolution_appointing_vistra", "Resolution appointing Vistra / RORA"),
    ("bvi_record_keeping_resolution", "BVI record-keeping resolution"),
    ("rom_bvi_form", "ROM BVI form"),
]


def new_restoration_checklist() -> list[dict]:
    return [
        {"key": key, "label": label, "status": ChecklistItemStatus.PENDING.value, "note": None}
        for key, label in RESTORATION_CHECKLIST_TEMPLATE
    ]


class EntityLifecycle(Base):
    __tablename__ = "entity_lifecycle"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), unique=True, nullable=False)

    # ─── Closure / strike-off / lapse (§X) ──────────────────────────────
    closure_method = Column(String(40), nullable=True)
    closure_initiated_date = Column(Date, nullable=True)
    closure_reason = Column(Text, nullable=True)
    client_acknowledgement_received = Column(Boolean, default=False, nullable=False)
    client_acknowledgement_date = Column(Date, nullable=True)
    outstanding_filings_cleared = Column(Boolean, default=False, nullable=False)
    strike_off_date = Column(Date, nullable=True)
    strike_off_in_good_standing = Column(Boolean, default=False, nullable=False)
    expected_dissolution_date = Column(Date, nullable=True)  # strike_off_date + 7 years
    dissolution_confirmed = Column(Boolean, default=False, nullable=False)
    dissolution_date = Column(Date, nullable=True)

    # ─── Restoration (§XI) ──────────────────────────────────────────────
    restoration_status = Column(String(20), default=RestorationStatus.NOT_APPLICABLE.value, nullable=False)
    restoration_initiated_date = Column(Date, nullable=True)
    restoration_completed_date = Column(Date, nullable=True)
    strike_off_cause = Column(String(20), nullable=True)
    restoration_checklist = Column(JSON, nullable=True)  # [{key, label, status, note}, ...]

    # ─── Registered-agent transfer ─────────────────────────────────────
    transfer_from_agent = Column(String(50), nullable=True)
    transfer_to_agent = Column(String(50), nullable=True)
    transfer_initiated_date = Column(Date, nullable=True)
    transfer_completed_date = Column(Date, nullable=True)
    transfer_ends_administration = Column(Boolean, default=False, nullable=False)
    transfer_notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    case = relationship("Case", back_populates="lifecycle")
