"""Client amendments (BRD v1.1 §13 "Existing Client Maintenance", §15 maker-checker).

Once a client is approved, its live record changes only through Compliance:

    Amend client ──> Draft (maker saves sections / parties as usual; nothing touches the live record)
                       │ Submit (mandatory checklist must still be complete)
                       v
                    Pending (client locked for further amendments) ──Approve──> changes applied
                       │ Reject (reason + explanation) / Withdraw
                       v
                    a new Draft holding the same changes, so the maker can fix and resubmit

A draft stores the staged edits in ApprovalRequest.payload:
    {"account": {field: json value, ...},
     "parties": [{"op": "create", "temp_id": -1, "data": {...}},
                 {"op": "update", "party_id": 7, "data": {...}},
                 {"op": "delete", "party_id": 9}]}

Every save replays the whole draft on the live objects inside the transaction, runs the same
validation as a direct save, captures the result and rolls back. Approval replays it once more and
commits, so the checker approves exactly what they were shown and the audit trail records each field.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.audit import log_event
from app.auth.permissions import has_permission
from app.models import Account, AccountParty, ApprovalRequest, ApprovalStatus, User
from app.schemas.account import AccountRead, AccountUpdate
from app.schemas.account_party import AccountPartyCreate, AccountPartyRead, AccountPartyUpdate
from app.services import account_party_service, account_service, client_workflow_service as wf
from app.services import master_service, notification_service

TYPE = "client_amendment"
# Statuses in which the profile is "approved" and therefore changes only through an amendment.
AMENDABLE = (wf.APPROVED, wf.ACTIVE, wf.INACTIVE, wf.MARKED_EXIT)
OPEN = (ApprovalStatus.DRAFT.value, ApprovalStatus.PENDING.value)

# Read-only/system fields that never appear as an amendment line.
_IGNORED = {"id", "account_uid", "client_id", "created_at", "updated_at", "profile_status", "status_updated_at",
            "status_updated_by_id", "next_aml_review_date", "total_invoiced_amount", "case_count", "is_pep",
            "account_id"}

_LABELS = {
    "company_name": "Client Name", "search_name": "Unique Search Name", "account_type": "Client Type",
    "spoc_id": "Anchor RM", "non_anchor_rm_ids": "Non-anchor RMs", "anchor_entity": "Anchor Triam Entity",
    "non_anchor_entities": "Non-anchor Entities", "registration_number": "Incorporation Certificate No.",
    "license_number": "License Number", "country": "Country of Incorporation", "trn_vat_number": "TRN / VAT No.",
    "corp_tax_registration_number": "Corp Tax Registration No.", "financial_year_end": "Financial Year End",
    "risk_rating": "CDD/AML Risk Level", "aml_classification": "AML Classification", "edd_reason": "Reason for EDD",
    "kyc_verified_by": "KYC Verification performed by", "cdd_completion_date": "CDD Completion Date",
    "engagement_letter_valid_until": "Engagement Letter Valid Until", "services_obtained": "Services Obtained",
    "effective_ownership_percent": "Effective Ownership %", "party_role": "Role", "full_name": "Full Name",
    "mobile_number": "Contact Mobile", "mobile_country_code": "Mobile Country Code", "email": "Email",
    "regulator_name": "Name of Regulator", "is_regulated": "Is entity regulated",
    "corp_tax_registered": "Corporate Tax Registered", "has_introducer": "Introducer",
    "regulatory_license_expiry_date": "Current regulatory license expiry",
}


def _label(field: str) -> str:
    return _LABELS.get(field) or field.replace("_", " ").strip().capitalize()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _client_label(acc: Account) -> str:
    return f"{acc.company_name} ({acc.client_id or acc.account_uid})"


def is_amendable(acc: Account) -> bool:
    return acc.profile_status in AMENDABLE


def open_request(db: Session, account_id: int) -> Optional[ApprovalRequest]:
    return (db.query(ApprovalRequest)
            .filter(ApprovalRequest.account_id == account_id, ApprovalRequest.request_type == TYPE,
                    ApprovalRequest.status.in_(OPEN))
            .order_by(ApprovalRequest.id.desc()).first())


def _empty() -> dict:
    return {"account": {}, "parties": []}


# ─── Replay / preview / diff ────────────────────────────────────────────────

def _replay(db: Session, acc: Account, payload: dict, user: User) -> dict[int, AccountParty]:
    """Apply the staged edits to the live objects (not committed). Returns temp_id -> new party."""
    fields = payload.get("account") or {}
    if fields:
        account_service.apply_update(db, acc, AccountUpdate(**fields), user)
    temp: dict[int, AccountParty] = {}
    by_id = {p.id: p for p in acc.parties}
    for op in payload.get("parties") or []:
        if op["op"] == "create":
            p = AccountParty(**AccountPartyCreate(**op["data"]).model_dump())
            acc.parties.append(p)
            account_party_service.validate_party(acc, p)
            temp[op["temp_id"]] = p
        elif op["op"] == "update":
            p = by_id.get(op["party_id"])
            if p is None:
                raise HTTPException(status_code=409, detail="A party in this amendment no longer exists on the client")
            for k, v in AccountPartyUpdate(**op["data"]).model_dump(exclude_unset=True).items():
                setattr(p, k, v)
            account_party_service.validate_party(acc, p)
        elif op["op"] == "delete":
            p = by_id.get(op["party_id"])
            if p is not None:
                acc.parties.remove(p)
    if acc.account_type != "Individual":
        acc.is_pep = any(p.is_pep for p in acc.parties)
    db.flush()
    return temp


def _account_json(acc: Account) -> dict:
    return AccountRead.model_validate(acc).model_dump(mode="json")


def _party_json(p: AccountParty, temp_id: Optional[int] = None) -> dict:
    out = AccountPartyRead.model_validate(p).model_dump(mode="json")
    if temp_id is not None:
        out["id"] = temp_id
    out["amendment"] = "added" if temp_id is not None else None
    return out


def _state(acc: Account, temp: Optional[dict] = None) -> dict:
    reverse = {id(p): t for t, p in (temp or {}).items()}
    return {"account": _account_json(acc),
            "parties": [_party_json(p, reverse.get(id(p))) for p in acc.parties]}


def _user_name(db: Session, uid) -> Optional[str]:
    u = db.get(User, uid) if isinstance(uid, int) else None
    return u.name if u else uid


def _show(db: Session, field: str, value):
    if value in (None, "", []):
        return None
    if field in ("spoc_id", "owner_id"):
        return _user_name(db, value)
    if field == "non_anchor_rm_ids" and isinstance(value, list):
        return ", ".join(str(_user_name(db, v)) for v in value)
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    if isinstance(value, dict):
        return ", ".join(str(v) for v in value.values() if v) or None
    return value


def _blank(v) -> bool:
    """None, "", [] and an address block whose lines are all empty all mean 'nothing entered'."""
    if isinstance(v, dict):
        return all(_blank(x) for x in v.values())
    return v in (None, "", [])


def _same(a, b) -> bool:
    if _blank(a) and _blank(b):
        return True
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except Exception:
        return a == b


def _diff(db: Session, before: dict, after: dict) -> dict:
    """Field-level before/after, in the shape the Compliance review screen shows."""
    account = [{"field": f, "label": _label(f), "old": _show(db, f, before["account"].get(f)), "new": _show(db, f, v)}
               for f, v in after["account"].items()
               if f not in _IGNORED and not _same(before["account"].get(f), v)]
    old_parties = {p["id"]: p for p in before["parties"]}
    new_parties = {p["id"]: p for p in after["parties"]}
    parties = []
    for pid, p in new_parties.items():
        name = p.get("full_name")
        if pid not in old_parties:
            parties.append({"action": "added", "name": name, "role": p.get("party_role"),
                            "changes": [{"field": f, "label": _label(f), "old": None, "new": _show(db, f, v)}
                                        for f, v in p.items() if f not in _IGNORED | {"amendment"} and not _blank(v) and v is not False]})
        else:
            old = old_parties[pid]
            changed = [{"field": f, "label": _label(f), "old": _show(db, f, old.get(f)), "new": _show(db, f, v)}
                       for f, v in p.items() if f not in _IGNORED | {"amendment"} and not _same(old.get(f), v)]
            if changed:
                parties.append({"action": "changed", "name": name, "role": p.get("party_role"), "changes": changed})
    for pid, p in old_parties.items():
        if pid not in new_parties:
            parties.append({"action": "removed", "name": p.get("full_name"), "role": p.get("party_role"), "changes": []})
    return {"account": account, "parties": parties, "count": len(account) + len(parties)}


def _simulate(db: Session, acc: Account, payload: dict, user: User, check_mandatory: bool = False) -> tuple[dict, dict, list]:
    """Replay on the live record, capture before/after, then roll everything back."""
    before = _state(acc)
    try:
        temp = _replay(db, acc, payload, user)
        after = _state(acc, temp)
        missing = account_service.missing_mandatory(acc) if check_mandatory else []
    finally:
        db.rollback()
    return before, after, missing


def _prune(payload: dict, before: dict) -> None:
    """Drop staged account values that are back to what the live record already holds."""
    live = before["account"]
    for f in [f for f, v in payload["account"].items() if f in live and _same(live[f], v)]:
        del payload["account"][f]


# ─── Draft handling ─────────────────────────────────────────────────────────

def _assert_access(db: Session, acc: Account, user: User) -> None:
    if not wf._can_see(db, acc, user):
        raise HTTPException(status_code=403, detail="Access denied")


def start(db: Session, acc: Account, user: User) -> ApprovalRequest:
    """BRD §13 — the explicit 'Amend' option on an approved client."""
    _assert_access(db, acc, user)
    wf.assert_editable(acc)
    if not is_amendable(acc):
        raise HTTPException(status_code=409, detail="Only an approved client is amended. Before approval, edit the profile directly.")
    req = open_request(db, acc.id)
    if req is not None:
        if req.status == ApprovalStatus.DRAFT.value and req.maker_id == user.id:
            return req
        who = req.maker.name if req.maker else "another user"
        raise HTTPException(status_code=409, detail=(f"An amendment by {who} is already awaiting Compliance approval"
                                                     if req.status == ApprovalStatus.PENDING.value
                                                     else f"{who} is already amending this client"))
    req = ApprovalRequest(account_id=acc.id, request_type=TYPE, status=ApprovalStatus.DRAFT.value,
                          maker_id=user.id, payload=_empty())
    db.add(req)
    db.flush()
    log_event(db, "amend_start", f"Amendment started on {_client_label(acc)}", subject_type="Account",
              subject_id=acc.id, account_id=acc.id, changes={"request_id": req.id})
    db.commit()
    return req


def _draft_for_edit(db: Session, acc: Account, user: User) -> ApprovalRequest:
    req = open_request(db, acc.id)
    if req is None:
        raise HTTPException(status_code=409, detail="This client is approved. Use 'Amend client' to start an amendment; changes go to Compliance for approval.")
    if req.status == ApprovalStatus.PENDING.value:
        raise HTTPException(status_code=409, detail="An amendment to this client is awaiting Compliance approval. It is locked until it is approved, rejected or withdrawn.")
    if req.maker_id != user.id:
        who = req.maker.name if req.maker else "another user"
        raise HTTPException(status_code=409, detail=f"{who} is already amending this client")
    return req


def _stage(db: Session, acc: Account, user: User, mutate) -> tuple[dict, object]:
    req = _draft_for_edit(db, acc, user)
    req_id = req.id
    payload = copy.deepcopy(req.payload or _empty())
    result = mutate(payload)
    before, after, _ = _simulate(db, acc, payload, user)  # raises (and rolls back) if invalid
    _prune(payload, before)
    req = db.get(ApprovalRequest, req_id)
    req.payload = payload
    db.commit()
    return after, result


def stage_account_update(db: Session, acc: Account, data: AccountUpdate, user: User) -> dict:
    fields = data.model_dump(mode="json", exclude_unset=True)
    after, _ = _stage(db, acc, user, lambda payload: payload["account"].update(fields))
    return after["account"]


def stage_party_create(db: Session, acc: Account, data: AccountPartyCreate, user: User) -> dict:
    def mutate(payload):
        temp_id = min([op.get("temp_id", 0) for op in payload["parties"]] + [0]) - 1
        payload["parties"].append({"op": "create", "temp_id": temp_id, "data": data.model_dump(mode="json")})
        return temp_id
    after, temp_id = _stage(db, acc, user, mutate)
    return next(p for p in after["parties"] if p["id"] == temp_id)


def stage_party_update(db: Session, acc: Account, party_id: int, data: AccountPartyUpdate, user: User) -> dict:
    fields = data.model_dump(mode="json", exclude_unset=True)

    def mutate(payload):
        ops = payload["parties"]
        if party_id < 0:
            op = next((o for o in ops if o["op"] == "create" and o["temp_id"] == party_id), None)
            if op is None:
                raise HTTPException(status_code=404, detail="Party not found in this amendment")
            op["data"].update(fields)
            return
        if party_id not in {p.id for p in acc.parties} or any(o["op"] == "delete" and o["party_id"] == party_id for o in ops):
            raise HTTPException(status_code=404, detail="Party not found")
        op = next((o for o in ops if o["op"] == "update" and o["party_id"] == party_id), None)
        if op is None:
            ops.append({"op": "update", "party_id": party_id, "data": fields})
        else:
            op["data"].update(fields)
    after, _ = _stage(db, acc, user, mutate)
    return next(p for p in after["parties"] if p["id"] == party_id)


def stage_party_delete(db: Session, acc: Account, party_id: int, user: User) -> None:
    def mutate(payload):
        ops = payload["parties"]
        if party_id < 0:
            payload["parties"] = [o for o in ops if not (o["op"] == "create" and o["temp_id"] == party_id)]
            return
        if party_id not in {p.id for p in acc.parties}:
            raise HTTPException(status_code=404, detail="Party not found")
        payload["parties"] = [o for o in ops if o.get("party_id") != party_id] + [{"op": "delete", "party_id": party_id}]
    _stage(db, acc, user, mutate)


def my_draft_preview(db: Session, acc: Account, user: User) -> Optional[dict]:
    """The client as the maker's open draft would leave it (None if they have no draft)."""
    req = open_request(db, acc.id)
    if req is None or req.status != ApprovalStatus.DRAFT.value or req.maker_id != user.id:
        return None
    _, after, _ = _simulate(db, acc, req.payload or _empty(), user)
    return after


