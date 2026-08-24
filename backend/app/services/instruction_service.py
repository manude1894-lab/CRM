"""Service layer: Instruction (per-entity service-request tracker)."""
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException
from typing import Optional

from app.models import Instruction, Case, User, UserRole
from app.schemas.instruction import InstructionCreate, InstructionUpdate


def _apply_rbac_filter(query, user: User):
    if user.role == UserRole.RM:
        query = query.join(Case, Instruction.case_id == Case.id).filter(Case.rm_id == user.id)
    return query


def list_instructions(
    db: Session,
    user: User,
    skip: int = 0,
    limit: int = 100,
    case_id: Optional[int] = None,
    status: Optional[str] = None,
    instruction_type: Optional[str] = None,
    search: Optional[str] = None,
) -> tuple[list[Instruction], int]:
    query = db.query(Instruction)
    query = _apply_rbac_filter(query, user)

    if case_id:
        query = query.filter(Instruction.case_id == case_id)
    if status:
        query = query.filter(Instruction.status == status)
    if instruction_type:
        query = query.filter(Instruction.instruction_type == instruction_type)
    if search:
        pattern = f"%{search}%"
        query = query.join(Case, Instruction.case_id == Case.id).filter(or_(
            Case.company_name.ilike(pattern),
            Instruction.instruction_type.ilike(pattern),
            Instruction.comments.ilike(pattern),
            Instruction.invoice_reference.ilike(pattern),
        ))

    total = query.count()
    items = query.order_by(Instruction.id.desc()).offset(skip).limit(limit).all()
    return items, total


def _get_case_for_write(db: Session, case_id: int, user: User) -> Case:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=400, detail="Case does not exist")
    if user.role == UserRole.RM and case.rm_id != user.id:
        raise HTTPException(status_code=403, detail="You don't own this case")
    return case


def get_instruction(db: Session, instruction_id: int, user: User) -> Instruction:
    inst = db.query(Instruction).filter(Instruction.id == instruction_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Instruction not found")
    case = db.query(Case).filter(Case.id == inst.case_id).first()
    if user.role == UserRole.RM and case and case.rm_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return inst


def create_instruction(db: Session, data: InstructionCreate, user: User) -> Instruction:
    _get_case_for_write(db, data.case_id, user)
    inst = Instruction(**data.model_dump())
    db.add(inst)
    db.commit()
    db.refresh(inst)
    return inst


def update_instruction(db: Session, instruction_id: int, data: InstructionUpdate, user: User) -> Instruction:
    inst = get_instruction(db, instruction_id, user)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(inst, field, value)
    db.commit()
    db.refresh(inst)
    return inst


def delete_instruction(db: Session, instruction_id: int, user: User) -> None:
    inst = get_instruction(db, instruction_id, user)
    db.delete(inst)
    db.commit()
