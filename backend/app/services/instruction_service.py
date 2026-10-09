"""Service layer: Service Requests (the Instruction Tracker, generalised to every client — BRD §17).

A request belongs to a client; linking a BVI case is optional. The Vistra dates only apply to
BVI work routed through Vistra.
"""
from sqlalchemy.orm import Session
from sqlalchemy import or_, select
from fastapi import HTTPException
from typing import Optional

from app.models import Account, Instruction, Case, User, UserRole
from app.schemas.instruction import InstructionCreate, InstructionUpdate
from app.services import access_control, master_service


def _apply_rbac_filter(db: Session, query, user: User):
    if user.role != UserRole.RM:
        return query
    acc_clause = access_control.account_visibility_clause(db, user)
    visible_accounts = select(Account.id).where(acc_clause) if acc_clause is not None else select(Account.id)
    visible_cases = select(Case.id).where(access_control.rm_visibility_clause(user))
    return query.filter(or_(Instruction.account_id.in_(visible_accounts), Instruction.case_id.in_(visible_cases)))


def list_instructions(
    db: Session,
    user: User,
    skip: int = 0,
    limit: int = 100,
    case_id: Optional[int] = None,
    status: Optional[str] = None,
    instruction_type: Optional[str] = None,
    search: Optional[str] = None,
    account_id: Optional[int] = None,
) -> tuple[list[Instruction], int]:
    query = _apply_rbac_filter(db, db.query(Instruction), user)

    if account_id:
        query = query.filter(Instruction.account_id == account_id)
    if case_id:
        query = query.filter(Instruction.case_id == case_id)
    if status:
        query = query.filter(Instruction.status == status)
    if instruction_type:
        query = query.filter(Instruction.instruction_type == instruction_type)
    if search:
        pattern = f"%{search}%"
        query = (query.outerjoin(Case, Instruction.case_id == Case.id)
                 .outerjoin(Account, Instruction.account_id == Account.id)
                 .filter(or_(
                     Case.company_name.ilike(pattern),
                     Account.company_name.ilike(pattern),
                     Account.client_id.ilike(pattern),
                     Instruction.instruction_type.ilike(pattern),
                     Instruction.comments.ilike(pattern),
                     Instruction.invoice_reference.ilike(pattern),
                 )))

    total = query.count()
    items = query.order_by(Instruction.id.desc()).offset(skip).limit(limit).all()
    return items, total


def _can_see(db: Session, inst: Instruction, user: User) -> bool:
    if inst.account_id:
        acc = db.get(Account, inst.account_id)
        if acc and access_control.user_can_access_account(db, acc, user):
            return True
    if inst.case_id:
        case = db.get(Case, inst.case_id)
        if case and access_control.user_can_access_case(case, user):
            return True
    return False


def get_instruction(db: Session, instruction_id: int, user: User) -> Instruction:
    inst = db.query(Instruction).filter(Instruction.id == instruction_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Service request not found")
    if not _can_see(db, inst, user):
        raise HTTPException(status_code=403, detail="Access denied")
    return inst


def _resolve_links(db: Session, account_id: Optional[int], case_id: Optional[int], user: User) -> tuple[Optional[int], Optional[int]]:
    case = None
    if case_id:
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise HTTPException(status_code=400, detail="Case does not exist")
        if not access_control.user_can_access_case(case, user):
            raise HTTPException(status_code=403, detail="You don't have access to this case")
    account_id = account_id or (case.account_id if case else None)
    if account_id:
        acc = db.get(Account, account_id)
        if not acc:
            raise HTTPException(status_code=400, detail="Client does not exist")
        if not access_control.user_can_access_account(db, acc, user):
            raise HTTPException(status_code=403, detail="You don't have access to this client")
        if case and case.account_id and case.account_id != acc.id:
            raise HTTPException(status_code=400, detail="The case belongs to a different client")
    if not account_id and not case:
        raise HTTPException(status_code=400, detail="Choose the client (and optionally the case) for this service request")
    return account_id, case_id


def create_instruction(db: Session, data: InstructionCreate, user: User) -> Instruction:
    account_id, case_id = _resolve_links(db, data.account_id, data.case_id, user)
    master_service.assert_valid(db, "service_request_type", data.instruction_type, "Request type")
    inst = Instruction(**data.model_dump(exclude={"account_id", "case_id"}), account_id=account_id, case_id=case_id)
    db.add(inst)
    db.commit()
    db.refresh(inst)
    return inst


def update_instruction(db: Session, instruction_id: int, data: InstructionUpdate, user: User) -> Instruction:
    from app.models import Invoice

    inst = get_instruction(db, instruction_id, user)
    payload = data.model_dump(exclude_unset=True)
    if "instruction_type" in payload and payload["instruction_type"] != inst.instruction_type:
        master_service.assert_valid(db, "service_request_type", payload["instruction_type"], "Request type")
    for field, value in payload.items():
        setattr(inst, field, value)

    # Triam mark-up §16: a completed, charged service request is an instruction to Accounts to invoice it.
    new_invoice = None
    if payload.get("status") == "Completed" and inst.charge_amount and not inst.invoice_id and inst.account_id:
        from datetime import datetime, timezone
        new_invoice = Invoice(account_id=inst.account_id, case_id=inst.case_id, description=inst.instruction_type,
                              amount=inst.charge_amount, status="Requested", requested_by_id=user.id,
                              requested_at=datetime.now(timezone.utc))
        db.add(new_invoice)
        db.flush()
        inst.invoice_id = new_invoice.id

    db.commit()
    db.refresh(inst)
    if new_invoice is not None:
        from app.services import invoice_service, notification_service
        for u in invoice_service._accounts_team(db):
            if u.id != user.id:
                notification_service.notify_user(db, u.id, f"Invoice instruction: service request '{inst.instruction_type}' completed — "
                                                 f"{new_invoice.currency} {new_invoice.amount} to invoice.", "invoice_requested")
    return inst


def delete_instruction(db: Session, instruction_id: int, user: User) -> None:
    inst = get_instruction(db, instruction_id, user)
    db.delete(inst)
    db.commit()
