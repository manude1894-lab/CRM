"""Service layer: Document uploads.

Bytes are stored in Document.content (Postgres bytea, deferred). The only code that
reads/writes those bytes lives here — the swap point for a future volume/S3 backend.
"""
import re
from datetime import date

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Document, DocumentCategory, Case, CaseDocument, Instruction, User, UserRole

# Allow-list — reject anything not here (executables, html, svg, ...).
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/png", "image/jpeg", "image/gif", "image/tiff",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain", "text/csv",
    "application/octet-stream",  # some browsers send this for .xlsx/.doc — extension is re-checked below
}
_ALLOWED_EXT = {
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".tif", ".tiff",
    ".doc", ".docx", ".xls", ".xlsx", ".txt", ".csv",
}
_VALID_CATEGORIES = {c.value for c in DocumentCategory}


def _safe_filename(name: str) -> str:
    name = (name or "file").replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^A-Za-z0-9._ \-()]", "_", name).strip() or "file"
    return name[:255]


def _ext(name: str) -> str:
    return name[name.rfind("."):].lower() if "." in name else ""


def _case_for_read(db: Session, case_id: int, user: User) -> Case:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if user.role == UserRole.RM and case.rm_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return case


def list_for_case(db: Session, case_id: int, user: User) -> list[Document]:
    _case_for_read(db, case_id, user)
    return (
        db.query(Document)
        .filter(Document.case_id == case_id)
        .order_by(Document.id.desc())
        .all()
    )


def create(
    db: Session,
    case_id: int,
    upload: UploadFile,
    category: str,
    user: User,
    case_document_id: int | None = None,
    instruction_id: int | None = None,
    notes: str | None = None,
) -> Document:
    _case_for_read(db, case_id, user)

    if category not in _VALID_CATEGORIES:
        category = DocumentCategory.OTHER.value

    filename = _safe_filename(upload.filename)
    if _ext(filename) not in _ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"File type not allowed: {filename}")
    if upload.content_type and upload.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Content type not allowed: {upload.content_type}")

    data = upload.file.read()
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"File exceeds the {settings.MAX_UPLOAD_MB} MB limit")

    if case_document_id is not None:
        cd = db.query(CaseDocument).filter(CaseDocument.id == case_document_id).first()
        if not cd or cd.cdd_record.case_id != case_id:
            raise HTTPException(status_code=400, detail="Checklist item does not belong to this case")
    if instruction_id is not None:
        ins = db.query(Instruction).filter(Instruction.id == instruction_id).first()
        if not ins or ins.case_id != case_id:
            raise HTTPException(status_code=400, detail="Instruction does not belong to this case")

    doc = Document(
        case_id=case_id,
        case_document_id=case_document_id,
        instruction_id=instruction_id,
        category=category,
        filename=filename,
        content_type=upload.content_type,
        size_bytes=len(data),
        content=data,
        uploaded_by_id=user.id,
        notes=(notes or None),
    )
    db.add(doc)

    # Attaching a file to a checklist item marks it received.
    if case_document_id is not None:
        cd = db.query(CaseDocument).filter(CaseDocument.id == case_document_id).first()
        if cd and not cd.received:
            cd.received = True
            cd.received_date = date.today()

    db.commit()
    db.refresh(doc)
    return doc


def get(db: Session, document_id: int, user: User) -> Document:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    _case_for_read(db, doc.case_id, user)
    return doc


def stream_content(db: Session, document_id: int, user: User) -> tuple[bytes, str, str]:
    doc = get(db, document_id, user)
    return doc.content, doc.filename, doc.content_type or "application/octet-stream"


def delete(db: Session, document_id: int, user: User) -> None:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if user.role != UserRole.ADMIN and doc.uploaded_by_id != user.id:
        raise HTTPException(status_code=403, detail="Only the uploader or an Admin can delete this document")
    db.delete(doc)
    db.commit()
