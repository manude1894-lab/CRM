from typing import Optional

from pydantic import BaseModel, Field


class CancelRequest(BaseModel):
    """Body for cancelling or removing a record. Records are never deleted; the reason is kept."""
    reason: str = Field(..., min_length=3, max_length=500)


class OptionalReason(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)
