"""Service layer: Service Requests (BRD §15).

Each request is handled by one of the client's Triam entities; that entity decides the request types
and statuses offered (Triam's "Service Requests - Triam Entities" list, kept as master data).

Requests open once Compliance has approved the client (Triam, 12-11-2026): the Final approval is not
awaited. Invoicing follows Triam's Invoice Box template (11-11-2026): the RM records the charge
(excluding VAT) with its currency, any payment received and any service provider, and Submit sends the
request to the Accountant's queue as an invoice instruction. The Accountant records the invoice and
sends it to the RM (invoice_service.raise_invoice).
"""
from datetime import date, datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import or_, select
from fastapi import HTTPException
from decimal import Decimal
from typing import Optional

from app.models import Account, Instruction, InstructionStatus, User, UserRole
from app.schemas.instruction import InstructionCreate, InstructionUpdate
from app.services import access_control, master_service


def _apply_rbac_filter(db: Session, query, user: User):
    if user.role != UserRole.RM:
        return query
    acc_clause = access_control.account_visibility_clause(db, user)
    if acc_clause is None:
        return query
    return query.filter(Instruction.account_id.in_(select(Account.id).where(acc_clause)))


def list_instructions(
    db: Session,
    user: User,
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    instruction_type: Optional[str] = None,
    search: Optional[str] = None,
    account_id: Optional[int] = None,
) -> tuple[list[Instruction], int]:
    query = _apply_rbac_filter(db, db.query(Instruction), user)

    if account_id:
        query = query.filter(Instruction.account_id == account_id)
    if status:
        query = query.filter(Instruction.status == status)
    if instruction_type:
        query = query.filter(Instruction.instruction_type == instruction_type)
    if search:
        pattern = f"%{search}%"
        query = (query.join(Account, Instruction.account_id == Account.id)
                 .filter(or_(
                     Account.company_name.ilike(pattern),
                     Account.client_id.ilike(pattern),
                     Instruction.instruction_type.ilike(pattern),
                     Instruction.other_description.ilike(pattern),
                     Instruction.comments.ilike(pattern),
                 )))

    total = query.count()
    items = query.order_by(Instruction.id.desc()).offset(skip).limit(limit).all()
    return items, total


def _can_see(db: Session, inst: Instruction, user: User) -> bool:
    acc = db.get(Account, inst.account_id)
    return bool(acc and access_control.user_can_access_account(db, acc, user))


