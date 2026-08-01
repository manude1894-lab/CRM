"""Service layer: CDDRecord + CaseDocument checklist + screening review."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import CDDRecord, CaseDocument, Case, CaseStatus, DocumentStatus, User
from app.schemas.cdd import CDDRecordUpdate, CDDReviewRequest, CaseDocumentCreate, CaseDocumentUpdate


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
            case.status = CaseStatus.ACTIVE
    else:
        if not data.rejection_reason:
            raise HTTPException(status_code=400, detail="rejection_reason is required when rejecting CDD")
        cdd.cdd_form_status = DocumentStatus.REJECTED
        cdd.kyc_verification_status = DocumentStatus.REJECTED
        cdd.rejection_reason = data.rejection_reason
        if case:
            case.status = CaseStatus.REJECTED

    cdd.screening_reviewer_id = user.id
    cdd.reviewed_at = datetime.now(timezone.utc)
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
