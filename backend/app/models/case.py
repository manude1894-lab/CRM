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
    # Entity-lifecycle states — derived by lifecycle_service from EntityLifecycle.
    IN_CLOSURE = "In Closure"
    STRUCK_OFF = "Struck Off"
    DISSOLVED = "Dissolved"
    TRANSFERRED_OUT = "Transferred Out"


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
    ADGM = "ADGM"
    DIFC = "DIFC"
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
    # Who referred the entity to Triam (a registered agent or a person) — distinct
    # from the internal RM (rm_id). Free text; matches the tracker's "introduced-by".
    introducer = Column(String(150), nullable=True)
    # When Triam took the entity on — distinct from CompanyProfile.incorporation_date.
    onboarding_date = Column(Date, nullable=True)
    jurisdiction = Column(String(100), nullable=True)
    service_type = Column(String(100), nullable=True)

    # Pipeline state
    stage = Column(SAEnum(CaseStage, name="case_stage", values_callable=lambda obj: [e.value for e in obj]), default=CaseStage.NEW_INQUIRY, nullable=False)
    # Plain String (not a PG enum) so lifecycle values can be added freely — same
    # precedent as jurisdiction / service_type (migration 0003).
    status = Column(String(30), default=CaseStatus.ACTIVE.value, nullable=False)

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

    # Engagement Letter tracking (the letter itself lives in the document store).
    engagement_letter_sent_date = Column(Date, nullable=True)
    engagement_letter_signed_date = Column(Date, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    account = relationship("Account", back_populates="cases")
    rm = relationship("User", back_populates="cases_as_rm", foreign_keys=[rm_id])
    ops_owner = relationship("User", back_populates="cases_as_ops", foreign_keys=[ops_owner_id])
    activities = relationship("Activity", back_populates="case", cascade="all, delete-orphan")
    cdd_record = relationship("CDDRecord", back_populates="case", uselist=False, cascade="all, delete-orphan")
    compliance_schedule = relationship("ComplianceSchedule", back_populates="case", uselist=False, cascade="all, delete-orphan")
    company_profile = relationship("CompanyProfile", back_populates="case", uselist=False, cascade="all, delete-orphan")
    lifecycle = relationship("EntityLifecycle", back_populates="case", uselist=False, cascade="all, delete-orphan")
    formation = relationship("FormationRecord", back_populates="case", uselist=False, cascade="all, delete-orphan")
    directors = relationship("Director", back_populates="case", cascade="all, delete-orphan", order_by="Director.id")
    shareholders = relationship("Shareholder", back_populates="case", cascade="all, delete-orphan", order_by="Shareholder.id")
    ubos = relationship("UBO", back_populates="case", cascade="all, delete-orphan", order_by="UBO.id")
    instructions = relationship("Instruction", back_populates="case", cascade="all, delete-orphan", order_by="Instruction.id.desc()")
    invoices = relationship("Invoice", back_populates="case", cascade="all, delete-orphan", order_by="Invoice.id.desc()")
    aml_assessments = relationship("AMLRiskAssessment", back_populates="case", cascade="all, delete-orphan", order_by="AMLRiskAssessment.id.desc()")
    documents = relationship("Document", back_populates="case", cascade="all, delete-orphan", order_by="Document.id.desc()")
    additional_rms = relationship("CaseAdditionalRM", back_populates="case", cascade="all, delete-orphan")

    @property
    def additional_rm_ids(self) -> list[int]:
        return [r.user_id for r in self.additional_rms]


class CaseAdditionalRM(Base):
    """A secondary Relationship Manager on a case — Case.rm_id remains the primary RM."""
    __tablename__ = "case_relationship_managers"

    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)

    case = relationship("Case", back_populates="additional_rms")
    user = relationship("User")
