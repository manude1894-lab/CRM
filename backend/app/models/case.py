"""SQLAlchemy model: Case (client onboarding journey)."""
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey, Numeric, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class CaseStage(str, enum.Enum):
    NEW_INQUIRY = "New Inquiry"
    RM_ASSIGNED = "RM Assigned"
    DOCS_REQUESTED = "Docs Requested"
    CDD_KYC_IN_REVIEW = "CDD/KYC In Review"
    CDD_APPROVED = "CDD Approved"
    INVOICE_RAISED = "Invoice Raised"
    INVOICE_PAID = "Invoice Paid"
    OPS_ASSIGNED = "Ops Assigned"
    APPLICATION_SUBMITTED = "Application Submitted"
    LICENSE_RECEIVED = "License Received"
    ACTIVE = "Active"


# Linear forward pipeline: each stage moves to exactly one next stage.
CASE_STAGE_TRANSITIONS: dict[str, list[str]] = {
    CaseStage.NEW_INQUIRY.value: [CaseStage.RM_ASSIGNED.value],
    CaseStage.RM_ASSIGNED.value: [CaseStage.DOCS_REQUESTED.value],
    CaseStage.DOCS_REQUESTED.value: [CaseStage.CDD_KYC_IN_REVIEW.value],
    CaseStage.CDD_KYC_IN_REVIEW.value: [CaseStage.CDD_APPROVED.value],
    CaseStage.CDD_APPROVED.value: [CaseStage.INVOICE_RAISED.value],
    CaseStage.INVOICE_RAISED.value: [CaseStage.INVOICE_PAID.value],
    CaseStage.INVOICE_PAID.value: [CaseStage.OPS_ASSIGNED.value],
    CaseStage.OPS_ASSIGNED.value: [CaseStage.APPLICATION_SUBMITTED.value],
    CaseStage.APPLICATION_SUBMITTED.value: [CaseStage.LICENSE_RECEIVED.value],
    CaseStage.LICENSE_RECEIVED.value: [CaseStage.ACTIVE.value],
    CaseStage.ACTIVE.value: [],
}


class CaseStatus(str, enum.Enum):
    ACTIVE = "Active"
    DOCS_PENDING = "Docs Pending"
    REJECTED = "Rejected"
    ON_HOLD = "On Hold"


class CaseSource(str, enum.Enum):
    SENIOR_MGMT = "Senior Mgmt"
    SOCIAL_MEDIA = "Social Media"
    REFERRAL = "Referral"
    OTHER = "Other"


class Jurisdiction(str, enum.Enum):
    BVI = "BVI"
    CAYMAN = "Cayman Islands"
    SEYCHELLES = "Seychelles"
    JERSEY = "Jersey"
    GUERNSEY = "Guernsey"
    ISLE_OF_MAN = "Isle of Man"
    MAURITIUS = "Mauritius"
    OTHER = "Other"


class ServiceType(str, enum.Enum):
    COMPANY_FORMATION = "Company Formation"
    ESR_FILING = "ESR Filing"
    ANNUAL_RETURN = "Annual Return"
    OWNERSHIP_UPDATE = "Ownership Update"
    DOCUMENT_PROVISION = "Document Provision"
    CDD_SUBMISSION = "CDD Submission"
    COMPANY_CLOSURE = "Company Closure"
    RESTORATION = "Restoration"
    OTHER = "Other"


class InvoiceStatus(str, enum.Enum):
    NOT_RAISED = "Not Raised"
    RAISED = "Raised"
    PAID = "Paid"


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    case_uid = Column(String(20), unique=True, index=True, nullable=False)  # CASE-0001

    # Foreign keys
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    rm_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    ops_owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Case definition
    company_name = Column(String(255), nullable=False)
    source = Column(SAEnum(CaseSource, name="case_source", values_callable=lambda obj: [e.value for e in obj]), default=CaseSource.OTHER, nullable=False)
    jurisdiction = Column(SAEnum(Jurisdiction, native_enum=False, values_callable=lambda obj: [e.value for e in obj]), nullable=True)
    service_type = Column(SAEnum(ServiceType, native_enum=False, values_callable=lambda obj: [e.value for e in obj]), nullable=True)

    # Pipeline state
    stage = Column(SAEnum(CaseStage, name="case_stage", values_callable=lambda obj: [e.value for e in obj]), default=CaseStage.NEW_INQUIRY, nullable=False)
    status = Column(SAEnum(CaseStatus, name="case_status", values_callable=lambda obj: [e.value for e in obj]), default=CaseStatus.ACTIVE, nullable=False)

    # Invoicing
    invoice_status = Column(SAEnum(InvoiceStatus, name="invoice_status", values_callable=lambda obj: [e.value for e in obj]), default=InvoiceStatus.NOT_RAISED, nullable=False)
    invoice_amount = Column(Numeric(14, 2), default=0, nullable=False)
    invoice_raised_date = Column(Date, nullable=True)
    invoice_paid_date = Column(Date, nullable=True)

    # Regulator / license
    license_received_date = Column(Date, nullable=True)
    license_expiry_date = Column(Date, nullable=True)

    tags = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    account = relationship("Account", back_populates="cases")
    rm = relationship("User", back_populates="cases_as_rm", foreign_keys=[rm_id])
    ops_owner = relationship("User", back_populates="cases_as_ops", foreign_keys=[ops_owner_id])
    activities = relationship("Activity", back_populates="case", cascade="all, delete-orphan")
    cdd_record = relationship("CDDRecord", back_populates="case", uselist=False, cascade="all, delete-orphan")
    compliance_schedule = relationship("ComplianceSchedule", back_populates="case", uselist=False, cascade="all, delete-orphan")
