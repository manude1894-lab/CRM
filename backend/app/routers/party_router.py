"""Directors & Shareholders registers router (per Case / BVI entity)."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User
from app.schemas import (
    DirectorCreate, DirectorRead, DirectorUpdate,
    ShareholderCreate, ShareholderRead, ShareholderUpdate,
    UBOCreate, UBORead, UBOUpdate,
)
from app.services import party_service

router = APIRouter(tags=["Directors & Shareholders"])


# ─── Directors ───────────────────────────────────────────────────────────
@router.get("/cases/{case_id}/directors", response_model=List[DirectorRead])
def list_directors(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return party_service.list_directors(db, case_id)


@router.post("/cases/{case_id}/directors", response_model=DirectorRead, status_code=status.HTTP_201_CREATED)
def create_director(case_id: int, data: DirectorCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return party_service.create_director(db, case_id, data, user)


@router.patch("/directors/{director_id}", response_model=DirectorRead)
def update_director(director_id: int, data: DirectorUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return party_service.update_director(db, director_id, data, user)


@router.delete("/directors/{director_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_director(director_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    party_service.delete_director(db, director_id, user)
    return None


# ─── Shareholders ────────────────────────────────────────────────────────
@router.get("/cases/{case_id}/shareholders", response_model=List[ShareholderRead])
def list_shareholders(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return party_service.list_shareholders(db, case_id)


@router.post("/cases/{case_id}/shareholders", response_model=ShareholderRead, status_code=status.HTTP_201_CREATED)
def create_shareholder(case_id: int, data: ShareholderCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return party_service.create_shareholder(db, case_id, data, user)


@router.patch("/shareholders/{shareholder_id}", response_model=ShareholderRead)
def update_shareholder(shareholder_id: int, data: ShareholderUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return party_service.update_shareholder(db, shareholder_id, data, user)


@router.delete("/shareholders/{shareholder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shareholder(shareholder_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    party_service.delete_shareholder(db, shareholder_id, user)
    return None


# ─── UBOs ────────────────────────────────────────────────────────────────
@router.get("/cases/{case_id}/ubos", response_model=List[UBORead])
def list_ubos(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return party_service.list_ubos(db, case_id)


@router.post("/cases/{case_id}/ubos", response_model=UBORead, status_code=status.HTTP_201_CREATED)
def create_ubo(case_id: int, data: UBOCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return party_service.create_ubo(db, case_id, data, user)


@router.patch("/ubos/{ubo_id}", response_model=UBORead)
def update_ubo(ubo_id: int, data: UBOUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return party_service.update_ubo(db, ubo_id, data, user)


@router.delete("/ubos/{ubo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ubo(ubo_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    party_service.delete_ubo(db, ubo_id, user)
    return None
