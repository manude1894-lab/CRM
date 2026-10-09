"""Pydantic schemas: User, Auth tokens."""
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
from datetime import datetime
from typing import Optional

from app.models.user import UserRole


def _mobile(v):
    """Optional international mobile number for SMS notifications, stored as +<digits>."""
    if v in (None, ""):
        return None
    from app.services.sms_service import normalise
    n = normalise(str(v))
    if n is None:
        raise ValueError("must be an international number, e.g. +971501234567")
    return n


class UserBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    role: UserRole = UserRole.RM
    is_active: bool = True
    department_id: Optional[int] = None
    title: Optional[str] = None
    supervisor_id: Optional[int] = None
    business_role_id: Optional[int] = None
    mobile: Optional[str] = None

    _check_mobile = field_validator("mobile", mode="before")(classmethod(lambda cls, v: _mobile(v)))


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=100)


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=6)
    department_id: Optional[int] = None
    title: Optional[str] = None
    supervisor_id: Optional[int] = None
    business_role_id: Optional[int] = None
    mobile: Optional[str] = None

    _check_mobile = field_validator("mobile", mode="before")(classmethod(lambda cls, v: _mobile(v)))


class UserRead(UserBase):
    id: int
    permissions: list[str] = []
    business_role_name: Optional[str] = None
    locked_until: Optional[datetime] = None  # P7 — shown to admins; resetting the password unlocks
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserRead
    password_change_recommended: bool = False  # signed in with a default password


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenPayload(BaseModel):
    sub: str  # user id as string
    role: str
    exp: int
    type: str  # "access" or "refresh"
