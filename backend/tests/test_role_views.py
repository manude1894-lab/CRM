"""Role views: central-desk users get a shorter menu and don't appear as RMs on the dashboard."""
from app.services import dashboard_service


def test_handles_clients_follows_the_roles(make_user, make_role):
    rm_role, approver = make_role("Rel. Manager", []), make_role("Approver", ["client.final_approve"])
    assert make_user(business_role=rm_role).handles_clients
    assert make_user().handles_clients  # no business role yet: client-facing by default
    assert not make_user(business_role=approver).handles_clients
    accounts = make_user(business_role=make_role("Accountant", ["invoice.manage"]))
    assert not accounts.handles_clients


def test_portfolio_lists_only_client_facing_users(db, make_user, make_role):
    rita = make_user("Rita RM", business_role=make_role("Rel. Manager", []))
    ada = make_user("Ada Approver", business_role=make_role("Approver", ["client.final_approve"]))
    admin = make_user(role="admin")
    names = {p["name"] for p in dashboard_service.build_dashboard(db, admin)["portfolio_by_rm"]}
    assert rita.name in names and ada.name not in names
