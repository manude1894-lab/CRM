"""Cases router."""
from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.auth.dependencies import get_current_user, require_admin
from app.models import User
from app.schemas import CaseCreate, CaseRead, CaseUpdate, CaseStageChangeRequest
from app.services import case_service

router = APIRouter(prefix="/cases", tags=["Cases"])


@router.get("", summary="List cases (paginated, filterable)")
def list_cases(
    skip: int = 0, limit: int = 100,
    search: Optional[str] = None,
    stage: Optional[str] = None,
    status_filter: Optional[str] = None,
    rm_id: Optional[int] = None,
    response: Response = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = case_service.list_cases(
        db, user, skip, limit, search, stage, status_filter, rm_id,
    )
    if response is not None:
        response.headers["X-Total-Count"] = str(total)
    return {"items": [CaseRead.model_validate(i) for i in items], "total": total}


@router.get("/{case_id}", response_model=CaseRead)
def get_case(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return case_service.get_case(db, case_id, user)


@router.post("", response_model=CaseRead, status_code=status.HTTP_201_CREATED)
def create_case(data: CaseCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return case_service.create_case(db, data, user)


@router.patch("/{case_id}", response_model=CaseRead)
def update_case(
    case_id: int, data: CaseUpdate,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    return case_service.update_case(db, case_id, data, user)


@router.post("/{case_id}/stage", response_model=CaseRead, summary="Move case to a new stage")
def change_stage(
    case_id: int, body: CaseStageChangeRequest,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    return case_service.change_stage(db, case_id, body.stage, user)


@router.post("/{case_id}/invoice/raise", response_model=CaseRead, summary="Raise invoice (requires CDD approved)")
def raise_invoice(case_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return case_service.raise_invoice(db, case_id, user)


@router.post("/{case_id}/invoice/mark-paid", response_model=CaseRead, summary="Mark invoice paid")
def mark_invoice_paid(case_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return case_service.mark_invoice_paid(db, case_id, user)


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(case_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    case_service.delete_case(db, case_id, user)
    return None
