"""PEP assessment router — standalone PEP / EDD assessments per party."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User
from app.schemas import PEPAssessmentCreate, PEPAssessmentUpdate, PEPAssessmentRead
from app.services import pep_service

router = APIRouter(tags=["PEP Assessments"])


@router.get("/cases/{case_id}/pep-assessments", response_model=List[PEPAssessmentRead])
def list_pep_assessments(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return pep_service.list_for_case(db, case_id)


@router.post("/cases/{case_id}/pep-assessments", response_model=PEPAssessmentRead, status_code=status.HTTP_201_CREATED)
def create_pep_assessment(case_id: int, data: PEPAssessmentCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if data.case_id != case_id:
        data = data.model_copy(update={"case_id": case_id})
    return pep_service.create_assessment(db, data, user)


@router.patch("/pep-assessments/{assessment_id}", response_model=PEPAssessmentRead)
def update_pep_assessment(assessment_id: int, data: PEPAssessmentUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return pep_service.update_assessment(db, assessment_id, data, user)


@router.delete("/pep-assessments/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pep_assessment(assessment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    pep_service.delete_assessment(db, assessment_id, user)
    return None
