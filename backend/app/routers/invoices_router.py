"""Invoices router (running ledger of charges per Case)."""
from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User
from app.schemas import InvoiceCreate, InvoiceRead, InvoiceUpdate
from app.services import invoice_service

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.get("", summary="List invoices")
def list_invoices(
    skip: int = 0, limit: int = 100,
    case_id: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    response: Response = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = invoice_service.list_invoices(db, user, skip, limit, case_id, status, search)
    if response is not None:
        response.headers["X-Total-Count"] = str(total)
    return {"items": [InvoiceRead.model_validate(i) for i in items], "total": total}


@router.get("/{invoice_id}", response_model=InvoiceRead)
def get_invoice(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return invoice_service.get_invoice(db, invoice_id, user)


@router.post("", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
def create_invoice(data: InvoiceCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return invoice_service.create_invoice(db, data, user)


@router.patch("/{invoice_id}", response_model=InvoiceRead)
def update_invoice(
    invoice_id: int, data: InvoiceUpdate,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    return invoice_service.update_invoice(db, invoice_id, data, user)


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invoice(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    invoice_service.delete_invoice(db, invoice_id, user)
    return None
