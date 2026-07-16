"""Compliance schedule router (renewals, compliance filings, tax filings)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User
from app.schemas import ComplianceScheduleRead, ComplianceMarkDoneRequest, UpcomingComplianceItem
from app.services import compliance_service

router = APIRouter(prefix="/compliance", tags=["Compliance"])


@router.get("", response_model=list[UpcomingComplianceItem], summary="List upcoming renewals/filings within N days")
def list_upcoming(days: int = 60, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return compliance_service.list_upcoming(db, days)


@router.get("/{case_id}", response_model=ComplianceScheduleRead)
def get_schedule(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return compliance_service.get_schedule(db, case_id)


@router.post("/{case_id}/mark-done", response_model=ComplianceScheduleRead, summary="Mark a renewal/filing item done and roll the due date forward")
def mark_done(case_id: int, data: ComplianceMarkDoneRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return compliance_service.mark_done(db, case_id, data)
