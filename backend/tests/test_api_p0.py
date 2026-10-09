"""P0 endpoints through the real FastAPI app: auth, permissions, audit on requests."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.auth.security import create_access_token, hash_password
from app.models import UserRole, AuditLog, User


@pytest.fixture()
def client(db):
    def _get_db():
        yield db
    app.dependency_overrides[get_db] = _get_db
    yield TestClient(app)  # not used as a context manager -> the scheduler lifespan doesn't start
    app.dependency_overrides.clear()


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


def test_masters_read_for_everyone_write_needs_permission(client, make_user, seed_master):
    seed_master("tag", ["SPV"])
    rm, admin = make_user(), make_user(role=UserRole.ADMIN)
    assert client.get("/api/v1/masters/tag", headers=auth(rm)).json()[0]["code"] == "SPV"
    assert client.post("/api/v1/masters/tag", json={"label": "New"}, headers=auth(rm)).status_code == 403
    assert client.post("/api/v1/masters/tag", json={"label": "New"}, headers=auth(admin)).status_code == 201


def test_business_role_grants_permission(client, make_user, make_role):
    maintainer = make_user(business_role=make_role("Data Steward", ["master.manage"]))
    assert client.post("/api/v1/masters/tag", json={"label": "X"}, headers=auth(maintainer)).status_code == 201


def test_me_exposes_permissions(client, make_user, make_role):
    co = make_user(business_role=make_role("CO", ["client.approve", "audit.view"]))
    # client.approve implies view.all_clients (a checker must see what they approve)
    assert client.get("/api/v1/auth/me", headers=auth(co)).json()["permissions"] == ["audit.view", "client.approve", "view.all_clients"]


def test_me_shows_business_role_name(client, make_user, make_role):
    mlro = make_user(business_role=make_role("MLRO", ["client.approve"]))
    assert client.get("/api/v1/auth/me", headers=auth(mlro)).json()["business_role_name"] == "MLRO"
    assert client.get("/api/v1/auth/me", headers=auth(make_user())).json()["business_role_name"] is None


def test_changes_through_the_api_are_attributed(client, db, make_user):
    admin = make_user("Admin", role=UserRole.ADMIN)
    r = client.post("/api/v1/roles", json={"name": "MLRO", "permissions": ["client.approve"]}, headers=auth(admin))
    assert r.status_code == 201
    entry = db.query(AuditLog).filter(AuditLog.subject_type == "Role").one()
    assert entry.user_id == admin.id and entry.action == "create"


def test_audit_endpoint_requires_permission(client, make_user):
    assert client.get("/api/v1/audit", headers=auth(make_user())).status_code == 403
    assert client.get("/api/v1/audit", headers=auth(make_user(role=UserRole.ADMIN))).status_code == 200


def test_client_history_follows_client_visibility(client, make_user, make_account):
    owner, stranger = make_user("Owner"), make_user("Stranger")
    acc = make_account(spoc=owner)
    assert client.get(f"/api/v1/accounts/{acc.id}/audit", headers=auth(owner)).status_code == 200
    assert client.get(f"/api/v1/accounts/{acc.id}/audit", headers=auth(stranger)).status_code == 403


def test_unknown_permission_rejected(client, make_user):
    r = client.post("/api/v1/roles", json={"name": "X", "permissions": ["do.anything"]}, headers=auth(make_user(role=UserRole.ADMIN)))
    assert r.status_code == 400


def test_supervisor_loop_rejected(client, make_user):
    admin = make_user(role=UserRole.ADMIN)
    a = make_user("A")
    b = make_user("B", supervisor=a)
    r = client.patch(f"/api/v1/users/{a.id}", json={"supervisor_id": b.id}, headers=auth(admin))
    assert r.status_code == 400


def test_login_success_and_failure_are_audited(client, db):
    u = User(name="Login User", email="login@example.com", hashed_password=hash_password("secret123"), role=UserRole.RM)
    db.add(u); db.commit()
    assert client.post("/api/v1/auth/login", json={"email": "login@example.com", "password": "wrong"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": "login@example.com", "password": "secret123"}).status_code == 200
    actions = [e.action for e in db.query(AuditLog).filter(AuditLog.subject_type == "User", AuditLog.action.like("login%")).all()]
    assert actions == ["login_failed", "login"]
