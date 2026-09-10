"""Pydantic schemas: PEPAssessment (standalone PEP / EDD assessment)."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import date, datetime

from app.models.pep_assessment import PEPType, PEPRiskConclusion


class PEPAssessmentBase(BaseModel):
    subject_name: str = Field(..., min_length=1, max_length=255)
    director_id: Optional[int] = None
    shareholder_id: Optional[int] = None
    ubo_id: Optional[int] = None
    pep_type: Optional[PEPType] = None
    position: Optional[str] = None
    pep_jurisdiction: Optional[str] = None
    since_date: Optional[date] = None
    still_in_office: Optional[bool] = None
    family_and_associates: Optional[str] = None
    source_of_wealth_scrutiny: Optional[str] = None
    source_of_funds_scrutiny: Optional[str] = None
    edd_measures: Optional[str] = None
    adverse_media_findings: Optional[str] = None
    risk_conclusion: Optional[PEPRiskConclusion] = None
    senior_management_approved: Optional[bool] = None
    assessment_date: Optional[date] = None
    notes: Optional[str] = None


class PEPAssessmentCreate(PEPAssessmentBase):
    case_id: int


class PEPAssessmentUpdate(PEPAssessmentBase):
    subject_name: Optional[str] = Field(None, min_length=1, max_length=255)


class PEPAssessmentRead(PEPAssessmentBase):
    id: int
    case_id: int
    approved_by_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    assessed_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