def view(db: Session, acc: Account, user: User) -> dict:
    """Everything the client screen needs about amendments: the open request, its diff, the staged
    view for the maker, the last decision and which actions this user may take."""
    _assert_access(db, acc, user)
    req = open_request(db, acc.id)
    approver = has_permission(user, "client.approve")
    out = {"amendable": is_amendable(acc) and acc.profile_status != wf.EXITED, "request": None, "diff": None,
           "preview": None, "previous": None, "actions": []}
    if req is not None:
        out["request"] = req
        if req.status == ApprovalStatus.DRAFT.value:
            before, after, _ = _simulate(db, acc, req.payload or _empty(), user)
            out["diff"] = _diff(db, before, after)
            if req.maker_id == user.id:
                out["preview"] = after
                out["actions"] = ["submit", "discard"]
            if req.previous_request_id:
                out["previous"] = db.get(ApprovalRequest, req.previous_request_id)
        else:  # Pending
            out["diff"] = req.changes
            if approver and req.maker_id != user.id:
                out["actions"] += ["approve", "reject"]
            if req.maker_id == user.id or approver:
                out["actions"].append("withdraw")
    elif out["amendable"]:
        out["actions"] = ["start"]
    return out


# ─── Maker / checker actions ────────────────────────────────────────────────

