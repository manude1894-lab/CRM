"""Pydantic schemas: Document (uploaded file metadata — never the bytes)."""
from pydantic import BaseModel, ConfigDict
from typing import Optional
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
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
