"""Reports router: the BRD §20 standard reports (shown on screen, exported to CSV in the browser)."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User
from app.services import standard_reports_service

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/standard", summary="Standard reports available")
def standard_reports(user: User = Depends(get_current_user)):
    return [{"key": k, "title": t} for k, t in standard_reports_service.REPORTS.items()]


@router.get("/standard/{key}", summary="Run a standard report")
def run_standard_report(key: str, days: Optional[int] = None, date_from: Optional[date] = None, date_to: Optional[date] = None,
                        status: Optional[str] = None, department_id: Optional[int] = None,
                        db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return standard_reports_service.run(db, user, key, days, date_from, date_to, status, department_id)


@router.get("/onboarding-statuses", summary="Statuses the client onboarding report can be filtered by")
def onboarding_statuses(user: User = Depends(get_current_user)):
    return list(standard_reports_service.ONBOARDING_STATUSES)
