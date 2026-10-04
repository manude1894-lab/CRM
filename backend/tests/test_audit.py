"""BRD §13/§15 — every material change is recorded with who made it and what changed."""
from app.audit import log_event
from app.models import AuditLog, AccountParty, UserRole


def _entries(db, **filters):
    q = db.query(AuditLog)
    for k, v in filters.items():
        q = q.filter(getattr(AuditLog, k) == v)
    return q.order_by(AuditLog.id).all()


def test_create_is_logged_with_actor_and_client(db, make_user, make_account, act_as):
    rm = make_user("Aisha")
    act_as(rm)
    acc = make_account(name="Acme Holdings", risk_rating="Low")

    [entry] = _entries(db, subject_type="Account", action="create")
    assert entry.user_id == rm.id
    assert entry.account_id == acc.id
    assert entry.subject_id == acc.id
    assert entry.changes["company_name"] == "Acme Holdings"
    assert entry.ip_address == "127.0.0.1"
    assert "Acme Holdings" in entry.summary


def test_update_records_field_level_before_and_after(db, make_user, make_account, act_as):
    rm = make_user()
    acc = make_account(risk_rating="Low")
    act_as(rm)
    acc.risk_rating = "High"
    acc.kyc_status = "Approved"
    db.commit()

    [entry] = _entries(db, subject_type="Account", action="update")
    assert entry.changes == {"risk_rating": ["Low", "High"], "kyc_status": ["Not Started", "Approved"]}
    assert entry.user_id == rm.id


def test_old_value_is_captured_even_after_an_earlier_commit_expired_the_object(db, make_account):
    acc = make_account(risk_rating="Low")
    db.commit()  # expires acc — the next assignment happens without the old value loaded
    acc.risk_rating = "Medium"
    db.commit()
    entry = db.query(AuditLog).filter(AuditLog.action == "update").one()
    assert entry.changes["risk_rating"] == ["Low", "Medium"]


def test_no_entry_when_nothing_actually_changed(db, make_account):
    acc = make_account(risk_rating="Low")
    before = db.query(AuditLog).count()
    acc.risk_rating = "Low"
    db.commit()
    assert db.query(AuditLog).count() == before


def test_party_changes_are_attached_to_the_client(db, make_account):
    acc = make_account()
    db.add(AccountParty(account_id=acc.id, party_role="Shareholder", full_name="Jane Doe"))
    db.commit()
    [entry] = _entries(db, subject_type="AccountParty")
    assert entry.account_id == acc.id


def test_passwords_are_never_written(db, make_user):
    u = make_user()
    u.hashed_password = "new-hash"
    db.commit()
    [entry] = _entries(db, subject_type="User", action="update")
    assert entry.changes["hashed_password"] == ["<redacted>", "<redacted>"]
    create = _entries(db, subject_type="User", action="create")[0]
    assert create.changes["hashed_password"] == "<redacted>"


def test_delete_is_logged(db, make_account):
    acc = make_account(name="Gone Ltd")
    db.delete(acc)
    db.commit()
    [entry] = _entries(db, subject_type="Account", action="delete")
    assert "Gone Ltd" in entry.summary


def test_explicit_events(db, make_user):
    u = make_user(role=UserRole.ADMIN)
    log_event(db, "login", "Admin logged in", user_id=u.id, subject_type="User", subject_id=u.id)
    db.commit()
    [entry] = _entries(db, action="login")
    assert entry.user_id == u.id
