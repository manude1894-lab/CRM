"""CDD / KYC screening router."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user, require_screening
from app.models import User
from typing import List

from app.schemas import (
    CDDRecordRead, CDDRecordUpdate, CDDReviewRequest,
    CaseDocumentCreate, CaseDocumentRead, CaseDocumentUpdate,
)
from app.services import cdd_service

router = APIRouter(prefix="/cdd", tags=["CDD / KYC"])


@router.get("", response_model=List[CDDRecordRead], summary="List all CDD records (one per case)")
def list_cdd(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return cdd_service.list_cdd_records(db)


@router.get("/{case_id}", response_model=CDDRecordRead)
def get_cdd(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return cdd_service.get_cdd_record(db, case_id)


@router.patch("/{case_id}", response_model=CDDRecordRead)
def update_cdd(case_id: int, data: CDDRecordUpdate, db: Session = Depends(get_db), user: User = Depends(require_screening)):
    return cdd_service.update_cdd_record(db, case_id, data)


@router.post("/{case_id}/review", response_model=CDDRecordRead, summary="Approve or reject CDD/KYC (Screening/Admin only)")
def review_cdd(case_id: int, data: CDDReviewRequest, db: Session = Depends(get_db), user: User = Depends(require_screening)):
    return cdd_service.review_cdd(db, case_id, data, user)


@router.post("/{case_id}/documents", response_model=CaseDocumentRead, status_code=status.HTTP_201_CREATED)
def add_document(case_id: int, data: CaseDocumentCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return cdd_service.add_document(db, case_id, data)


@router.patch("/documents/{document_id}", response_model=CaseDocumentRead)
def update_document(document_id: int, data: CaseDocumentUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return cdd_service.update_document(db, document_id, data)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, db: Session = Depends(get_db), user: User = Depends(require_screening)):
    cdd_service.delete_document(db, document_id)
    return None
