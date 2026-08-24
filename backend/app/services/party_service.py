"""Service layer: Director and Shareholder registers (per Case)."""
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import Director, Shareholder, Case, User, UserRole
from app.schemas.party import DirectorCreate, DirectorUpdate, ShareholderCreate, ShareholderUpdate
from app.services import cdd_service


def _get_case_for_write(db: Session, case_id: int, user: User) -> Case:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if user.role == UserRole.RM and case.rm_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return case


# ─── Directors ───────────────────────────────────────────────────────────
def list_directors(db: Session, case_id: int) -> list[Director]:
    return db.query(Director).filter(Director.case_id == case_id).order_by(Director.id).all()


def get_director(db: Session, director_id: int) -> Director:
    d = db.query(Director).filter(Director.id == director_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Director not found")
    return d


def create_director(db: Session, case_id: int, data: DirectorCreate, user: User) -> Director:
    _get_case_for_write(db, case_id, user)
    d = Director(case_id=case_id, **data.model_dump())
    db.add(d)
    db.commit()
    db.refresh(d)
    cdd_service.generate_director_documents(db, d)
    return d


def update_director(db: Session, director_id: int, data: DirectorUpdate, user: User) -> Director:
    d = get_director(db, director_id)
    _get_case_for_write(db, d.case_id, user)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(d, field, value)
    db.commit()
    db.refresh(d)
    return d


def delete_director(db: Session, director_id: int, user: User) -> None:
    d = get_director(db, director_id)
    _get_case_for_write(db, d.case_id, user)
    db.delete(d)
    db.commit()


# ─── Shareholders ────────────────────────────────────────────────────────
def list_shareholders(db: Session, case_id: int) -> list[Shareholder]:
    return db.query(Shareholder).filter(Shareholder.case_id == case_id).order_by(Shareholder.id).all()


def get_shareholder(db: Session, shareholder_id: int) -> Shareholder:
    s = db.query(Shareholder).filter(Shareholder.id == shareholder_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Shareholder not found")
    return s


def create_shareholder(db: Session, case_id: int, data: ShareholderCreate, user: User) -> Shareholder:
    _get_case_for_write(db, case_id, user)
    s = Shareholder(case_id=case_id, **data.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    cdd_service.generate_shareholder_documents(db, s)
    return s


def update_shareholder(db: Session, shareholder_id: int, data: ShareholderUpdate, user: User) -> Shareholder:
    s = get_shareholder(db, shareholder_id)
    _get_case_for_write(db, s.case_id, user)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    db.commit()
    db.refresh(s)
    return s


def delete_shareholder(db: Session, shareholder_id: int, user: User) -> None:
    s = get_shareholder(db, shareholder_id)
    _get_case_for_write(db, s.case_id, user)
    db.delete(s)
    db.commit()
