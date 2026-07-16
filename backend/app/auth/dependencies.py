"""FastAPI auth dependencies: get current user, enforce roles."""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.auth.security import decode_token
from app.database import get_db
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the JWT access token to a User, or 401."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token, is_refresh=False)
        user_id = int(payload["sub"])
    except (ValueError, KeyError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if user is None:
        raise credentials_exception
    return user


def require_roles(*allowed_roles: UserRole):
    """Dependency factory: require one of the given roles."""
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Action requires one of roles: {[r.value for r in allowed_roles]}",
            )
        return user
    return checker


# Convenience dependencies
require_admin = require_roles(UserRole.ADMIN)
require_rm = require_roles(UserRole.ADMIN, UserRole.RM)
require_ops = require_roles(UserRole.ADMIN, UserRole.OPS)
require_screening = require_roles(UserRole.ADMIN, UserRole.SCREENING)
require_any = require_roles(UserRole.ADMIN, UserRole.RM, UserRole.OPS, UserRole.SCREENING)
