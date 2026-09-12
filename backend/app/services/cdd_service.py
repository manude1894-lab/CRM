"""Service layer: CDDRecord + CaseDocument checklist + screening review."""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import CDDRecord, CaseDocument, Case, CaseStatus, DocumentStatus, User, UserRole, Director, Shareholder, UBO
from app.schemas.cdd import CDDRecordUpdate, CDDReviewRequest, CaseDocumentCreate, CaseDocumentUpdate
from app.services import notification_service

# Per-party CDD requirements — Vistra KYC Appendix C.
INDIVIDUAL_PARTY_DOCUMENTS = [
    "Passport / ID Copy (certified true copy)",
    "Proof of Residential Address (utility bill / bank statement, max 6 months)",
]
CORPORATE_PARTY_DOCUMENTS = [
    "Certificate of Incorporation (certified true copy)",
    "Register of Directors (certified true copy)",
    "Register of Members (certified true copy)",
    "Memorandum & Articles of Association, if available (certified true copy)",
]
# UBOs additionally need the KYC Appendix A individual information form.
UBO_DOCUMENTS = INDIVIDUAL_PARTY_DOCUMENTS + ["Appendix A - Individual Information Form (KYC)"]
# Shareholders below 10% interest are optional CDD per Appendix C — documents are
# only auto-generated when the interest is unknown or at/above the threshold.
SHAREHOLDER_CDD_THRESHOLD_PERCENT = 10


def list_cdd_records(db: Session) -> list[CDDRecord]:
    return db.query(CDDRecord).all()


def get_cdd_record(db: Session, case_id: int) -> CDDRecord:
    cdd = db.query(CDDRecord).filter(CDDRecord.case_id == case_id).first()
    if not cdd:
        raise HTTPException(status_code=404, detail="CDD record not found for this case")
    return cdd


def update_cdd_record(db: Session, case_id: int, data: CDDRecordUpdate) -> CDDRecord:
    cdd = get_cdd_record(db, case_id)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(cdd, field, value)
    db.commit()
    db.refresh(cdd)
    return cdd


def review_cdd(db: Session, case_id: int, data: CDDReviewRequest, user: User) -> CDDRecord:
    cdd = get_cdd_record(db, case_id)
    case = db.query(Case).filter(Case.id == case_id).first()

    if data.approve:
        cdd.cdd_form_status = DocumentStatus.APPROVED
        cdd.kyc_verification_status = DocumentStatus.APPROVED
        cdd.rejection_reason = None
        if case:
            case.status = CaseStatus.ACTIVE.value
    else:
        if not data.rejection_reason:
            raise HTTPException(status_code=400, detail="rejection_reason is required when rejecting CDD")
        cdd.cdd_form_status = DocumentStatus.REJECTED
        cdd.kyc_verification_status = DocumentStatus.REJECTED
        cdd.rejection_reason = data.rejection_reason
        if case:
            case.status = CaseStatus.REJECTED.value

    cdd.screening_reviewer_id = user.id
    cdd.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(cdd)
    return cdd


def grant_cdd_exception(db: Session, case_id: int, reason: str, days: int, user: User) -> CDDRecord:
    """Time-boxed override letting the case proceed to invoicing before CDD is fully
    approved. Admin-only (enforced at the router); always expires."""
    cdd = get_cdd_record(db, case_id)
    cdd.exception_granted = True
    cdd.exception_reason = reason
    cdd.exception_granted_by_id = user.id
    cdd.exception_granted_at = datetime.now(timezone.utc)
    cdd.exception_expires_on = date.today() + timedelta(days=days)
    db.commit()
    db.refresh(cdd)

    case = db.query(Case).filter(Case.id == case_id).first()
    if case:
        msg = (f"CDD exception granted on {case.case_uid} ({case.company_name}) — "
               f"expires {cdd.exception_expires_on}. Reason: {reason}")
        if case.rm_id:
            notification_service.notify_user(db, case.rm_id, msg, "cdd_exception_granted",
                                             link=f"/cases/{case_id}", case_id=case_id)
        notification_service.notify_role(db, UserRole.OPS, msg, "cdd_exception_granted",
                                         link=f"/cases/{case_id}", case_id=case_id)
    return cdd


def revoke_cdd_exception(db: Session, case_id: int) -> CDDRecord:
    cdd = get_cdd_record(db, case_id)
    cdd.exception_granted = False
    db.commit()
    db.refresh(cdd)
    return cdd