def _approvers(db: Session) -> list[User]:
    return wf._approvers(db)


def submit(db: Session, acc: Account, user: User, comment: Optional[str] = None) -> ApprovalRequest:
    req = _draft_for_edit(db, acc, user)
    req_id, payload = req.id, req.payload or _empty()
    before, after, missing = _simulate(db, acc, payload, user, check_mandatory=True)
    diff = _diff(db, before, after)
    if not diff["count"]:
        raise HTTPException(status_code=400, detail="There are no changes to submit")
    if missing:
        raise HTTPException(status_code=400, detail="The amended profile would be incomplete: " + ", ".join(m["label"] for m in missing))
    req = db.get(ApprovalRequest, req_id)
    req.status, req.submitted_at = ApprovalStatus.PENDING.value, _now()
    req.maker_comment = (comment or "").strip() or None
    req.changes, req.snapshot = diff, before
    log_event(db, "amend_submit", f"Amendment to {_client_label(acc)} submitted to Compliance ({diff['count']} change(s))",
              subject_type="Account", subject_id=acc.id, account_id=acc.id, changes={"request_id": req.id})
    db.commit()
    for u in _approvers(db):
        if u.id != user.id:
            notification_service.notify_user(db, u.id, f"{user.name} submitted an amendment to {_client_label(acc)} for Compliance approval.", "amendment_submitted")
    return req


