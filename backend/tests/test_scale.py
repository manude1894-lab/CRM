"""Review 22-11-2026, package 4 (scale): client lists are filtered, sorted and paged on the server; the dashboard's
"Due soon" covers every client the user may see; reports load related rows in bulk."""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import event

from app.models import Prospect
from app.services import account_service, dashboard_service, standard_reports_service as rpt
from tests.helpers import auth


def _clients(make_account, rm, n=7):
    now = datetime.now(timezone.utc)
    out = []
    for i in range(n):
        out.append(make_account(name=f"Client {i:02d}", spoc=rm, profile_status=["WIP", "Active", "Dropped"][i % 3],
                                risk_rating=["Low", "High"][i % 2], approved_at=now - timedelta(days=10 * i)))
    return out


def test_statuses_search_risk_and_paging(db, make_user, make_account):
    rm = make_user("Rita RM")
    _clients(make_account, rm)
    items, total = account_service.list_accounts(db, rm, statuses=["WIP", "Active"])
    assert total == 5 and {a.profile_status for a in items} == {"WIP", "Active"}  # Dropped left out
    first, total = account_service.list_accounts(db, rm, statuses=["WIP", "Active"], skip=0, limit=2)
    second, _ = account_service.list_accounts(db, rm, statuses=["WIP", "Active"], skip=2, limit=2)
    assert total == 5 and len(first) == 2 and not {a.id for a in first} & {a.id for a in second}
    assert [a.company_name for a in account_service.list_accounts(db, rm, search="client 03")[0]] == ["Client 03"]
    assert all(a.risk_rating == "High" for a in account_service.list_accounts(db, rm, risk="High")[0])


def test_approved_since_and_sorts(db, make_user, make_account):
    rm = make_user("Rita RM")
    _clients(make_account, rm)
    recent, _ = account_service.list_accounts(db, rm, approved_since=date.today() - timedelta(days=25))
    assert {a.company_name for a in recent} == {"Client 00", "Client 01", "Client 02"}
    by_approval, _ = account_service.list_accounts(db, rm, sort="-approved")
    assert [a.company_name for a in by_approval][:2] == ["Client 00", "Client 01"]  # latest approval first


def test_search_finds_the_prospect_id(db, make_user, make_account):
    rm = make_user("Rita RM")
    p = Prospect(prospect_uid="PROS-0420", company_name="Zenith", owner_id=rm.id)
    db.add(p)
    db.commit()
    make_account(name="Zenith Wealth", spoc=rm, prospect_id=p.id)
    assert [a.company_name for a in account_service.list_accounts(db, rm, search="PROS-0420")[0]] == ["Zenith Wealth"]


def test_the_route_takes_the_filters_and_caps_the_page(client, db, make_user, make_account):
    rm = make_user("Rita RM")
    _clients(make_account, rm)
    r = client.get("/api/v1/accounts", params={"statuses": "Active,Dropped", "sort": "-approved", "limit": 2}, headers=auth(rm))
    assert r.status_code == 200 and r.json()["total"] == 4 and len(r.json()["items"]) == 2
    assert client.get("/api/v1/accounts", params={"limit": 5000}, headers=auth(rm)).status_code == 422


def test_due_soon_covers_every_client(db, make_user, make_account):
    rm = make_user("Rita RM")
    today = date.today()
    for i in range(250):  # more than the 200 the screen used to load
        make_account(name=f"Serviced {i:03d}", spoc=rm, profile_status="Active", license_expiry_date=today + timedelta(days=400))
    late = make_account(name="Late Ltd", spoc=rm, profile_status="Active", license_expiry_date=today - timedelta(days=3))
    make_account(name="Being onboarded", spoc=rm, profile_status="WIP", license_expiry_date=today)
    due = dashboard_service.build_dashboard(db, rm)["due_soon"]
    assert [(d["account_id"], d["what"], d["days"]) for d in due] == [(late.id, "Trade licence expiry", -3)]


def test_reports_load_people_in_bulk(db, make_user, make_account):
    """The documents report reads every client's people; the queries must not grow with the number of clients."""
    rm = make_user("Rita RM")
    for i in range(30):
        make_account(name=f"Bulk {i}", spoc=rm, license_expiry_date=date.today() + timedelta(days=5))
    db.expire_all()
    statements = []
    listener = lambda *args: statements.append(1)  # noqa: E731
    event.listen(db.get_bind(), "before_cursor_execute", listener)
    try:
        rpt.documents_expiring(db, rm)
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", listener)
    assert len(statements) < 15  # about 5 queries, not 30+


def test_every_column_sorts_both_ways(db, make_user, make_account):
    rita, bob = make_user("Rita RM"), make_user("Bob RM")
    make_account(name="Alpha", spoc=rita, risk_rating="Low", client_id="TCPL/00002", is_pep=True)
    make_account(name="beta", spoc=bob, risk_rating="High", client_id="TCPL/00001")
    make_account(name="Gamma", spoc=bob, risk_rating=None, client_id=None)
    admin = make_user("Ada Admin", role="admin")
    names = lambda sort: [a.company_name for a in account_service.list_accounts(db, admin, sort=sort)[0]]  # noqa: E731
    assert names("name") == ["Alpha", "beta", "Gamma"] and names("-name") == ["Gamma", "beta", "Alpha"]
    assert names("risk") == ["beta", "Alpha", "Gamma"] and names("-risk") == ["Alpha", "beta", "Gamma"]  # blank last
    assert names("client_id")[:2] == ["beta", "Alpha"]
    assert names("rm") == ["beta", "Gamma", "Alpha"]  # Bob before Rita
    assert names("pep")[0] == "Alpha"
