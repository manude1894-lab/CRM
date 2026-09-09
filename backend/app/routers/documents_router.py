"""Document upload / download / delete."""
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User
from app.schemas import DocumentRead
from app.services import document_service

router = APIRouter(tags=["Documents"])


@router.get("/cases/{case_id}/documents", response_model=List[DocumentRead])
def list_documents(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return document_service.list_for_case(db, case_id, user)


@router.post("/cases/{case_id}/documents", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def upload_document(
    case_id: int,
    file: UploadFile = File(...),
    category: str = Form("Other"),
    case_document_id: Optional[int] = Form(None),
    instruction_id: Optional[int] = Form(None),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return document_service.create(
        db, case_id, file, category, user,
        case_document_id=case_document_id, instruction_id=instruction_id, notes=notes,
    )


@router.get("/documents/{document_id}/download")
def download_document(document_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    data, filename, content_type = document_service.stream_content(db, document_id, user)
    return Response(
        content=data,
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    document_service.delete(db, document_id, user)
    return None
