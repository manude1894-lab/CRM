"""System health for administrators (P7 go-live checks), and error reports from the browser."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import require_admin
from app.database import get_db
from app.models import User
from app.services import alert_service, security_service
from app.services.rate_limit import error_reports
from app.utils.net import client_ip

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/health-checks", summary="Go-live security and configuration checks — Admin")
def health_checks(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return security_service.system_health(db)


class ClientError(BaseModel):
    where: str = Field(..., max_length=300)  # the page, e.g. "Dashboard"
    error_type: str = Field("Error", max_length=100)
    message: str = Field("", max_length=1000)
    stack: Optional[str] = Field(None, max_length=4000)


@router.post("/client-errors", status_code=202, summary="A crash in the browser, reported for the support desk")
def client_error(body: ClientError, request: Request):
    """Review 22-11-2026 (package 6). Open without sign-in (a page can fail before it), limited per address."""
    address = client_ip(request)
    if error_reports.blocked(address):
        raise HTTPException(status_code=429, detail="Too many error reports")
    error_reports.record(address)
    ref = alert_service.report("browser", body.where, body.error_type, body.message, extra=body.stack)
    return {"reference": ref}
