"""Seed the database.

    python -m app.seed --minimal   support account + country list only (production / client deployments)
    python -m app.seed             also demo users, one per Triam desk, and a few prospects to walk the
                                   BRD flow: Prospect → Client (RM) → Compliance (MLRO) → Approver

Departments, roles, Triam entities, services and the other master lists come from the migrations.
"""
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import User, UserRole, Role, Prospect
from app.auth.security import hash_password
from app.services.countries_service import seed_countries
from app.utils.uid import next_uid

SUPPORT_EMAIL = "admin@ezeetechgroup.com"

# (name, email, password, user type, business role)
DEMO_USERS = [
    ("Triam Admin", "admin@asktriam.com", "Admin-2026-demo", UserRole.ADMIN, None),
    ("Priya Coordinator", "priya@asktriam.com", "Demo-2026-pass", UserRole.RM, "Prospecting Coordinator"),
    ("Kalyan", "kalyan@asktriam.com", "Demo-2026-pass", UserRole.RM, "Rel. Manager"),
    ("Aisha", "aisha@asktriam.com", "Demo-2026-pass", UserRole.RM, "Rel. Manager"),
    ("Ritu (MLRO)", "mlro@asktriam.com", "Demo-2026-pass", UserRole.RM, "MLRO"),
    ("Girish (Approver)", "approver@asktriam.com", "Demo-2026-pass", UserRole.RM, "Approver"),
    ("Swathi (Accounts)", "accounts@asktriam.com", "Demo-2026-pass", UserRole.RM, "Accountant"),
    ("Inquiry Desk", "inquiry@asktriam.com", "Demo-2026-pass", UserRole.RM, "Inquiry"),
]

DEMO_PROSPECTS = [
    ("Meridian Capital Partners Ltd", "Karim Haddad", None),
    ("Alpine Fintech Solutions", "Emily Foster", "kalyan@asktriam.com"),
    ("Zenith Wealth Advisors", "Rashid Al Naqbi", "aisha@asktriam.com"),
]


def seed_minimal(db: Session) -> None:
    """The Ezee Tech support account only, so the CRM starts empty."""
    if db.query(User).count() > 0:
        print("Seed skipped: users already exist.")
        return
    db.add(User(name="Admin User", email=SUPPORT_EMAIL, hashed_password=hash_password("admin123"),
                role=UserRole.ADMIN, is_active=True, is_super_admin=True))
    db.commit()
    print(f"Created support account: {SUPPORT_EMAIL} / admin123")


def seed_demo(db: Session) -> None:
    roles = {r.name: r for r in db.query(Role).all()}
    users = {}
    for name, email, password, user_type, role_name in DEMO_USERS:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(name=name, email=email, hashed_password=hash_password(password), role=user_type, is_active=True,
                        business_role_id=roles[role_name].id if role_name in roles else None)
            db.add(user)
            print(f"  {email:28s} {password:18s} {role_name or 'Administrator'}")
        users[email] = user
    db.flush()
    for company, contact, rm_email in DEMO_PROSPECTS:
        if db.query(Prospect).filter(Prospect.company_name == company).first():
            continue
        db.add(Prospect(prospect_uid=next_uid(db, Prospect, "prospect_uid", "PROS"), company_name=company,
                        contact_name=contact, owner_id=users[rm_email].id if rm_email else None))
        db.flush()
    db.commit()
    print(f"Seeded {len(DEMO_USERS)} demo users and {len(DEMO_PROSPECTS)} prospects.")


def main():
    import sys
    db = SessionLocal()
    try:
        n = seed_countries(db)
        if n:
            print(f"-> Seeded the country list ({n} countries)")
        seed_minimal(db)
        if "--minimal" not in sys.argv:
            seed_demo(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