def _pending(db: Session, acc: Account) -> ApprovalRequest:
    req = open_request(db, acc.id)
    if req is None or req.status != ApprovalStatus.PENDING.value:
        raise HTTPException(status_code=409, detail="There is no amendment awaiting approval on this client")
    return req


def _assert_checker(db: Session, acc: Account, user: User, req: ApprovalRequest) -> None:
    _assert_access(db, acc, user)
    if not has_permission(user, "client.approve"):
        raise HTTPException(status_code=403, detail="Needs an approver (CO / MLRO)")
    if req.maker_id == user.id:
        raise HTTPException(status_code=403, detail="You submitted this amendment — another approver must review it")


def approve(db: Session, acc: Account, user: User, comment: Optional[str] = None) -> ApprovalRequest:
    req = _pending(db, acc)
    _assert_checker(db, acc, user, req)
    maker = req.maker.name if req.maker else None
    try:
        _replay(db, acc, req.payload or _empty(), user)
    except HTTPException as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"The amendment can no longer be applied: {e.detail}. Reject it so the maker can update it.")
    req.status, req.checker_id, req.decided_at = ApprovalStatus.APPROVED.value, user.id, _now()
    req.reason_text = (comment or "").strip() or None
    log_event(db, "amend_approve", f"Amendment to {_client_label(acc)} approved and applied (made by {maker})",
              subject_type="Account", subject_id=acc.id, account_id=acc.id,
              changes={"request_id": req.id, "maker": maker, "comment": req.reason_text, "diff": req.changes})
    db.commit()
    if req.maker_id:
        notification_service.notify_user(db, req.maker_id, f"{user.name} approved your amendment to {_client_label(acc)}.", "amendment_approved")
    return req


