"""Service layer: Prospect (pre-Case proposal tracking)."""
from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import Prospect, ProspectStatus, User, UserRole
from app.schemas.prospect import ProspectCreate, ProspectUpdate, ProspectConvertRequest
from app.schemas.case import CaseCreate
from app.utils.uid import next_uid
from app.services import case_service


def _apply_rbac_filter(query, user: User):
    if user.role == UserRole.RM:
        query = query.filter(Prospect.owner_id == user.id)
    return query


def list_prospects(db: Session, user: User, status: Optional[str] = None) -> list[Prospect]:
    query = _apply_rbac_filter(db.query(Prospect), user)
    if status:
        query = query.filter(Prospect.status == status)
    return query.order_by(Prospect.id.desc()).all()


def get_prospect(db: Session, prospect_id: int, user: User) -> Prospect:
    p = db.query(Prospect).filter(Prospect.id == prospect_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Prospect not found")
    if user.role == UserRole.RM and p.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return p


def create_prospect(db: Session, data: ProspectCreate, user: User) -> Prospect:
    payload = data.model_dump()
    if not payload.get("owner_id"):
        payload["owner_id"] = user.id
    p = Prospect(prospect_uid=next_uid(db, Prospect, "prospect_uid", "PROS"), **payload)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def update_prospect(db: Session, prospect_id: int, data: ProspectUpdate, user: User) -> Prospect:
    p = get_prospect(db, prospect_id, user)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(p, field, value)
    db.commit()
    db.refresh(p)
    return p


def delete_prospect(db: Session, prospect_id: int, user: User) -> None:
    p = get_prospect(db, prospect_id, user)
    db.delete(p)
    db.commit()


def convert_to_case(db: Session, prospect_id: int, data: ProspectConvertRequest, user: User):
    p = get_prospect(db, prospect_id, user)
    if p.converted_case_id:
        raise HTTPException(status_code=400, detail="This prospect has already been converted")
    case = case_service.create_case(db, CaseCreate(
        company_name=p.company_name,
        source="Referral",
        introducer=p.source,
        jurisdiction=data.jurisdiction,
        service_type=data.service_type or "Company Formation",
        rm_id=data.rm_id or p.owner_id,
        notes=f"Converted from prospect {p.prospect_uid}.",
    ), user)
    p.converted_case_id = case.id
    p.status = ProspectStatus.WON.value
    db.commit()
    db.refresh(p)
    return case
