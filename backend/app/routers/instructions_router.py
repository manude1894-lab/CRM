"""Instructions router (per-entity service-request tracker)."""
from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.auth.dependencies import get_current_user, require_admin
from app.models import User
from app.schemas import InstructionCreate, InstructionRead, InstructionUpdate
from app.schemas.case import ImportRequest
from app.services import instruction_service, engagement_service

router = APIRouter(prefix="/instructions", tags=["Instructions"])


@router.get("", summary="List instructions")
def list_instructions(
    skip: int = 0, limit: int = 100,
    case_id: Optional[int] = None,
    account_id: Optional[int] = None,
    status: Optional[str] = None,
    instruction_type: Optional[str] = None,
    search: Optional[str] = None,
    response: Response = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = instruction_service.list_instructions(
        db, user, skip, limit, case_id, status, instruction_type, search, account_id=account_id,
    )
    if response is not None:
        response.headers["X-Total-Count"] = str(total)
    return {"items": [InstructionRead.model_validate(i) for i in items], "total": total}


@router.post("/import", summary="Import open service requests from CSV rows (dry run first) — Admin")
def import_service_requests(body: ImportRequest, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return engagement_service.import_service_requests(db, user, body.rows, body.dry_run)


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


@router.delete("/{instruction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_instruction(instruction_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    instruction_service.delete_instruction(db, instruction_id, user)
    return None
