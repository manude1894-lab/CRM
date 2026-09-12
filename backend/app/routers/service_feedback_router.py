"""Service feedback router — staff-logged client feedback."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User
from app.schemas import ServiceFeedbackCreate, ServiceFeedbackRead
from app.services import service_feedback_service

router = APIRouter(tags=["Feedback"])


@router.get("/cases/{case_id}/feedback", response_model=List[ServiceFeedbackRead])
def list_feedback(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service_feedback_service.list_for_case(db, case_id, user)


@router.post("/cases/{case_id}/feedback", response_model=ServiceFeedbackRead, status_code=status.HTTP_201_CREATED)
def create_feedback(case_id: int, data: ServiceFeedbackCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service_feedback_service.create(db, case_id, data, user)


@router.delete("/feedback/{feedback_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_feedback(feedback_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service_feedback_service.delete(db, feedback_id, user)
    return None
