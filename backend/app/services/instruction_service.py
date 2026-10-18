"""Service layer: Service Requests (the Instruction Tracker, generalised to every client — BRD §17).

A request belongs to a client; linking a BVI case is optional. The Vistra dates only apply to
BVI work routed through Vistra.
"""
from sqlalchemy.orm import Session
from sqlalchemy import or_, select
from fastapi import HTTPException
from typing import Optional

from app.models import Account, Instruction, InstructionStatus, Case, User, UserRole
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


SERVICEABLE = {"Approved", "Active", "Inactive", "Marked for Exit"}

# ─── Request types and statuses by Triam entity (Triam's Service Request list) ────────────────────
OTHER = "Other"
# Used only while the status master list is empty (e.g. a database that hasn't been seeded).
FALLBACK_STATUSES = ["Received", "Applied for service", "On Hold", "Completed", "Dropped"]


def _for_entity(items, entity: Optional[str]):
    """Items whose entity ticks include `entity`; an item with no entities ticked applies to all."""
    return [i for i in items if not (i.meta or {}).get("entities") or (entity and entity in i.meta["entities"])]


def options(db: Session, entity: Optional[str]) -> dict:
    """The request types and statuses offered for a Triam entity, in their configured order."""
    types = [i.code for i in _for_entity(master_service.list_items(db, "service_request_type"), entity)]
    rows = _for_entity(master_service.list_items(db, "service_request_status"), entity)
    statuses = ([{"code": s.code, "closed": bool((s.meta or {}).get("closed"))} for s in rows] if rows else
                [{"code": c, "closed": c in ("Completed", "Dropped")} for c in FALLBACK_STATUSES])
    return {"triam_entity": entity, "types": types, "statuses": statuses}


def _client_entities(acc: Optional[Account]) -> list[str]:
    if acc is None:
        return []
    return [e for e in [acc.anchor_entity, *(acc.non_anchor_entities or [])] if e]


def _resolve_entity(db: Session, entity: Optional[str], account_id: Optional[int], case_id: Optional[int]) -> Optional[str]:
    acc = db.get(Account, account_id) if account_id else None
    served_by = _client_entities(acc)
    if not entity:
        entity = served_by[0] if served_by else ("TBVI" if case_id else None)
    if entity:
        master_service.assert_valid(db, "triam_entity", entity, "Triam entity")
        if served_by and entity not in served_by:
            raise HTTPException(status_code=400, detail=f"{entity} doesn't serve {acc.company_name} — choose one of {', '.join(served_by)}")
    return entity


def _check_type_and_status(db: Session, inst: Instruction, status_given: bool) -> None:
    """The request type and status must belong to the request's entity; "Other" needs a description."""
    opts = options(db, inst.triam_entity)
    if opts["types"] and inst.instruction_type not in opts["types"]:
        raise HTTPException(status_code=400, detail=f"'{inst.instruction_type}' is not a request type for {inst.triam_entity or 'this entity'}")
    if inst.instruction_type == OTHER:
        if not (inst.other_description or "").strip():
            raise HTTPException(status_code=400, detail="Describe the request (up to 50 characters) when the type is Other")
        inst.other_description = inst.other_description.strip()
    else:
        inst.other_description = None
    codes = [s["code"] for s in opts["statuses"]]
    if not status_given:
        if not inst.status or inst.status not in codes:
            inst.status = next((s["code"] for s in opts["statuses"] if not s["closed"]), codes[0])
        return
    if inst.status == InstructionStatus.CANCELLED.value:
        raise HTTPException(status_code=400, detail="Use Cancel (with a reason) to drop a request")
    if inst.status not in codes:
        raise HTTPException(status_code=400, detail=f"'{inst.status}' is not a status for {inst.triam_entity or 'this entity'}")


def _assert_client_serviceable(db: Session, account_id) -> None:
    """Triam mark-up §8: a client is available for service requests once it is approved."""
    from app.models import Account
    acc = db.get(Account, account_id) if account_id else None
    if acc is not None and acc.profile_status not in SERVICEABLE:
        raise HTTPException(status_code=400, detail=f"{acc.company_name} is {acc.profile_status} — service requests open once the client is approved")


def create_instruction(db: Session, data: InstructionCreate, user: User) -> Instruction:
    account_id, case_id = _resolve_links(db, data.account_id, data.case_id, user)
    _assert_client_serviceable(db, account_id)
    master_service.assert_valid(db, "service_request_type", data.instruction_type, "Request type")
    inst = Instruction(**data.model_dump(exclude={"account_id", "case_id", "triam_entity"}), account_id=account_id, case_id=case_id,
                       triam_entity=_resolve_entity(db, data.triam_entity, account_id, case_id))
    _check_type_and_status(db, inst, status_given=bool(data.status))
    db.add(inst)
    db.commit()
    db.refresh(inst)
    return inst


def update_instruction(db: Session, instruction_id: int, data: InstructionUpdate, user: User) -> Instruction:
    from app.models import Invoice

    inst = get_instruction(db, instruction_id, user)
    payload = data.model_dump(exclude_unset=True)
    if payload.get("status") == InstructionStatus.CANCELLED.value or inst.status == InstructionStatus.CANCELLED.value:
        raise HTTPException(status_code=400, detail="Use Cancel (with a reason) to drop a request; a dropped request can't be changed")
    if "instruction_type" in payload and payload["instruction_type"] != inst.instruction_type:
        master_service.assert_valid(db, "service_request_type", payload["instruction_type"], "Request type")
    if "triam_entity" in payload:
        payload["triam_entity"] = _resolve_entity(db, payload["triam_entity"], inst.account_id, inst.case_id)
    for field, value in payload.items():
        setattr(inst, field, value)
    if {"instruction_type", "triam_entity", "status", "other_description"} & set(payload):
        try:
            _check_type_and_status(db, inst, status_given="status" in payload)
        except HTTPException:
            db.rollback()
            raise

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


def cancel_instruction(db: Session, instruction_id: int, reason: str, user: User) -> None:
    """Service requests are never deleted: they are cancelled with a reason and stay on record."""
    inst = get_instruction(db, instruction_id, user)
    if inst.status in (InstructionStatus.COMPLETED.value, InstructionStatus.CANCELLED.value):
        raise HTTPException(status_code=400, detail=f"A {inst.status.lower()} service request can't be cancelled")
    inst.status, inst.cancel_reason = InstructionStatus.CANCELLED.value, reason.strip()
    db.commit()
