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
    # Triam UAT 19-11-2026: the amendments, invoice and service request reports only for the roles named.
    return [{"key": k, "title": t} for k, t in standard_reports_service.available(user).items()]


@router.get("/standard/{key}", summary="Run a standard report")
def run_standard_report(key: str, days: Optional[int] = None, date_from: Optional[date] = None, date_to: Optional[date] = None,
                        status: Optional[str] = None, department_id: Optional[int] = None, entity: Optional[str] = None,
                        tag: Optional[str] = None, rm_id: Optional[int] = None, request_type: Optional[str] = None,
                        sr_type: Optional[str] = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return standard_reports_service.run(db, user, key, days, date_from, date_to, status, department_id, entity, tag, rm_id,
                                        request_type, sr_type)


def _filters_used(db: Session, **f) -> list:
    """The filters behind a downloaded report, in words, printed at the top of the file (Triam 23-11-2026)."""
    from app.models import Department
    from app.services.report_export_service import _shown
    out = []
    if f["days"] is not None:
        out.append(("Days", str(f["days"])))
    if f["date_from"] or f["date_to"]:
        out.append(("Period", f"{_shown(f['date_from'].isoformat()) if f['date_from'] else 'start'} to "
                              f"{_shown(f['date_to'].isoformat()) if f['date_to'] else 'today'}"))
    if f["status"]:
        out.append(("Status", f["status"]))
    if f["department_id"]:
        dept = db.get(Department, f["department_id"])
        out.append(("Department", dept.name if dept else str(f["department_id"])))
    if f["entity"]:
        out.append(("Triam entity", f["entity"]))
    if f["tag"]:
        out.append(("Client tag", f["tag"]))
    if f["rm_id"]:
        rm = db.get(User, f["rm_id"])
        out.append(("Anchor RM", rm.name if rm else str(f["rm_id"])))
    if f["request_type"]:
        out.append(("Request type", f["request_type"]))
    if f["sr_type"]:
        out.append(("Service request type", f["sr_type"]))
    return out


@router.get("/standard/{key}/export", summary="Download a standard report as Excel (xlsx) or PDF")
def export_standard_report(key: str, format: str = "xlsx", days: Optional[int] = None, date_from: Optional[date] = None,
                           date_to: Optional[date] = None, status: Optional[str] = None, department_id: Optional[int] = None,
                           entity: Optional[str] = None, tag: Optional[str] = None, rm_id: Optional[int] = None,
                           request_type: Optional[str] = None, sr_type: Optional[str] = None,
                           db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not has_permission(user, REPORT_EXPORT):
        raise HTTPException(status_code=403, detail="Downloading reports isn't enabled for you. Ask the Administrator.")
    if format not in FORMATS:
        raise HTTPException(status_code=400, detail="Format must be xlsx or pdf")
    report = standard_reports_service.run(db, user, key, days, date_from, date_to, status, department_id, entity, tag, rm_id,
                                          request_type, sr_type)
    media_type, build = FORMATS[format]
    content = build(report, user, _filters_used(db, days=days, date_from=date_from, date_to=date_to, status=status,
                                                department_id=department_id, entity=entity, tag=tag, rm_id=rm_id,
                                                request_type=request_type, sr_type=sr_type))
    log_event(db, "report_export", f"{report['title']} downloaded as {'Excel' if format == 'xlsx' else 'PDF'} "
              f"({len(report['rows'])} rows)", user_id=user.id, subject_type="Report",
              changes={"report": key, "format": format, "rows": len(report["rows"])})
    db.commit()
    name = report_export_service.filename(report, format)
    return Response(content=content, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/onboarding-statuses", summary="Statuses the client onboarding report can be filtered by")
def onboarding_statuses(user: User = Depends(get_current_user)):
    return list(standard_reports_service.ONBOARDING_STATUSES)
