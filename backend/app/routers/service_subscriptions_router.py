"""Service subscriptions router — recurring services per entity."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User
from app.schemas import ServiceSubscriptionCreate, ServiceSubscriptionUpdate, ServiceSubscriptionRead
from app.services import service_subscription_service

router = APIRouter(tags=["Service Subscriptions"])


@router.get("/cases/{case_id}/service-subscriptions", response_model=List[ServiceSubscriptionRead])
def list_service_subscriptions(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service_subscription_service.list_for_case(db, case_id, user)


@router.post("/cases/{case_id}/service-subscriptions", response_model=ServiceSubscriptionRead, status_code=status.HTTP_201_CREATED)
def create_service_subscription(case_id: int, data: ServiceSubscriptionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service_subscription_service.create(db, case_id, data, user)


@router.patch("/service-subscriptions/{sub_id}", response_model=ServiceSubscriptionRead)
def update_service_subscription(sub_id: int, data: ServiceSubscriptionUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service_subscription_service.update(db, sub_id, data, user)


@router.delete("/service-subscriptions/{sub_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service_subscription(sub_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service_subscription_service.delete(db, sub_id, user)
    return None
