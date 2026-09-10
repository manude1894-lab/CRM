"""Document generation router — templated PDFs saved into the case document store."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User
from app.schemas import DocumentRead, DocumentTemplateInfo, DocumentGenerateRequest
from app.services import generation_service

router = APIRouter(tags=["Document Generation"])


@router.get("/document-templates", response_model=List[DocumentTemplateInfo])
def list_document_templates(user: User = Depends(get_current_user)):
    return generation_service.list_templates()


@router.get("/cases/{case_id}/document-templates/{code}/prefill")
def prefill_document_template(code: str, case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return generation_service.prefill(db, case_id, code, user)


@router.post("/cases/{case_id}/documents/generate", response_model=DocumentRead)
def generate_document(case_id: int, body: DocumentGenerateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return generation_service.generate(db, case_id, body.template_code, body.params, user)
