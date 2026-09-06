"""AML Risk Matrix router — assessments + country-risk reference table."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.auth.dependencies import get_current_user, require_admin, require_roles
from app.models import User, UserRole
from app.schemas import (
    AMLAssessmentCreate, AMLAssessmentUpdate, AMLAssessmentRead, AMLCatalogRead,
    CountryRiskCreate, CountryRiskUpdate, CountryRiskRead,
)
from app.services import aml_service, aml_matrix

router = APIRouter(prefix="/aml", tags=["AML Risk"])

require_assessor = require_roles(UserRole.ADMIN, UserRole.SCREENING, UserRole.RM)


# ─── Catalog ────────────────────────────────────────────────────────────
@router.get("/catalog", response_model=AMLCatalogRead, summary="Factor definitions + option lists")
def get_catalog(user: User = Depends(get_current_user)):
    return aml_matrix.catalog()


# ─── Country risk table ─────────────────────────────────────────────────
@router.get("/country-risk", response_model=List[CountryRiskRead])
def list_country_risk(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return aml_service.list_country_risk(db)


@router.post("/country-risk", response_model=CountryRiskRead, status_code=status.HTTP_201_CREATED)
def create_country_risk(data: CountryRiskCreate, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return aml_service.create_country_risk(db, data)


@router.patch("/country-risk/{country_id}", response_model=CountryRiskRead)
def update_country_risk(country_id: int, data: CountryRiskUpdate, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return aml_service.update_country_risk(db, country_id, data)


@router.delete("/country-risk/{country_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_country_risk(country_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    aml_service.delete_country_risk(db, country_id)
    return None


# ─── Assessments ────────────────────────────────────────────────────────
@router.get("/assessments", response_model=List[AMLAssessmentRead])
def list_assessments(case_id: Optional[int] = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return aml_service.list_assessments(db, case_id)


@router.get("/assessments/{assessment_id}", response_model=AMLAssessmentRead)
def get_assessment(assessment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return aml_service.get_assessment(db, assessment_id)


@router.post("/assessments", response_model=AMLAssessmentRead, status_code=status.HTTP_201_CREATED)
def create_assessment(data: AMLAssessmentCreate, db: Session = Depends(get_db), user: User = Depends(require_assessor)):
    return aml_service.create_assessment(db, data, user)


@router.patch("/assessments/{assessment_id}", response_model=AMLAssessmentRead, summary="Edit selections (assessor) or apply an MLRO amendment (screening/admin)")
def update_assessment(assessment_id: int, data: AMLAssessmentUpdate, db: Session = Depends(get_db), user: User = Depends(require_assessor)):
    return aml_service.update_assessment(db, assessment_id, data, user)


@router.delete("/assessments/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assessment(assessment_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    aml_service.delete_assessment(db, assessment_id, user)
    return None
