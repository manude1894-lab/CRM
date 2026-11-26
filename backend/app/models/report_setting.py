"""SQLAlchemy models: report settings set by the Administrator, and each user's favourite reports (Triam 26-11-2026).

As in other CRMs (Zoho, Salesforce, HubSpot): the Administrator decides who sees each report, may rename or hide
it and set its default period; each user stars the reports they use most.
"""
from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class ReportSetting(Base):
    __tablename__ = "report_settings"

    report_key = Column(String(60), primary_key=True)  # e.g. "documents-expiring"
    name = Column(String(150), nullable=True)  # the Administrator's name for it; blank keeps the standard name
    hidden = Column(Boolean, default=False, nullable=False)
    role_ids = Column(JSON, nullable=True)  # roles that may run it; null keeps the standard access
    default_days = Column(Integer, nullable=True)  # for the reports taking a number of days
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ReportFavourite(Base):
    __tablename__ = "report_favourites"
    __table_args__ = (UniqueConstraint("user_id", "report_key", name="uq_report_favourite"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    report_key = Column(String(60), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
