"""Service layer: admin-managed master lists (BRD §18).

Also the single place other services call to validate that a stored value comes from an active
master list (BRD §4 "selection from the configured Triam Entity list", §18).
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import MasterItem, MASTER_LIST_TYPES
from app.schemas.master import MasterItemCreate, MasterItemUpdate


def _check_type(list_type: str) -> None:
    if list_type not in MASTER_LIST_TYPES:
        raise HTTPException(status_code=404, detail=f"Unknown master list '{list_type}'")


def list_items(db: Session, list_type: str, include_inactive: bool = False) -> list[MasterItem]:
    _check_type(list_type)
    q = db.query(MasterItem).filter(MasterItem.list_type == list_type)
    if not include_inactive:
        q = q.filter(MasterItem.is_active == True)  # noqa: E712
    return q.order_by(MasterItem.sort_order, MasterItem.label).all()


def get_item(db: Session, item_id: int) -> MasterItem:
    item = db.get(MasterItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Master item not found")
    return item


def create_item(db: Session, list_type: str, data: MasterItemCreate) -> MasterItem:
    _check_type(list_type)
    code = (data.code or data.label).strip()
    exists = db.query(MasterItem).filter(MasterItem.list_type == list_type, MasterItem.code == code).first()
    if exists:
        raise HTTPException(status_code=400, detail=f"'{code}' already exists in this list" + ("" if exists.is_active else " (inactive — reactivate it instead)"))
    if data.sort_order is None:
        last = db.query(MasterItem).filter(MasterItem.list_type == list_type).order_by(MasterItem.sort_order.desc()).first()
        sort_order = (last.sort_order + 10) if last else 10
    else:
        sort_order = data.sort_order
    item = MasterItem(list_type=list_type, code=code, label=data.label.strip(), sort_order=sort_order,
                      is_active=data.is_active, meta=data.meta)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_item(db: Session, item_id: int, data: MasterItemUpdate) -> MasterItem:
    """The code is immutable — records store it. Only label / order / active / meta change."""
    item = get_item(db, item_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


# ─── Validation used by other services ──────────────────────────────────────

def active_codes(db: Session, list_type: str) -> set[str]:
    rows = db.query(MasterItem.code).filter(MasterItem.list_type == list_type, MasterItem.is_active == True).all()  # noqa: E712
    return {r.code for r in rows}


def assert_valid(db: Session, list_type: str, values, field_label: str) -> None:
    """Raise 400 if any value isn't an active code of the list. Empty / None values pass.

    Lists with no rows at all are not enforced (lets a fresh DB without seeds keep working)."""
    if values is None or values == "" or values == []:
        return
    codes = active_codes(db, list_type)
    if not codes:
        return
    if isinstance(values, str):
        values = [values]
    bad = [v for v in values if v not in codes]
    if bad:
        raise HTTPException(status_code=400, detail=f"{field_label}: '{', '.join(bad)}' is not in the active {MASTER_LIST_TYPES[list_type]} list")
