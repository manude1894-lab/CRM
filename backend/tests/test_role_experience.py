"""Review 22-11-2026, package 5 (role experience): the Accounts desk's dashboard numbers."""
from decimal import Decimal

from app.models import Invoice
from app.services import dashboard_service


def test_dashboard_counts_invoices_to_raise_and_overdue(db, make_user, make_account):
    rm = make_user("Rita RM")
    acc = make_account(name="Ledger Ltd", spoc=rm, profile_status="Active")
    for status in ("Requested", "Requested", "Raised", "Overdue"):
        db.add(Invoice(account_id=acc.id, amount=Decimal("100"), currency="AED", status=status))
    db.commit()
    kpis = dashboard_service.build_dashboard(db, rm)["kpis"]
    assert (kpis["invoices_to_raise"], kpis["invoices_overdue"], kpis["invoices_unpaid"]) == (2, 1, 2)
