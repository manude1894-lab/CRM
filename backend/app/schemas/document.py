"""Pydantic schemas: Document (uploaded / generated file metadata — never the bytes)."""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Any
from datetime import datetime


class DocumentRead(BaseModel):
    id: int
    case_id: Optional[int] = None
    account_id: Optional[int] = None
    case_document_id: Optional[int] = None
    instruction_id: Optional[int] = None
    category: str
    filename: str
    content_type: Optional[str] = None
    size_bytes: int
    uploaded_by_id: Optional[int] = None
    notes: Optional[str] = None
    generated_from: Optional[str] = None
    link_url: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentTemplateField(BaseModel):
    key: str
    label: str
    type: str  # text | textarea | date | select
    required: bool = False
    options: Optional[list[str]] = None


class DocumentTemplateInfo(BaseModel):
    code: str
    label: str
    category: str
    fields: list[DocumentTemplateField]


class DocumentGenerateRequest(BaseModel):
    template_code: str
    params: dict[str, Any] = {}


class FolderDocument(DocumentRead):
    uploaded_by_name: Optional[str] = None
    can_delete: bool = False
    stage: Optional[str] = None  # Draft / Submitted / Locked (BRD §16)
    lock_reason: Optional[str] = None
    case_uid: Optional[str] = None  # set for documents that belong to one of the client's cases
    link_url: Optional[str] = None


class RemovedDocument(BaseModel):
    filename: Optional[str] = None
    category: Optional[str] = None
    removed_by_name: Optional[str] = None
    removed_at: Optional[datetime] = None


class LinkDocumentCreate(BaseModel):
    category: str
    url: str = Field(..., max_length=1000)
    title: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = Field(None, max_length=500)


class ClientFolder(BaseModel):
    """BRD §16 — every document filed against a Client ID."""
    account_id: int
    client_id: Optional[str] = None
    temp_id: Optional[str] = None  # shown until the Client ID is issued at Compliance approval
    company_name: str
    profile_status: Optional[str] = None
    stage: str
    max_upload_mb: int
    documents: list[FolderDocument]
    case_documents: list[FolderDocument]
    removed: list[RemovedDocument] = []
    compliance_can_file: bool = False
