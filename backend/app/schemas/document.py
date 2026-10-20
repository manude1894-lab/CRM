"""Pydantic schemas: Document (file / link metadata — never the bytes)."""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime


class DocumentRead(BaseModel):
    id: int
    account_id: int
    instruction_id: Optional[int] = None
    category: str
    filename: str
    content_type: Optional[str] = None
    size_bytes: int
    uploaded_by_id: Optional[int] = None
    notes: Optional[str] = None
    link_url: Optional[str] = None
    party_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FolderDocument(DocumentRead):
    uploaded_by_name: Optional[str] = None
    can_delete: bool = False
    stage: Optional[str] = None  # Draft / Submitted / Locked (BRD §14)
    lock_reason: Optional[str] = None
    party_name: Optional[str] = None  # the UBO / director / signatory / joint holder it was filed for
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
    party_id: Optional[int] = None


class ClientFolder(BaseModel):
    """BRD §14 — every document filed against a Client ID."""
    account_id: int
    client_id: Optional[str] = None
    temp_id: Optional[str] = None  # shown until the Client ID is issued at Compliance approval
    company_name: str
    profile_status: Optional[str] = None
    stage: str
    max_upload_mb: int
    documents: list[FolderDocument]
    removed: list[RemovedDocument] = []
    compliance_can_file: bool = False
    parties: list[dict] = []  # the client's people, for filing their documents
