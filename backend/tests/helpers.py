"""Small helpers shared by the API tests."""
from app.auth.security import create_access_token


def auth(user):
    """Request headers signed in as this user."""
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}
