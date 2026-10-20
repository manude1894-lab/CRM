"""Pydantic schemas: Countries master (BRD §17)."""
from pydantic import BaseModel, ConfigDict, Field


class CountryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)


class CountryRead(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)
