"""SQLAlchemy model: Prospect — pre-Case proposal tracking.

A prospect is a company Triam has pitched but not yet onboarded. Triam BRD mark-up §4A: every new
client starts here. A Prospecting Coordinator assigns the RM (or an RM takes it themselves), and the
client is created from the prospect; its Prospect ID is the client's temporary ID until Compliance
approves and the Client ID is issued.
"""
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class ProspectStatus(str, enum.Enum):
    NEW = "New"
    PROPOSAL_SENT = "Proposal Sent"
    NEGOTIATING = "Negotiating"
    WON = "Won"
    LOST = "Lost"


class Prospect(Base):
    __tablename__ = "prospects"

    id = Column(Integer, primary_key=True, index=True)
    prospect_uid = Column(String(20), unique=True, index=True, nullable=False)  # PROS-0001

    company_name = Column(String(255), nullable=False)
    contact_name = Column(String(150), nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    source = Column(String(50), nullable=True)

    owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(20), default=ProspectStatus.NEW.value, nullable=False)

    proposal_sent_date = Column(Date, nullable=True)
    proposal_amount = Column(Numeric(14, 2), nullable=True)
    expected_close_date = Column(Date, nullable=True)
    next_follow_up_date = Column(Date, nullable=True)
    lost_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    converted_case_id = Column(Integer, ForeignKey("cases.id", ondelete="SET NULL"), nullable=True)
    converted_account_id = Column(Integer, ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True)
    # owner_id is the assigned RM (empty = not yet assigned)
    assigned_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    assignor_comments = Column(Text, nullable=True)  # optional, up to 250 words

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    owner = relationship("User", foreign_keys=[owner_id])
    assigned_by = relationship("User", foreign_keys=[assigned_by_id])
    converted_case = relationship("Case", foreign_keys=[converted_case_id])
