"""Auth router: login, token refresh, current user."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.audit import set_actor, log_event
from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, Token, RefreshTokenRequest, UserRead
from app.schemas.user import ChangePasswordRequest, ForgotPasswordRequest, ResetPasswordRequest
from app.services import security_service
from app.auth.security import hash_password
from app.auth.security import (
    verify_password, create_access_token, create_refresh_token, decode_token, issued_before_password_change,
)
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token, summary="Login with email and password")
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else None
    from app.services.user_service import find_by_email
    user = find_by_email(db, data.email)
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
    from datetime import datetime, timezone
    user.previous_login_at, user.last_login_at = user.last_login_at, datetime.now(timezone.utc)
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


@router.post("/change-password", response_model=Token, summary="Change your own password")
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
    # Other sessions are signed out by the change; this one carries on with new tokens.
    return {
        "access_token": create_access_token(user.id, user.role.value),
        "refresh_token": create_refresh_token(user.id, user.role.value),
        "token_type": "bearer",
        "user": user,
    }


@router.post("/forgot-password", summary="Ask for a password reset link")
def forgot_password(data: ForgotPasswordRequest, background: BackgroundTasks):
    # The lookup and any emails happen after the response, in their own session: every email gets the
    # same, immediate answer. email_sent says whether reset emails are set up at all (not per user).
    background.add_task(_forgot_password_task, data.email)
    return {"email_sent": security_service.reset_emails_enabled()}


def _forgot_password_task(email: str) -> None:
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        security_service.request_password_reset(db, email)
    finally:
        db.close()


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT, summary="Set a new password from a reset link")
def reset_password(data: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    set_actor(db, None, request.client.host if request.client else None)
    security_service.reset_password(db, data.token, data.new_password)
    return None


@router.post("/refresh", response_model=Token, summary="Exchange refresh token for new tokens")
def refresh(data: RefreshTokenRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_token(data.refresh_token, is_refresh=True)
        user_id = int(payload["sub"])
    except (ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user or issued_before_password_change(payload, user):
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
