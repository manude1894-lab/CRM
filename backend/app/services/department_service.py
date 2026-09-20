"""Service layer: Department (org-structure master table, Admin-managed)."""
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import Department
from app.schemas.department import DepartmentCreate, DepartmentUpdate


def list_departments(db: Session) -> list[Department]:
    return db.query(Department).order_by(Department.name).all()


def get_department(db: Session, department_id: int) -> Department:
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    return dept


def create_department(db: Session, data: DepartmentCreate) -> Department:
    if db.query(Department).filter(Department.name == data.name).first():
        raise HTTPException(status_code=400, detail="Department already exists")
    dept = Department(**data.model_dump())
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


def update_department(db: Session, department_id: int, data: DepartmentUpdate) -> Department:
    dept = get_department(db, department_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(dept, field, value)
    db.commit()
    db.refresh(dept)
    return dept


def delete_department(db: Session, department_id: int) -> None:
    dept = get_department(db, department_id)
    db.delete(dept)
    db.commit()
