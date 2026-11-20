"""Reports router: the BRD §20 standard reports, shown on screen and downloaded as Excel or PDF by the users the
Administrator allows (Triam UAT 19-11-2026)."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.audit import log_event
from app.auth.dependencies import get_current_user
from app.auth.permissions import REPORT_EXPORT, has_permission
from app.database import get_db
from app.models import User
from app.services import report_export_service, standard_reports_service

router = APIRouter(prefix="/reports", tags=["Reports"])

FORMATS = {
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", report_export_service.to_xlsx),
    "pdf": ("application/pdf", report_export_service.to_pdf),
}


@router.get("/standard", summary="Standard reports available")
def standard_reports(user: User = Depends(get_current_user)):
    return [{"key": k, "title": t} for k, t in standard_reports_service.REPORTS.items()]


@router.get("/standard/{key}", summary="Run a standard report")
def run_standard_report(key: str, days: Optional[int] = None, date_from: Optional[date] = None, date_to: Optional[date] = None,
                        status: Optional[str] = None, department_id: Optional[int] = None,
                        db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return standard_reports_service.run(db, user, key, days, date_from, date_to, status, department_id)


@router.get("/standard/{key}/export", summary="Download a standard report as Excel (xlsx) or PDF")
def export_standard_report(key: str, format: str = "xlsx", days: Optional[int] = None, date_from: Optional[date] = None,
                           date_to: Optional[date] = None, status: Optional[str] = None, department_id: Optional[int] = None,
                           db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not has_permission(user, REPORT_EXPORT):
        raise HTTPException(status_code=403, detail="Downloading reports isn't enabled for you. Ask the Administrator.")
    if format not in FORMATS:
        raise HTTPException(status_code=400, detail="Format must be xlsx or pdf")
    report = standard_reports_service.run(db, user, key, days, date_from, date_to, status, department_id)
    media_type, build = FORMATS[format]
    content = build(report, user)
    log_event(db, "report_export", f"{report['title']} downloaded as {'Excel' if format == 'xlsx' else 'PDF'} "
              f"({len(report['rows'])} rows)", user_id=user.id, subject_type="Report",
              changes={"report": key, "format": format, "rows": len(report["rows"])})
    db.commit()
    name = report_export_service.filename(report, format)
    return Response(content=content, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/onboarding-statuses", summary="Statuses the client onboarding report can be filtered by")
def onboarding_statuses(user: User = Depends(get_current_user)):
    return list(standard_reports_service.ONBOARDING_STATUSES)
