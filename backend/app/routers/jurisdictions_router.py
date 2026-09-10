"""Jurisdictions router — the per-jurisdiction rules catalog (read-only)."""
from fastapi import APIRouter, Depends
from typing import List

from app.auth.dependencies import get_current_user
from app.models import User
from app.schemas.jurisdiction import JurisdictionInfo
from app import jurisdictions

router = APIRouter(tags=["Jurisdictions"])


@router.get("/jurisdictions", response_model=List[JurisdictionInfo])
def list_jurisdictions(user: User = Depends(get_current_user)):
    return jurisdictions.list_specs()
