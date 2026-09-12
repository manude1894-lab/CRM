"""Pydantic schemas: ServiceSubscription (recurring services per entity)."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

from app.models.service_subscription import ServiceBillingFrequency, ServiceSubscriptionStatus


class ServiceSubscriptionBase(BaseModel):
    service_name: str = Field(..., min_length=1, max_length=150)
    billing_frequency: ServiceBillingFrequency = ServiceBillingFrequency.MONTHLY
    fee_amount: Optional[Decimal] = Field(None, ge=0)
    status: ServiceSubscriptionStatus = ServiceSubscriptionStatus.ACTIVE
    start_date: Optional[date] = None
    next_billing_date: Optional[date] = None
    notes: Optional[str] = None


class ServiceSubscriptionCreate(ServiceSubscriptionBase):
    pass


class ServiceSubscriptionUpdate(BaseModel):
    service_name: Optional[str] = Field(None, min_length=1, max_length=150)
    billing_frequency: Optional[ServiceBillingFrequency] = None
    fee_amount: Optional[Decimal] = Field(None, ge=0)
    status: Optional[ServiceSubscriptionStatus] = None
    start_date: Optional[date] = None
    next_billing_date: Optional[date] = None
    notes: Optional[str] = None


class ServiceSubscriptionRead(ServiceSubscriptionBase):
    id: int
    case_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
