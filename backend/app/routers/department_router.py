"""Departments router — org-structure master table (Admin-managed)."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.auth.dependencies import get_current_user, require_admin
from app.models import User
from app.schemas import DepartmentCreate, DepartmentRead, DepartmentUpdate
from app.services import department_service

router = APIRouter(prefix="/departments", tags=["Departments"])


@router.get("", response_model=List[DepartmentRead])
def list_departments(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return department_service.list_departments(db)


@router.post("", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED)
def create_department(data: DepartmentCreate, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return department_service.create_department(db, data)


@router.patch("/{department_id}", response_model=DepartmentRead)
def update_department(department_id: int, data: DepartmentUpdate, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return department_service.update_department(db, department_id, data)


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(department_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    department_service.delete_department(db, department_id)
    return None
