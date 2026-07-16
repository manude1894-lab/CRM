"""Reports router: PDF downloads."""
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session
from datetime import date

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User
from app.services import dashboard_service, case_service
from app.reports import (
    case_stage_summary_pdf,
    case_details_pdf,
    compliance_calendar_pdf,
    rm_ops_performance_pdf,
)

router = APIRouter(prefix="/reports", tags=["Reports"])


def _pdf_response(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/case-stage-summary", summary="Case Stage Summary PDF")
def case_stage_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    dashboard = dashboard_service.build_dashboard(db, user)
    pdf = case_stage_summary_pdf(dashboard)
    return _pdf_response(pdf, f"case_stage_summary_{date.today().isoformat()}.pdf")


@router.get("/case-details", summary="Case Details PDF")
def case_details(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cases, _ = case_service.list_cases(db, user, skip=0, limit=1000)
    pdf = case_details_pdf(cases)
    return _pdf_response(pdf, f"case_details_{date.today().isoformat()}.pdf")


@router.get("/compliance-calendar", summary="Compliance Calendar PDF")
def compliance_calendar(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    dashboard = dashboard_service.build_dashboard(db, user)
    pdf = compliance_calendar_pdf(dashboard)
    return _pdf_response(pdf, f"compliance_calendar_{date.today().isoformat()}.pdf")


@router.get("/rm-ops-performance", summary="RM/Ops Performance PDF")
def rm_ops_performance(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    dashboard = dashboard_service.build_dashboard(db, user)
    pdf = rm_ops_performance_pdf(dashboard)
    return _pdf_response(pdf, f"rm_ops_performance_{date.today().isoformat()}.pdf")
