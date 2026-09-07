"""Pydantic schemas: AML Risk Assessment + Country Risk reference table."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Any
from datetime import date, datetime
from decimal import Decimal

from app.models.aml import AMLSubjectType


# ─── Country risk ────────────────────────────────────────────────────────
class CountryRiskBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    kyc_score: Optional[Decimal] = None
    risk_level: str = Field(..., pattern="^(Low|Medium|High|Prohibited)$")
    score: int = Field(..., ge=1, le=5)
    default_to_high: bool = False


class CountryRiskCreate(CountryRiskBase):
    pass


class CountryRiskUpdate(BaseModel):
    kyc_score: Optional[Decimal] = None
    risk_level: Optional[str] = Field(None, pattern="^(Low|Medium|High|Prohibited)$")
    score: Optional[int] = Field(None, ge=1, le=5)
    default_to_high: Optional[bool] = None


class CountryRiskRead(CountryRiskBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


# ─── AML risk assessment ────────────────────────────────────────────────
class AMLAssessmentCreate(BaseModel):
    case_id: int
    subject_type: AMLSubjectType = AMLSubjectType.ENTITY
    subject_name: str = Field(..., min_length=1, max_length=255)
    director_id: Optional[int] = None
    shareholder_id: Optional[int] = None
    ubo_id: Optional[int] = None
    assessment_date: Optional[date] = None
    completed_by_id: Optional[int] = None
    # {factor_key: chosen option string}
    selections: dict[str, str] = Field(default_factory=dict)
    remarks: Optional[str] = None


class AMLAssessmentUpdate(BaseModel):
    subject_name: Optional[str] = Field(None, min_length=1, max_length=255)
    director_id: Optional[int] = None
    shareholder_id: Optional[int] = None
    ubo_id: Optional[int] = None
    assessment_date: Optional[date] = None
    completed_by_id: Optional[int] = None
    selections: Optional[dict[str, str]] = None
    remarks: Optional[str] = None
    # MLRO override ("Amended Overall Customer Risk")
    amended_rating: Optional[str] = Field(None, pattern="^(Low|Medium|High)$")
    mlro_notes: Optional[str] = None


class AMLAssessmentRead(BaseModel):
    id: int
    case_id: int
    subject_type: str
    subject_name: str
    director_id: Optional[int] = None
    shareholder_id: Optional[int] = None
    ubo_id: Optional[int] = None
    assessment_date: Optional[date] = None
    completed_by_id: Optional[int] = None
    matrix_version: Optional[str] = None

    factors: Optional[list[dict[str, Any]]] = None
    total_weighted_score: Optional[Decimal] = None
    calculated_rating: Optional[str] = None
    override_reason: Optional[str] = None
    onboarding_blocked: bool = False

    amended_rating: Optional[str] = None
    mlro_notes: Optional[str] = None
    mlro_id: Optional[int] = None
    mlro_reviewed_at: Optional[datetime] = None
    effective_rating: Optional[str] = None

    remarks: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AMLFactorOption(BaseModel):
    value: str
    rating: str


class AMLFactorDef(BaseModel):
    key: str
    label: str
    weight: float
    kind: str  # "country" | "options"
    options: Optional[list[AMLFactorOption]] = None


class AMLPrefillRead(BaseModel):
    subject_name: Optional[str] = None
    ubo_nationality: Optional[str] = None
    ubo_residence: Optional[str] = None


class AMLCatalogRead(BaseModel):
    version: str
    rating_score: dict[str, int]
    bands: list[list]
    pep_high_option: str
    entity_factors: list[AMLFactorDef]
    individual_factors: list[AMLFactorDef]
