"""Shared pytest fixtures.

Tests run against an in-memory SQLite database built from the SQLAlchemy models (no Postgres
needed). Every model column type used by the app works on SQLite. Each test gets a fresh schema.
"""
import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # make `app` importable
os.environ.setdefault("JWT_SECRET_KEY", "test-access-secret-test-access-secret")
os.environ.setdefault("JWT_REFRESH_SECRET_KEY", "test-refresh-secret-test-refresh-secret")

from app.database import Base  # noqa: E402
import app.models  # noqa: E402,F401  — registers every model on Base.metadata
import app.audit  # noqa: E402,F401  — registers the audit listener
from app.models import User, UserRole, Account, Role, MasterItem  # noqa: E402
from app.audit import set_actor  # noqa: E402


@pytest.fixture()
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    yield session
    session.close()


_counter = {"n": 0}


def _next(prefix):
    _counter["n"] += 1
    return f"{prefix}-{_counter['n']:04d}"


@pytest.fixture()
def make_user(db):
    def _make(name="User", role=UserRole.RM, supervisor=None, department_id=None, business_role=None):
        u = User(name=name, email=f"{_next('u').lower()}@example.com", hashed_password="x", role=role,
                 supervisor_id=supervisor.id if supervisor else None, department_id=department_id,
                 business_role_id=business_role.id if business_role else None)
        db.add(u)
        db.commit()
        db.refresh(u)
        return u
    return _make


@pytest.fixture()
def make_account(db):
    def _make(name=None, owner=None, spoc=None, non_anchor=None, **fields):
        acc = Account(account_uid=_next("ACC"), company_name=name or _next("Client"),
                      owner_id=owner.id if owner else None, spoc_id=spoc.id if spoc else None,
                      non_anchor_rm_ids=[u.id for u in non_anchor] if non_anchor else None, **fields)
        db.add(acc)
        db.commit()
        db.refresh(acc)
        return acc
    return _make


@pytest.fixture()
def make_role(db):
    def _make(name, permissions, is_active=True):
        r = Role(name=name, permissions=permissions, is_active=is_active)
        db.add(r)
        db.commit()
        db.refresh(r)
        return r
    return _make


@pytest.fixture()
def seed_master(db):
    def _seed(list_type, codes, inactive=()):
        for i, c in enumerate(codes):
            db.add(MasterItem(list_type=list_type, code=c, label=c, sort_order=i, is_active=True))
        for c in inactive:
            db.add(MasterItem(list_type=list_type, code=c, label=c, sort_order=99, is_active=False))
        db.commit()
    return _seed


@pytest.fixture()
def act_as(db):
    """Attribute subsequent changes on this session to a user (what get_current_user does)."""
    def _act(user):
        set_actor(db, user.id if user else None, "127.0.0.1")
    return _act
