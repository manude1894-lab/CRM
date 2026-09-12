"""Service layer: CompanyProfile (formation / statutory detail, 1:1 with Case)."""
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import CompanyProfile, ComplianceSchedule, Case, User, UserRole
from app.models.company_profile import NameCheckStatus
from app.schemas.company_profile import CompanyProfileUpdate
from app.services import compliance_service, access_control


def _get_case_for_write(db: Session, case_id: int, user: User) -> Case:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if not access_control.user_can_access_case(case, user):
        raise HTTPException(status_code=403, detail="Access denied")
    return case


def get_or_create(db: Session, case_id: int) -> CompanyProfile:
    profile = db.query(CompanyProfile).filter(CompanyProfile.case_id == case_id).first()
    if profile:
        return profile
    if not db.query(Case).filter(Case.id == case_id).first():
        raise HTTPException(status_code=404, detail="Case not found")
    profile = CompanyProfile(case_id=case_id, name_check_status=NameCheckStatus.NOT_SUBMITTED.value)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def update(db: Session, case_id: int, data: CompanyProfileUpdate, user: User) -> CompanyProfile:
    _get_case_for_write(db, case_id, user)
    profile = get_or_create(db, case_id)
    payload = data.model_dump(exclude_unset=True)
    incorporation_changed = (
        "incorporation_date" in payload and payload["incorporation_date"] != profile.incorporation_date
    )
    for field, value in payload.items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)

    # Keep the renewal date anchored to the incorporation anniversary (per the
    # case's jurisdiction — for BVI that is the incorporation anniversary).
    if incorporation_changed and profile.incorporation_date:
        schedule = db.query(ComplianceSchedule).filter(ComplianceSchedule.case_id == case_id).first()
        if schedule:
            from app import jurisdictions
            case = db.query(Case).filter(Case.id == case_id).first()
            renewal = jurisdictions.get(case.jurisdiction if case else None).item("renewal")
            if renewal:
                schedule.renewal_due_date = compliance_service.compute_due(
                    renewal, incorporation_date=profile.incorporation_date, base=profile.incorporation_date,
                )
                db.commit()

    return profile
