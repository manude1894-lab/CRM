from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

RiskLevel = Literal["High", "Medium", "Low"]


class CountryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    code: Optional[str] = Field(None, pattern=r"^[A-Za-z]{2}$")
    risk_level: RiskLevel = "Low"


class CountryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    code: Optional[str] = Field(None, pattern=r"^[A-Za-z]{2}$")
    risk_level: Optional[RiskLevel] = None


class CountryRead(BaseModel):
    id: int
    name: str
    code: Optional[str] = None
    risk_level: Optional[str] = None
    changed_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)
