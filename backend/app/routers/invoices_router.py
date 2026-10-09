"""Invoices router — the Invoice module (Triam BRD mark-up §16). Rules live in invoice_service."""
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.schemas import DocumentRead
from app.schemas.invoice import InvoiceCreate, InvoicePaid, InvoiceRaise, InvoiceRead, InvoiceRequest, InvoiceUpdate, invoice_read
from app.services import invoice_service

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.get("", summary="List invoices")
def list_invoices(
    skip: int = 0, limit: int = 100,
    case_id: Optional[int] = None, account_id: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    response: Response = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = invoice_service.list_invoices(db, user, skip, limit, case_id, status, search, account_id)
    if response is not None:
        response.headers["X-Total-Count"] = str(total)
    return {"items": [invoice_read(i, db) for i in items], "total": total}


@router.get("/{invoice_id}", response_model=InvoiceRead)
def get_invoice(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return invoice_read(invoice_service.get_invoice(db, invoice_id, user), db)


@router.post("/request", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED,
             summary="RM / Sales: request an invoice (instruction to Accounts)")
def request_invoice(data: InvoiceRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return invoice_read(invoice_service.request_invoice(db, data, user), db)


@router.post("", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED, summary="Accounts: enter an invoice directly")
def create_invoice(data: InvoiceCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return invoice_read(invoice_service.create_invoice(db, data, user), db)


@router.post("/{invoice_id}/raise", response_model=InvoiceRead, summary="Accounts: record Invoice No, Date, Currency, Amount")
def raise_invoice(invoice_id: int, data: InvoiceRaise, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return invoice_read(invoice_service.raise_invoice(db, invoice_id, data, user), db)


@router.post("/{invoice_id}/paid", response_model=InvoiceRead, summary="Accounts: record the payment")
def mark_paid(invoice_id: int, data: InvoicePaid, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return invoice_read(invoice_service.mark_paid(db, invoice_id, data.paid_date, user), db)


@router.get("/{invoice_id}/attachments", response_model=List[DocumentRead])
def list_attachments(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return invoice_service.attachments(db, invoice_id, user)


@router.post("/{invoice_id}/attachments", response_model=DocumentRead, status_code=status.HTTP_201_CREATED,
             summary="Attach a Pricing Approval (RM / Sales) or the Invoice (Accounts)")
def add_attachment(invoice_id: int, file: UploadFile = File(...), kind: str = Form(...),
                   db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return invoice_service.attach(db, invoice_id, file, kind, user)


@router.patch("/{invoice_id}", response_model=InvoiceRead)
def update_invoice(invoice_id: int, data: InvoiceUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return invoice_read(invoice_service.update_invoice(db, invoice_id, data, user), db)


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invoice(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    invoice_service.delete_invoice(db, invoice_id, user)
    return None
