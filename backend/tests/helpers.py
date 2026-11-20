"""Small helpers shared by the API tests."""
from app.auth.security import create_access_token


def auth(user):
    """Request headers signed in as this user."""
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


def rows_of(report):
    """A standard report's rows as {column: value}, so tests read columns by name, not position."""
    return [dict(zip(report["columns"], r)) for r in report["rows"]]