_INTRODUCER_WAIVE_REASON = (
    "Professional introducer — supporting evidence not required unless requested "
    "by the registered agent (Vistra KYC Appendix C)."
)


def apply_introducer_exemption(db: Session, case_id: int) -> CDDRecord:
    """Vistra KYC Appendix C: a professional introducer (Triam) need not provide the
    per-party supporting evidence (passport, address proof) unless the RA asks. Waive
    those checklist items; keep the Appendix A forms and company-level items required."""
    cdd = get_cdd_record(db, case_id)
    for doc in cdd.documents:
        party_linked = doc.director_id or doc.shareholder_id or doc.ubo_id
        is_appendix_a = "appendix a" in doc.doc_type.lower()
        if party_linked and not is_appendix_a and not doc.received and not doc.waived:
            doc.waived = True
            doc.waived_reason = _INTRODUCER_WAIVE_REASON
    db.commit()
    db.refresh(cdd)
    return cdd


def add_document(db: Session, case_id: int, data: CaseDocumentCreate) -> CaseDocument:
    cdd = get_cdd_record(db, case_id)
    doc = CaseDocument(cdd_record_id=cdd.id, **data.model_dump())
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def update_document(db: Session, document_id: int, data: CaseDocumentUpdate) -> CaseDocument:
    doc = db.query(CaseDocument).filter(CaseDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(doc, field, value)
    db.commit()
    db.refresh(doc)
    return doc


def delete_document(db: Session, document_id: int) -> None:
    doc = db.query(CaseDocument).filter(CaseDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(doc)
    db.commit()


def generate_director_documents(db: Session, director: Director) -> list[CaseDocument]:
    """Seed the CDD checklist items required for a newly-added director.

    Directors always require full CDD (Vistra KYC Appendix A2/C — no ownership
    threshold applies to directors, unlike shareholders).
    """
    cdd = db.query(CDDRecord).filter(CDDRecord.case_id == director.case_id).first()
    if not cdd:
        return []
    doc_types = INDIVIDUAL_PARTY_DOCUMENTS if director.director_type == "Individual" else CORPORATE_PARTY_DOCUMENTS
    docs = [CaseDocument(cdd_record_id=cdd.id, director_id=director.id, doc_type=t) for t in doc_types]
    db.add_all(docs)
    db.commit()
    return docs


def generate_shareholder_documents(db: Session, shareholder: Shareholder) -> list[CaseDocument]:
    """Seed the CDD checklist items required for a newly-added shareholder.

    Full CDD is only mandatory for 10%+ holders (Vistra KYC Appendix C /
    BVI beneficial-ownership rules) — skip auto-generation below that threshold
    unless the holding is unspecified, since under-10% CDD is optional per the
    form's own "C3. Optional" language.
    """
    pct = shareholder.shareholding_percent
    if pct is not None and pct < SHAREHOLDER_CDD_THRESHOLD_PERCENT:
        return []
    cdd = db.query(CDDRecord).filter(CDDRecord.case_id == shareholder.case_id).first()
    if not cdd:
        return []
    doc_types = INDIVIDUAL_PARTY_DOCUMENTS if shareholder.identification_type == "Individual" else CORPORATE_PARTY_DOCUMENTS
    docs = [CaseDocument(cdd_record_id=cdd.id, shareholder_id=shareholder.id, doc_type=t) for t in doc_types]
    db.add_all(docs)
    db.commit()
    return docs


def generate_ubo_documents(db: Session, ubo: UBO) -> list[CaseDocument]:
    """Seed CDD checklist items for a newly-added UBO.

    Full individual CDD (passport, address proof, Appendix A) is mandatory for
    10%+ beneficial owners — below that, CDD is optional per Vistra KYC Appendix
    C3, so only auto-generate when the interest is unknown or at/above threshold.
    """
    pct = ubo.percentage_interest
    if pct is not None and pct < SHAREHOLDER_CDD_THRESHOLD_PERCENT:
        return []
    cdd = db.query(CDDRecord).filter(CDDRecord.case_id == ubo.case_id).first()
    if not cdd:
        return []
    docs = [CaseDocument(cdd_record_id=cdd.id, ubo_id=ubo.id, doc_type=t) for t in UBO_DOCUMENTS]
    db.add_all(docs)
    db.commit()
    return docs
