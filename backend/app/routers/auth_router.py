"""Auth router: login, token refresh, current user."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.audit import set_actor, log_event
from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, Token, RefreshTokenRequest, UserRead
from app.schemas.user import ChangePasswordRequest
from app.services import security_service
from app.auth.security import hash_password
from app.auth.security import (
    verify_password, create_access_token, create_refresh_token, decode_token,
)
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token, summary="Login with email and password")
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else None
    user = db.query(User).filter(User.email == data.email).first()
    security_service.assert_not_locked(user)
    if not user or not user.is_active or not verify_password(data.password, user.hashed_password):
        security_service.record_failure(user if user and user.is_active else None)
        # BRD §15 audit — failed attempts are recorded too (email only; never the password).
        set_actor(db, user.id if user else None, ip)
        log_event(db, "login_failed", f"Failed login for {data.email}", subject_type="User",
                  subject_id=user.id if user else None)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    security_service.record_success(user)
    set_actor(db, user.id, ip)
    log_event(db, "login", f"{user.name} logged in", subject_type="User", subject_id=user.id)
    db.commit()
    access = create_access_token(user.id, user.role.value)
    refresh = create_refresh_token(user.id, user.role.value)
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "user": user,
        "password_change_recommended": data.password.lower() in security_service.DEFAULT_PASSWORDS,
    }


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT, summary="Change your own password")
def change_password(data: ChangePasswordRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Your current password is not correct")
    if data.new_password == data.current_password:
        raise HTTPException(status_code=400, detail="Choose a password different from the current one")
    security_service.assert_password_ok(data.new_password, user.email)
    user.hashed_password = hash_password(data.new_password)
    security_service.password_set(user)
    log_event(db, "password_change", f"{user.name} changed their password", subject_type="User", subject_id=user.id)
    db.commit()
    return None


@router.post("/refresh", response_model=Token, summary="Exchange refresh token for new tokens")
def refresh(data: RefreshTokenRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_token(data.refresh_token, is_refresh=True)
        user_id = int(payload["sub"])
    except (ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return {
        "access_token": create_access_token(user.id, user.role.value),
        "refresh_token": create_refresh_token(user.id, user.role.value),
        "token_type": "bearer",
        "user": user,
    }


@router.get("/me", response_model=UserRead, summary="Get current authenticated user")
def me(user: User = Depends(get_current_user)):
    return user
