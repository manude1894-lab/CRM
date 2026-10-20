"""Service Requests router (BRD §15) — requests on approved clients, by Triam entity."""
from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User
from app.schemas import InstructionCreate, InstructionRead, InstructionUpdate
from app.schemas.common import CancelRequest
from app.services import instruction_service

router = APIRouter(prefix="/instructions", tags=["Service Requests"])


@router.get("", summary="List service requests")
def list_instructions(
    skip: int = 0, limit: int = 100,
    account_id: Optional[int] = None,
    status: Optional[str] = None,
    instruction_type: Optional[str] = None,
    search: Optional[str] = None,
    response: Response = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = instruction_service.list_instructions(
        db, user, skip, limit, status, instruction_type, search, account_id=account_id,
    )
    if response is not None:
        response.headers["X-Total-Count"] = str(total)
    return {"items": [InstructionRead.model_validate(i) for i in items], "total": total}


@router.get("/options", summary="Request types and statuses offered for a Triam entity")
def request_options(triam_entity: Optional[str] = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return instruction_service.options(db, triam_entity)


@router.get("/{instruction_id}", response_model=InstructionRead)
def get_instruction(instruction_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return instruction_service.get_instruction(db, instruction_id, user)


@router.post("", response_model=InstructionRead, status_code=status.HTTP_201_CREATED)
def create_instruction(data: InstructionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return instruction_service.create_instruction(db, data, user)


@router.patch("/{instruction_id}", response_model=InstructionRead)
def update_instruction(
    instruction_id: int, data: InstructionUpdate,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    return instruction_service.update_instruction(db, instruction_id, data, user)


@router.post("/{instruction_id}/cancel", status_code=status.HTTP_204_NO_CONTENT,
             summary="Cancel with a reason (records are never deleted)")
def cancel_instruction(instruction_id: int, data: CancelRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    instruction_service.cancel_instruction(db, instruction_id, data.reason, user)
    return None
