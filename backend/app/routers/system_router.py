"""System health for administrators (P7 go-live checks)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import require_admin
from app.database import get_db
from app.models import User
from app.services import security_service

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/health-checks", summary="Go-live security and configuration checks — Admin")
def health_checks(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return security_service.system_health(db)
