"""Company profile router — formation / statutory detail (1:1 with Case)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User
from app.schemas import CompanyProfileRead, CompanyProfileUpdate
from app.services import company_service

router = APIRouter(tags=["Company Profile"])


@router.get("/cases/{case_id}/company-profile", response_model=CompanyProfileRead)
def get_company_profile(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return company_service.get_or_create(db, case_id)


@router.patch("/cases/{case_id}/company-profile", response_model=CompanyProfileRead)
def update_company_profile(case_id: int, data: CompanyProfileUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return company_service.update(db, case_id, data, user)