def get_instruction(db: Session, instruction_id: int, user: User) -> Instruction:
    inst = db.query(Instruction).filter(Instruction.id == instruction_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Service request not found")
    if not _can_see(db, inst, user):
        raise HTTPException(status_code=403, detail="Access denied")
    return inst


def _client_for(db: Session, account_id: Optional[int], user: User) -> Account:
    if not account_id:
        raise HTTPException(status_code=400, detail="Choose the client for this service request")
    acc = db.get(Account, account_id)
    if not acc:
        raise HTTPException(status_code=400, detail="Client does not exist")
    if not access_control.user_can_access_account(db, acc, user):
        raise HTTPException(status_code=403, detail="You don't have access to this client")
    return acc


SERVICEABLE = {"Approved", "Active", "Inactive", "Marked for Exit"}
AWAITING = "Awaiting Approval"

# ─── Request types and statuses by Triam entity (Triam's "Service Requests - Triam Entities" list) ──
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


def _client_entities(acc: Account) -> list[str]:
    return [e for e in [acc.anchor_entity, *(acc.non_anchor_entities or [])] if e]


def _resolve_entity(db: Session, entity: Optional[str], acc: Account) -> Optional[str]:
    served_by = _client_entities(acc)
    if not entity:
        entity = served_by[0] if served_by else None
    if entity:
        master_service.assert_valid(db, "triam_entity", entity, "Triam entity")
        if served_by and entity not in served_by:
            raise HTTPException(status_code=400, detail=f"{entity} doesn't serve {acc.company_name}. Choose one of {', '.join(served_by)}.")
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


def takes_requests(acc: Account) -> bool:
    """BRD §8; Triam 12-11-2026: a client takes service requests once Compliance has approved it, which is
    when its Client ID is issued, without waiting for the Final approval. A client rejected at the Final
    stage takes none until approved again; its existing requests and invoices stay as they are."""
    return acc.profile_status in SERVICEABLE or (acc.profile_status == AWAITING and bool(acc.client_id))


def _assert_client_serviceable(acc: Account) -> None:
    if not takes_requests(acc):
        raise HTTPException(status_code=400, detail=f"{acc.company_name} is {acc.profile_status}. "
                                                    "Service requests open once Compliance has approved the client.")


def _currency(value: Optional[str], label: str) -> Optional[str]:
    from app.services.invoice_service import CURRENCIES
    if value is None:
        return None
    value = value.upper()
    if value not in CURRENCIES:
        raise HTTPException(status_code=400, detail=f"{label}: currency must be one of {', '.join(CURRENCIES)}")
    return value


def _tidy_invoicing(inst: Instruction) -> None:
    """Each amount carries a currency (the charge's when none is given); no service provider, no details."""
    inst.charge_currency = _currency(inst.charge_currency, "Charge to the client") or "AED"
    inst.amount_paid_currency = (_currency(inst.amount_paid_currency, "Amount paid by the client")
                                 or (inst.charge_currency if inst.amount_paid is not None else None))
    inst.govt_authority_currency = (_currency(inst.govt_authority_currency, "Amount payable to Reg./Govt Auth")
                                    or (inst.charge_currency if inst.govt_authority_amount is not None else None))
    if not inst.service_provider_involved:
        inst.service_provider_name = inst.service_provider_amount = inst.service_provider_currency = None
    else:
        inst.service_provider_name = (inst.service_provider_name or "").strip() or None
        inst.service_provider_currency = (_currency(inst.service_provider_currency, "Amount payable to the service provider")
                                          or (inst.charge_currency if inst.service_provider_amount is not None else None))


def _invoice_open(db: Session, inst: Instruction) -> bool:
    """The request is with the Accountant: it has an invoice that hasn't been cancelled."""
    from app.models import Invoice
    inv = db.get(Invoice, inst.invoice_id) if inst.invoice_id else None
    return inv is not None and inv.status != "Cancelled"


def _invoice_notes(inst: Instruction) -> str:
    from app.utils.dates import dmy
    lines = [f"Service request #{inst.id}. Charge excludes VAT."]
    if inst.amount_paid is not None:
        when = f" on {dmy(inst.payment_received_date)}" if inst.payment_received_date else ""
        lines.append(f"Client has paid {inst.amount_paid_currency} {inst.amount_paid}{when}.")
    if inst.govt_authority_amount is not None:
        lines.append(f"Payable to Reg./Govt Auth: {inst.govt_authority_currency} {inst.govt_authority_amount}.")
    if inst.service_provider_involved:
        amount = (f", {inst.service_provider_currency} {inst.service_provider_amount} payable"
                  if inst.service_provider_amount is not None else "")
        lines.append(f"Service provider: {inst.service_provider_name or '—'}{amount}.")
    return " ".join(lines)


def _send_for_invoicing(db: Session, inst: Instruction, acc: Account, user: User) -> None:
    """Submit: an invoice instruction for the charge goes to the Accountant's queue (they are notified)."""
    from app.models import Invoice
    from app.services import invoice_service
    inv = Invoice(account_id=inst.account_id, description=inst.other_description or inst.instruction_type,
                  amount=inst.charge_amount, currency=inst.charge_currency or "AED", status=invoice_service.DRAFT,
                  requested_by_id=user.id, notes=_invoice_notes(inst))
    db.add(inv)
    db.flush()
    inst.invoice_id, inst.submitted_at, inst.submitted_by_id = inv.id, datetime.now(timezone.utc), user.id
    invoice_service._send_to_accounts(db, inv, acc, user)  # commits and notifies the Accountants


def submit_instruction(db: Session, instruction_id: int, user: User) -> Instruction:
    """The RM sends the request to the Accountant's queue, whatever the request's own status."""
    inst = get_instruction(db, instruction_id, user)
    if inst.status == InstructionStatus.CANCELLED.value:
        raise HTTPException(status_code=400, detail="A dropped request can't be submitted")
    if _invoice_open(db, inst):
        raise HTTPException(status_code=400, detail="This request is already with the Accountant")
    acc = db.get(Account, inst.account_id)
    _assert_client_serviceable(acc)
    if not inst.charge_amount:
        raise HTTPException(status_code=400, detail="Enter the charge to the client before submitting")
    if inst.service_provider_involved and not inst.service_provider_name:
        raise HTTPException(status_code=400, detail="Enter the name of the service provider")
    _send_for_invoicing(db, inst, acc, user)
    db.refresh(inst)
    return inst


def create_instruction(db: Session, data: InstructionCreate, user: User) -> Instruction:
    acc = _client_for(db, data.account_id, user)
    _assert_client_serviceable(acc)
    master_service.assert_valid(db, "service_request_type", data.instruction_type, "Request type")
    inst = Instruction(**data.model_dump(exclude={"account_id", "triam_entity"}), account_id=acc.id,
                       triam_entity=_resolve_entity(db, data.triam_entity, acc))
    _check_type_and_status(db, inst, status_given=bool(data.status))
    _tidy_invoicing(inst)
    db.add(inst)
    db.commit()
    db.refresh(inst)
    return inst


def update_instruction(db: Session, instruction_id: int, data: InstructionUpdate, user: User) -> Instruction:
    inst = get_instruction(db, instruction_id, user)
    payload = data.model_dump(exclude_unset=True)
    if payload.get("status") == InstructionStatus.CANCELLED.value or inst.status == InstructionStatus.CANCELLED.value:
        raise HTTPException(status_code=400, detail="Use Cancel (with a reason) to drop a request; a dropped request can't be changed")
    if "instruction_type" in payload and payload["instruction_type"] != inst.instruction_type:
        master_service.assert_valid(db, "service_request_type", payload["instruction_type"], "Request type")
    if "triam_entity" in payload:
        payload["triam_entity"] = _resolve_entity(db, payload["triam_entity"], db.get(Account, inst.account_id))
    # Once with the Accountant, the charge stands; cancelling the invoice reopens it.
    if _invoice_open(db, inst) and _changes_charge(inst, payload):
        raise HTTPException(status_code=400, detail="The charge is already with the Accountant. Ask them to cancel the invoice to change it.")
    for field, value in payload.items():
        setattr(inst, field, value)
    try:
        _tidy_invoicing(inst)
    except HTTPException:
        db.rollback()
        raise
    if {"instruction_type", "triam_entity", "status", "other_description"} & set(payload):
        try:
            _check_type_and_status(db, inst, status_given="status" in payload)
        except HTTPException:
            db.rollback()
            raise

    # A request marked Completed without a completion date is completed today.
    if payload.get("status") == "Completed" and not inst.date_completed:
        inst.date_completed = date.today()

    # BRD §16: a completed, charged request not yet submitted goes to the Accountant as if submitted.
    acc = db.get(Account, inst.account_id)
    if payload.get("status") == "Completed" and inst.charge_amount and not _invoice_open(db, inst) and takes_requests(acc):
        _send_for_invoicing(db, inst, acc, user)
    else:
        db.commit()
    db.refresh(inst)
    return inst


def _changes_charge(inst: Instruction, payload: dict) -> bool:
    if "charge_amount" in payload and payload["charge_amount"] is not None and inst.charge_amount is not None:
        if Decimal(str(payload["charge_amount"])) != Decimal(str(inst.charge_amount)):
            return True
    elif "charge_amount" in payload and (payload["charge_amount"] is None) != (inst.charge_amount is None):
        return True
    return bool(payload.get("charge_currency")) and payload["charge_currency"].upper() != (inst.charge_currency or "AED")


def cancel_instruction(db: Session, instruction_id: int, reason: str, user: User) -> None:
    """Service requests are never deleted: they are cancelled with a reason and stay on record."""
    inst = get_instruction(db, instruction_id, user)
    if inst.status in (InstructionStatus.COMPLETED.value, InstructionStatus.CANCELLED.value):
        raise HTTPException(status_code=400, detail=f"A {inst.status.lower()} service request can't be cancelled")
    inst.status, inst.cancel_reason = InstructionStatus.CANCELLED.value, reason.strip()
    db.commit()