def _reopen_for_maker(db: Session, req: ApprovalRequest) -> None:
    """After a rejection or withdrawal the maker continues from the same changes."""
    db.add(ApprovalRequest(account_id=req.account_id, request_type=TYPE, status=ApprovalStatus.DRAFT.value,
                           maker_id=req.maker_id, payload=copy.deepcopy(req.payload), previous_request_id=req.id))


def reject(db: Session, acc: Account, user: User, reason_code: str, reason_text: str) -> ApprovalRequest:
    req = _pending(db, acc)
    _assert_checker(db, acc, user, req)
    reason_text = (reason_text or "").strip()
    if not reason_code:
        raise HTTPException(status_code=400, detail="Choose a rejection reason")
    master_service.assert_valid(db, "rejection_reason", reason_code, "Rejection reason")
    if len(reason_text) < wf.MIN_REJECT_TEXT:
        raise HTTPException(status_code=400, detail=f"Explain what needs fixing (at least {wf.MIN_REJECT_TEXT} characters) so the maker can act on it")
    req.status, req.checker_id, req.decided_at = ApprovalStatus.REJECTED.value, user.id, _now()
    req.reason_code, req.reason_text = reason_code, reason_text
    _reopen_for_maker(db, req)
    log_event(db, "amend_reject", f"Amendment to {_client_label(acc)} rejected: {reason_code} — {reason_text}",
              subject_type="Account", subject_id=acc.id, account_id=acc.id,
              changes={"request_id": req.id, "reason_code": reason_code, "reason_text": reason_text})
    db.commit()
    if req.maker_id:
        notification_service.notify_user(db, req.maker_id, f"{user.name} rejected your amendment to {_client_label(acc)}: {reason_code} — {reason_text}", "amendment_rejected")
    return req


def withdraw(db: Session, acc: Account, user: User) -> ApprovalRequest:
    req = _pending(db, acc)
    _assert_access(db, acc, user)
    if req.maker_id != user.id and not has_permission(user, "client.approve"):
        raise HTTPException(status_code=403, detail="Only the submitter or an approver can withdraw")
    req.status, req.decided_at = ApprovalStatus.WITHDRAWN.value, _now()
    _reopen_for_maker(db, req)
    log_event(db, "amend_withdraw", f"Amendment to {_client_label(acc)} withdrawn from Compliance", subject_type="Account",
              subject_id=acc.id, account_id=acc.id, changes={"request_id": req.id})
    db.commit()
    return req


def discard(db: Session, acc: Account, user: User) -> ApprovalRequest:
    req = _draft_for_edit(db, acc, user)
    req.status, req.decided_at = ApprovalStatus.DISCARDED.value, _now()
    log_event(db, "amend_discard", f"Draft amendment to {_client_label(acc)} discarded", subject_type="Account",
              subject_id=acc.id, account_id=acc.id, changes={"request_id": req.id})
    db.commit()
    return req
