"""Pydantic schemas: Document (uploaded / generated file metadata — never the bytes)."""
from pydantic import BaseModel, ConfigDict
from typing import Optional, Any
from datetime import datetime


class DocumentRead(BaseModel):
    id: int
    case_id: int
    case_document_id: Optional[int] = None
    instruction_id: Optional[int] = None
    category: str
    filename: str
    content_type: Optional[str] = None
    size_bytes: int
    uploaded_by_id: Optional[int] = None
    notes: Optional[str] = None
    generated_from: Optional[str] = None
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
