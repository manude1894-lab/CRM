"""Countries master router (BRD §17) — every country drop-down reads this list; Admin adds to it."""
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user, require_admin
from app.models import User
from app.schemas.country import CountryCreate, CountryRead
from app.services import countries_service

router = APIRouter(prefix="/countries", tags=["Countries"])


@router.get("", response_model=List[CountryRead])
def list_countries(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return countries_service.list_countries(db)


@router.post("", response_model=CountryRead, status_code=status.HTTP_201_CREATED)
def create_country(data: CountryCreate, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return countries_service.create_country(db, data)
