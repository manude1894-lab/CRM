"""Auth router: login, token refresh, current user."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.audit import set_actor, log_event
from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, Token, RefreshTokenRequest, UserRead
from app.auth.security import (
    verify_password, create_access_token, create_refresh_token, decode_token,
)
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token, summary="Login with email and password")
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else None
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not user.is_active or not verify_password(data.password, user.hashed_password):
        # BRD §15 audit — failed attempts are recorded too (email only; never the password).
        set_actor(db, user.id if user else None, ip)
        log_event(db, "login_failed", f"Failed login for {data.email}", subject_type="User",
                  subject_id=user.id if user else None)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
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
    }


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
