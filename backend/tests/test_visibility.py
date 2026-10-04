"""BRD §15 — RM privacy, supervisor visibility, role-based widening."""
from app.models import Account, Case, UserRole, CaseAdditionalRM
from app.services import access_control
from app.auth.permissions import user_permissions, has_permission


def visible(db, user):
    q = db.query(Account)
    clause = access_control.account_visibility_clause(db, user)
    if clause is not None:
        q = q.filter(clause)
    return {a.company_name for a in q.all()}


def test_rm_sees_clients_where_they_are_anchor_non_anchor_or_creator(db, make_user, make_account):
    me, other = make_user("Me"), make_user("Other")
    make_account("Anchor", spoc=me)
    make_account("NonAnchor", spoc=other, non_anchor=[me])
    make_account("Created", owner=me, spoc=other)
    make_account("Someone else's", owner=other, spoc=other)

    assert visible(db, me) == {"Anchor", "NonAnchor", "Created"}
    assert visible(db, other) == {"NonAnchor", "Created", "Someone else's"}


def test_supervisor_sees_their_whole_chain(db, make_user, make_account):
    head = make_user("Head")
    lead = make_user("Lead", supervisor=head)
    rm = make_user("RM", supervisor=lead)
    outsider = make_user("Outsider")
    make_account("RM client", spoc=rm)
    make_account("Lead client", spoc=lead)
    make_account("Outside client", spoc=outsider)

    assert visible(db, head) == {"RM client", "Lead client"}
    assert visible(db, lead) == {"RM client", "Lead client"}
    assert visible(db, rm) == {"RM client"}


def test_single_object_check_matches_the_list_filter(db, make_user, make_account):
    boss = make_user("Boss")
    rm = make_user("RM", supervisor=boss)
    stranger = make_user("Stranger")
    acc = make_account("X", spoc=rm)
    assert access_control.user_can_access_account(db, acc, rm)
    assert access_control.user_can_access_account(db, acc, boss)
    assert not access_control.user_can_access_account(db, acc, stranger)


def test_ops_screening_admin_keep_full_visibility(db, make_user, make_account):
    make_account("A", spoc=make_user())
    for role in (UserRole.ADMIN, UserRole.OPS, UserRole.SCREENING):
        assert visible(db, make_user(role=role)) == {"A"}


def test_view_all_clients_permission_lifts_rm_restriction(db, make_user, make_account, make_role):
    make_account("A", spoc=make_user())
    mlro = make_user(business_role=make_role("MLRO", ["view.all_clients"]))
    assert visible(db, mlro) == {"A"}


def test_department_permission(db, make_user, make_account, make_role):
    from app.models import Department
    sales, ops = Department(name="Sales"), Department(name="Ops")
    db.add_all([sales, ops]); db.commit()
    manager = make_user(department_id=sales.id, business_role=make_role("Sales Manager", ["view.department_clients"]))
    make_account("Sales client", spoc=make_user(department_id=sales.id))
    make_account("Ops client", spoc=make_user(department_id=ops.id))
    assert visible(db, manager) == {"Sales client"}


def test_inactive_role_grants_nothing(db, make_user, make_role):
    u = make_user(business_role=make_role("CO", ["client.approve"], is_active=False))
    assert user_permissions(u) == set()
    assert not has_permission(u, "client.approve")


def test_admin_has_every_permission(db, make_user):
    assert has_permission(make_user(role=UserRole.ADMIN), "master.manage")


def test_cycle_detection(db, make_user):
    a = make_user("A")
    b = make_user("B", supervisor=a)
    c = make_user("C", supervisor=b)
    assert access_control.would_create_supervisor_cycle(db, a.id, c.id)  # A reporting to C loops
    assert not access_control.would_create_supervisor_cycle(db, c.id, a.id)
    assert not access_control.would_create_supervisor_cycle(db, a.id, None)


def test_case_visibility_includes_team(db, make_user, make_account):
    boss = make_user("Boss")
    rm = make_user("RM", supervisor=boss)
    helper = make_user("Helper")
    stranger = make_user("Stranger")
    case = Case(case_uid="CASE-9001", company_name="Formation Co", rm_id=rm.id)
    db.add(case); db.commit()
    db.add(CaseAdditionalRM(case_id=case.id, user_id=helper.id)); db.commit()
    db.refresh(case)

    def sees(user):
        return db.query(Case).filter(access_control.rm_visibility_clause(user)).count() == 1

    assert sees(rm) and sees(boss) and sees(helper)
    assert not sees(stranger)
    assert access_control.user_can_access_case(case, boss)
    assert not access_control.user_can_access_case(case, stranger)
