"""Pydantic schemas: CDDRecord and CaseDocument checklist."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import date, datetime

from app.models.cdd import DocumentStatus, AMLRiskRating


class CaseDocumentBase(BaseModel):
    doc_type: str = Field(..., min_length=1, max_length=150)
    received: bool = False
    received_date: Optional[date] = None


class CaseDocumentCreate(CaseDocumentBase):
    pass


class CaseDocumentUpdate(BaseModel):
    doc_type: Optional[str] = None
    received: Optional[bool] = None
    received_date: Optional[date] = None


class CaseDocumentRead(CaseDocumentBase):
    id: int
    cdd_record_id: int
    director_id: Optional[int] = None
    shareholder_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CDDRecordUpdate(BaseModel):
    cdd_form_status: Optional[DocumentStatus] = None
    kyc_verification_status: Optional[DocumentStatus] = None
    aml_risk_rating: Optional[AMLRiskRating] = None


class CDDReviewRequest(BaseModel):
    approve: bool
    rejection_reason: Optional[str] = None


class CDDRecordRead(BaseModel):
    id: int
    case_id: int
    cdd_form_status: DocumentStatus
    kyc_verification_status: DocumentStatus
    aml_risk_rating: Optional[AMLRiskRating] = None
    screening_reviewer_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    documents: List[CaseDocumentRead] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
