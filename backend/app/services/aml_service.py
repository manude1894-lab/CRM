"""Service layer: AML Risk Assessment + Country Risk reference table.

Runs the weighted matrix (app.services.aml_matrix), persists the result, and syncs
the latest Entity assessment's effective rating back to CDDRecord.aml_risk_rating so
the existing CDD workflow gate keeps working unchanged.
"""
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import (
    AMLRiskAssessment, AMLSubjectType, CountryRisk, Case, CDDRecord, User, UserRole,
)
from app.schemas.aml import (
    AMLAssessmentCreate, AMLAssessmentUpdate, CountryRiskCreate, CountryRiskUpdate,
)
from app.services import aml_matrix

_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "country_risk.json"


# ─── Country risk table ─────────────────────────────────────────────────
def seed_country_risk(db: Session) -> int:
    """Idempotently load the country-risk reference table. Returns rows inserted."""
    if db.query(CountryRisk).count() > 0:
        return 0
    payload = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    rows = [
        CountryRisk(
            name=c["name"],
            kyc_score=Decimal(str(c["kyc_score"])) if c.get("kyc_score") is not None else None,
            risk_level=c["risk_level"],
            score=int(c["score"]),
            default_to_high=bool(c.get("default_to_high", False)),
        )
        for c in payload["countries"]
    ]
    db.add_all(rows)
    db.commit()
    return len(rows)


def list_country_risk(db: Session) -> list[CountryRisk]:
    return db.query(CountryRisk).order_by(CountryRisk.name).all()


def _country_lookup(db: Session) -> dict[str, dict]:
    return {
        c.name: {"risk_level": c.risk_level, "score": c.score, "default_to_high": c.default_to_high}
        for c in db.query(CountryRisk).all()
    }


def create_country_risk(db: Session, data: CountryRiskCreate) -> CountryRisk:
    if db.query(CountryRisk).filter(CountryRisk.name == data.name).first():
        raise HTTPException(status_code=400, detail="Country already exists")
    c = CountryRisk(**data.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def update_country_risk(db: Session, country_id: int, data: CountryRiskUpdate) -> CountryRisk:
    c = db.query(CountryRisk).filter(CountryRisk.id == country_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Country not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(c, field, value)
    db.commit()
    db.refresh(c)
    return c


def delete_country_risk(db: Session, country_id: int) -> None:
    c = db.query(CountryRisk).filter(CountryRisk.id == country_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Country not found")
    db.delete(c)
    db.commit()


# ─── AML assessments ────────────────────────────────────────────────────
def _get_case_for_write(db: Session, case_id: int, user: User) -> Case:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if user.role == UserRole.RM and case.rm_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return case


def _apply_matrix(db: Session, assessment: AMLRiskAssessment, selections: dict[str, str]) -> None:
    result = aml_matrix.calculate(assessment.subject_type, selections, _country_lookup(db))
    assessment.factors = result.factors
    assessment.total_weighted_score = result.total_weighted_score
    assessment.calculated_rating = result.calculated_rating
    assessment.override_reason = result.override_reason
    assessment.onboarding_blocked = result.onboarding_blocked
    assessment.matrix_version = aml_matrix.AML_MATRIX_VERSION


def _sync_cdd_rating(db: Session, case_id: int) -> None:
    """Push the latest Entity assessment's effective rating onto CDDRecord."""
    latest = (
        db.query(AMLRiskAssessment)
        .filter(
            AMLRiskAssessment.case_id == case_id,
            AMLRiskAssessment.subject_type == AMLSubjectType.ENTITY.value,
        )
        .order_by(AMLRiskAssessment.id.desc())
        .first()
    )
    if not latest:
        return
    cdd = db.query(CDDRecord).filter(CDDRecord.case_id == case_id).first()
    if cdd:
        cdd.aml_risk_rating = latest.effective_rating
        db.commit()


def list_assessments(db: Session, case_id: int | None = None) -> list[AMLRiskAssessment]:
    q = db.query(AMLRiskAssessment)
    if case_id is not None:
        q = q.filter(AMLRiskAssessment.case_id == case_id)
    return q.order_by(AMLRiskAssessment.id.desc()).all()


def get_assessment(db: Session, assessment_id: int) -> AMLRiskAssessment:
    a = db.query(AMLRiskAssessment).filter(AMLRiskAssessment.id == assessment_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="AML assessment not found")
    return a


def create_assessment(db: Session, data: AMLAssessmentCreate, user: User) -> AMLRiskAssessment:
    _get_case_for_write(db, data.case_id, user)
    a = AMLRiskAssessment(
        case_id=data.case_id,
        subject_type=data.subject_type.value if hasattr(data.subject_type, "value") else data.subject_type,
        subject_name=data.subject_name,
        director_id=data.director_id,
        shareholder_id=data.shareholder_id,
        assessment_date=data.assessment_date,
        completed_by_id=data.completed_by_id or user.id,
        remarks=data.remarks,
    )
    _apply_matrix(db, a, data.selections)
    db.add(a)
    db.commit()
    db.refresh(a)
    if a.subject_type == AMLSubjectType.ENTITY.value:
        _sync_cdd_rating(db, a.case_id)
    return a


def update_assessment(db: Session, assessment_id: int, data: AMLAssessmentUpdate, user: User) -> AMLRiskAssessment:
    a = get_assessment(db, assessment_id)
    _get_case_for_write(db, a.case_id, user)
    payload = data.model_dump(exclude_unset=True)

    selections = payload.pop("selections", None)

    mlro_touched = payload.get("amended_rating") is not None or payload.get("mlro_notes") is not None
    if mlro_touched and user.role not in (UserRole.ADMIN, UserRole.SCREENING):
        raise HTTPException(status_code=403, detail="Only the MLRO (Screening/Admin) can amend a rating")
    for field, value in payload.items():
        setattr(a, field, value)

    if selections is not None:
        # Selections come back from the client as the full {key: input} map.
        _apply_matrix(db, a, selections)

    if mlro_touched:
        a.mlro_id = user.id
        a.mlro_reviewed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(a)
    if a.subject_type == AMLSubjectType.ENTITY.value:
        _sync_cdd_rating(db, a.case_id)
    return a


def delete_assessment(db: Session, assessment_id: int, user: User) -> None:
    a = get_assessment(db, assessment_id)
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only Admin can delete an AML assessment")
    case_id, was_entity = a.case_id, a.subject_type == AMLSubjectType.ENTITY.value
    db.delete(a)
    db.commit()
    if was_entity:
        _sync_cdd_rating(db, case_id)


def selections_of(assessment: AMLRiskAssessment) -> dict[str, str]:
    """Reconstruct the {key: input} map from the stored factor rows — used to
    prefill the edit form."""
    return {row["key"]: row.get("input") for row in (assessment.factors or []) if row.get("input")}
