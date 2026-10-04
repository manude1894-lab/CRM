"""Automatic audit trail (BRD §13 "audit trail preserves who made an amendment", §15 "all material
CRM activities and changes must be recorded").

An `after_flush` listener on every Session turns inserts / updates / deletes of audited models
into AuditLog rows, with field-level before/after values for updates.

Who did it: `get_current_user` stamps `session.info["user_id"]` (and the client IP) on the request's
DB session. Context variables can't be used — FastAPI runs sync dependencies and the endpoint in
separate threadpool calls, so a value set in the dependency would not reach the endpoint.

Import this module once at startup (app.main does) to register the listener.
"""
from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.models import AuditLog

# Model class name -> human label used in summaries.
AUDITED_MODELS = {
    "Account": "Client",
    "AccountParty": "Client party",
    "Document": "Document",
    "Case": "Case",
    "User": "User",
    "Role": "Role",
    "Department": "Department",
    "MasterItem": "Master item",
}

# Never written to the log: noise, binary blobs, secrets.
_SKIP_FIELDS = {"created_at", "updated_at", "content"}
_REDACT_FIELDS = {"hashed_password"}


def set_actor(session: Session, user_id: int | None, ip: str | None = None) -> None:
    """Record who is acting on this session; picked up by the listener for every row it writes."""
    session.info["user_id"] = user_id
    session.info["ip"] = ip


def _jsonable(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return "<binary>"
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return str(value)


def _account_id_for(obj) -> int | None:
    name = type(obj).__name__
    if name == "Account":
        return obj.id
    # Plain column attributes only — never trigger relationship loads inside a flush.
    return getattr(obj, "account_id", None)


def _label(obj) -> str:
    for attr in ("company_name", "full_name", "name", "label", "filename", "case_uid"):
        value = getattr(obj, attr, None)
        if isinstance(value, str) and value:
            return value
    return f"#{getattr(obj, 'id', '?')}"


def _column_keys(obj):
    return [c.key for c in inspect(obj).mapper.column_attrs if c.key not in _SKIP_FIELDS]


def _snapshot(obj) -> dict:
    out = {}
    state = inspect(obj)
    for key in _column_keys(obj):
        if key in state.unloaded:  # deferred / never loaded — don't force a load during flush
            continue
        value = getattr(obj, key)
        if value is None:
            continue
        out[key] = "<redacted>" if key in _REDACT_FIELDS else _jsonable(value)
    return out


def _diff(obj) -> dict:
    changes = {}
    state = inspect(obj)
    for key in _column_keys(obj):
        hist = state.attrs[key].history
        if not hist.has_changes():
            continue
        old = hist.deleted[0] if hist.deleted else None
        new = hist.added[0] if hist.added else None
        if old == new:
            continue
        if key in _REDACT_FIELDS:
            changes[key] = ["<redacted>", "<redacted>"]
        else:
            changes[key] = [_jsonable(old), _jsonable(new)]
    return changes


def _rows_for_flush(session: Session) -> list[dict]:
    actor = session.info.get("user_id")
    ip = session.info.get("ip")
    rows = []

    def row(obj, action, changes, summary):
        rows.append({
            "user_id": actor,
            "action": action,
            "subject_type": type(obj).__name__,
            "subject_id": getattr(obj, "id", None),
            "account_id": _account_id_for(obj),
            "changes": changes or None,
            "summary": summary[:500],
            "ip_address": ip,
        })

    for obj in session.new:
        label = AUDITED_MODELS.get(type(obj).__name__)
        if label:
            row(obj, "create", _snapshot(obj), f"{label} created: {_label(obj)}")
    for obj in session.dirty:
        label = AUDITED_MODELS.get(type(obj).__name__)
        if label and session.is_modified(obj, include_collections=False):
            changes = _diff(obj)
            if changes:
                row(obj, "update", changes, f"{label} updated: {_label(obj)} ({', '.join(sorted(changes))})")
    for obj in session.deleted:
        label = AUDITED_MODELS.get(type(obj).__name__)
        if label:
            row(obj, "delete", None, f"{label} deleted: {_label(obj)}")
    return rows


def _noop_set(target, value, oldvalue, initiator):
    return value


def _enable_old_values() -> None:
    """By default SQLAlchemy doesn't load a column's previous value when it's assigned on an expired
    object (e.g. after an earlier commit in the same request), so the diff would read
    "None -> new". `active_history=True` makes it load the old value first. Applied to the audited
    models' column attributes only, never to the document bytes."""
    import app.models as models
    for class_name in AUDITED_MODELS:
        cls = getattr(models, class_name)
        for prop in inspect(cls).column_attrs:
            if prop.key not in _SKIP_FIELDS:
                event.listen(getattr(cls, prop.key), "set", _noop_set, active_history=True, retval=True)


_enable_old_values()


@event.listens_for(Session, "after_flush")
def _write_audit_rows(session: Session, flush_context) -> None:
    rows = _rows_for_flush(session)
    if rows:
        # Core insert on the same connection/transaction: adding ORM objects inside after_flush
        # would re-enter the flush.
        session.connection().execute(AuditLog.__table__.insert(), rows)


def log_event(session: Session, action: str, summary: str, *, user_id: int | None = None,
              subject_type: str = "System", subject_id: int | None = None,
              account_id: int | None = None, changes: dict | None = None) -> None:
    """Explicit audit entry for things that aren't row changes (login, approval decisions, downloads).
    Caller commits."""
    session.add(AuditLog(
        user_id=user_id if user_id is not None else session.info.get("user_id"),
        action=action,
        subject_type=subject_type,
        subject_id=subject_id,
        account_id=account_id,
        changes=changes,
        summary=summary[:500],
        ip_address=session.info.get("ip"),
    ))
