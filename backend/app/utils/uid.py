"""Utility: generate next UID strings like LEAD-0001, OPP-0015, etc."""
from sqlalchemy.orm import Session
from sqlalchemy import func


def next_uid(db: Session, model, uid_column: str, prefix: str, padding: int = 4) -> str:
    """Compute the next sequential UID based on existing max id in the table."""
    max_id = db.query(func.max(model.id)).scalar() or 0
    next_num = max_id + 1
    return f"{prefix}-{str(next_num).zfill(padding)}"
