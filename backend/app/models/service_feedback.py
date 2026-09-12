"""SQLAlchemy model: ServiceFeedback — staff-logged client feedback after a service.

Not a client-facing form (this CRM has no unauthenticated client portal) — it's the
RM/Ops recording feedback they received from the client by phone/email/etc.
"""
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class ServiceFeedback(Base):
    __tablename__ = "service_feedback"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    instruction_id = Column(Integer, ForeignKey("instructions.id", ondelete="SET NULL"), nullable=True)

    rating = Column(Integer, nullable=True)  # 1-5
    comments = Column(Text, nullable=True)
    received_via = Column(String(20), nullable=True)  # Email / Phone / WhatsApp / In-person / Other
    recorded_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    feedback_date = Column(Date, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    case = relationship("Case")
    instruction = relationship("Instruction")
    recorded_by = relationship("User")
