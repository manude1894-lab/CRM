"""Dashboard & analytics router."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", summary="Full dashboard payload (KPIs + charts)")
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return dashboard_service.build_dashboard(db, user)
