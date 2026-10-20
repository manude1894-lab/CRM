"""Client document folder (BRD §14): upload, link, download, remove."""
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User
from app.schemas import DocumentRead
from app.schemas.document import ClientFolder, LinkDocumentCreate
from app.schemas.common import OptionalReason
from app.services import document_service

router = APIRouter(tags=["Documents"])


@router.get("/accounts/{account_id}/documents", response_model=List[DocumentRead])
def list_account_documents(account_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return document_service.list_for_account(db, account_id, user)


@router.get("/accounts/{account_id}/folder", response_model=ClientFolder, summary="Client document folder")
def client_folder(account_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return document_service.client_folder(db, account_id, user)


@router.post("/accounts/{account_id}/documents", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def upload_account_document(
    account_id: int,
    file: UploadFile = File(...),
    category: str = Form("Other"),
    notes: Optional[str] = Form(None),
    party_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return document_service.create_for_account(db, account_id, file, category, user, notes=notes, party_id=party_id)


@router.post("/accounts/{account_id}/documents/link", response_model=DocumentRead, status_code=status.HTTP_201_CREATED,
             summary="File a link (e.g. SharePoint) instead of a file")
def add_account_document_link(account_id: int, data: LinkDocumentCreate, db: Session = Depends(get_db),
                              user: User = Depends(get_current_user)):
    return document_service.create_link_for_account(db, account_id, data.category, data.url, data.title, user, notes=data.notes, party_id=data.party_id)


@router.get("/documents/{document_id}/download")
def download_document(document_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    data, filename, content_type = document_service.stream_content(db, document_id, user)
    return Response(
        content=data,
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.post("/documents/{document_id}/remove", status_code=status.HTTP_204_NO_CONTENT,
             summary="Remove a document from the folder (kept on record, shown in the folder history)")
def remove_document(document_id: int, data: OptionalReason = OptionalReason(), db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    document_service.delete(db, document_id, user, data.reason)
    return None
