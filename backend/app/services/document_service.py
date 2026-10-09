"""Service layer: Document uploads.

Bytes are stored in Document.content (Postgres bytea, deferred). The only code that
reads/writes those bytes lives here — the swap point for a future volume/S3 backend.
"""
import re
from typing import Optional
from datetime import date

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Document, DocumentCategory, Case, CaseDocument, Instruction, User, UserRole
from app.services import access_control, master_service

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
# Built-in categories used by internal flows (CDD checklist, generated docs, filings). User-chosen
# categories come from the admin-managed "document_category" master list (BRD §16, §18).
_BUILTIN_CATEGORIES = {c.value for c in DocumentCategory}


def _normalise_category(db: Session, category: str) -> str:
    if category in _BUILTIN_CATEGORIES or category in master_service.active_codes(db, "document_category"):
        return category
    return DocumentCategory.OTHER.value


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
    if not access_control.user_can_access_case(case, user):
        raise HTTPException(status_code=403, detail="Access denied")
    return case


def _account_for_read(db: Session, account_id: int, user: User):
    from app.services import account_service  # local import avoids a circular import at module load
    return account_service.get_account(db, account_id, user)


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

    category = _normalise_category(db, category)

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


def list_for_account(db: Session, account_id: int, user: User) -> list[Document]:
    _account_for_read(db, account_id, user)
    return (
        db.query(Document)
        .filter(Document.account_id == account_id)
        .order_by(Document.id.desc())
        .all()
    )


def create_for_account(
    db: Session,
    account_id: int,
    upload: UploadFile,
    category: str,
    user: User,
    notes: str | None = None,
) -> Document:
    account = _account_for_read(db, account_id, user)
    from app.services import client_workflow_service
    client_workflow_service.assert_editable(account)  # BRD §12 — frozen while with the checker

    category = _normalise_category(db, category)

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

    doc = Document(
        account_id=account_id,
        category=category,
        filename=filename,
        content_type=upload.content_type,
        size_bytes=len(data),
        content=data,
        uploaded_by_id=user.id,
        notes=(notes or None),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def get(db: Session, document_id: int, user: User) -> Document:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.case_id is not None:
        _case_for_read(db, doc.case_id, user)
    else:
        _account_for_read(db, doc.account_id, user)
    return doc


def stream_content(db: Session, document_id: int, user: User) -> tuple[bytes, str, str]:
    doc = get(db, document_id, user)
    return doc.content, doc.filename, doc.content_type or "application/octet-stream"


def delete(db: Session, document_id: int, user: User) -> None:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.account_id is not None:
        _assert_client_document_removable(db, doc, user)
    elif user.role != UserRole.ADMIN and doc.uploaded_by_id != user.id:
        raise HTTPException(status_code=403, detail="Only the uploader or an Admin can delete this document")
    db.delete(doc)
    db.commit()


DRAFT, SUBMITTED, LOCKED = "Draft", "Submitted", "Locked"


def _client_document_stage(db: Session, account) -> str:
    """BRD §16 document stage, from the client's progress:
    Draft until the client is first submitted, Submitted after that, Locked once approved."""
    from app.models import ApprovalRequest
    from app.services import client_workflow_service as wf
    if account.profile_status in (wf.APPROVED, wf.ACTIVE, wf.INACTIVE, wf.MARKED_EXIT, wf.EXITED):
        return LOCKED
    submitted = db.query(ApprovalRequest.id).filter(ApprovalRequest.account_id == account.id,
                                                    ApprovalRequest.request_type == "client_profile").first() is not None
    return SUBMITTED if submitted or account.profile_status == wf.AWAITING else DRAFT


def client_document_removal(db: Session, doc: Document, account, user: User) -> tuple[bool, str, Optional[str]]:
    """(may this user remove it, document stage, why not). BRD §16:
    - Draft: the uploader (or an Admin) may remove a document;
    - Submitted: only an Approver-level user (document.delete_submitted) may remove it;
    - Locked (client approved): documents can no longer be removed from the client folder."""
    from app.auth.permissions import has_permission
    from app.services import client_workflow_service as wf
    stage = _client_document_stage(db, account)
    if stage == LOCKED:
        return False, stage, "The client is approved — its documents can no longer be removed. Upload a newer version instead."
    if account.profile_status == wf.AWAITING:
        return False, stage, "The client is with Compliance for review; documents can't be changed until it is decided."
    if stage == SUBMITTED:
        if has_permission(user, "document.delete_submitted"):
            return True, stage, None
        return False, stage, "This client has been submitted for approval — only an Approver can remove its documents."
    if user.role == UserRole.ADMIN or doc.uploaded_by_id == user.id:
        return True, stage, None
    return False, stage, "Only the person who uploaded it (or an Admin) can remove it."


def _assert_client_document_removable(db: Session, doc: Document, user: User) -> None:
    account = _account_for_read(db, doc.account_id, user)
    from app.services import client_workflow_service as wf
    wf.assert_editable(account)
    allowed, stage, reason = client_document_removal(db, doc, account, user)
    if not allowed:
        raise HTTPException(status_code=409 if stage == LOCKED else 403, detail=reason)


def client_folder(db: Session, account_id: int, user: User) -> dict:
    """BRD §16 — the client's folder: everything filed against the Client ID, plus the documents
    attached to the client's cases (read-only here; they are managed on the case)."""
    from app.models import User as UserModel
    account = _account_for_read(db, account_id, user)
    names = {u.id: u.name for u in db.query(UserModel.id, UserModel.name).all()}

    def item(d: Document, **extra) -> dict:
        out = {c: getattr(d, c) for c in ("id", "case_id", "account_id", "case_document_id", "instruction_id", "category",
                                          "filename", "content_type", "size_bytes", "uploaded_by_id", "notes",
                                          "generated_from", "created_at")}
        out["uploaded_by_name"] = names.get(d.uploaded_by_id)
        out.update(extra)
        return out

    client_docs = []
    for d in db.query(Document).filter(Document.account_id == account.id).order_by(Document.id.desc()).all():
        allowed, stage, reason = client_document_removal(db, d, account, user)
        client_docs.append(item(d, can_delete=allowed, stage=stage, lock_reason=reason))
    case_docs = [item(d, can_delete=False, stage=None, lock_reason="Managed on the case", case_uid=d.case.case_uid)
                 for d in (db.query(Document).join(Case, Document.case_id == Case.id)
                           .filter(Case.account_id == account.id).order_by(Document.id.desc()).all())]
    return {
        "account_id": account.id, "client_id": account.client_id, "temp_id": account.account_uid, "company_name": account.company_name,
        "profile_status": account.profile_status, "stage": _client_document_stage(db, account),
        "max_upload_mb": settings.MAX_UPLOAD_MB, "documents": client_docs, "case_documents": case_docs,
    }
