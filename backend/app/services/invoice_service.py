"""Service layer: Invoice (running ledger of charges per Case)."""
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException
from typing import Optional

from app.models import Invoice, Case, User, UserRole
from app.schemas.invoice import InvoiceCreate, InvoiceUpdate


def _apply_rbac_filter(query, user: User):
    if user.role == UserRole.RM:
        query = query.join(Case, Invoice.case_id == Case.id).filter(Case.rm_id == user.id)
    return query


def list_invoices(
    db: Session,
    user: User,
    skip: int = 0,
    limit: int = 100,
    case_id: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
) -> tuple[list[Invoice], int]:
    query = db.query(Invoice)
    query = _apply_rbac_filter(query, user)

    if case_id:
        query = query.filter(Invoice.case_id == case_id)
    if status:
        query = query.filter(Invoice.status == status)
    if search:
        pattern = f"%{search}%"
        query = query.join(Case, Invoice.case_id == Case.id).filter(or_(
            Case.company_name.ilike(pattern),
            Invoice.invoice_number.ilike(pattern),
            Invoice.description.ilike(pattern),
        ))

    total = query.count()
    items = query.order_by(Invoice.id.desc()).offset(skip).limit(limit).all()
    return items, total


def _get_case_for_write(db: Session, case_id: int, user: User) -> Case:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=400, detail="Case does not exist")
    if user.role == UserRole.RM and case.rm_id != user.id:
        raise HTTPException(status_code=403, detail="You don't own this case")
    return case


def get_invoice(db: Session, invoice_id: int, user: User) -> Invoice:
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    case = db.query(Case).filter(Case.id == inv.case_id).first()
    if user.role == UserRole.RM and case and case.rm_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return inv


def create_invoice(db: Session, data: InvoiceCreate, user: User) -> Invoice:
    _get_case_for_write(db, data.case_id, user)
    inv = Invoice(**data.model_dump())
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


def update_invoice(db: Session, invoice_id: int, data: InvoiceUpdate, user: User) -> Invoice:
    inv = get_invoice(db, invoice_id, user)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(inv, field, value)
    db.commit()
    db.refresh(inv)
    return inv


def delete_invoice(db: Session, invoice_id: int, user: User) -> None:
    inv = get_invoice(db, invoice_id, user)
    db.delete(inv)
    db.commit()
