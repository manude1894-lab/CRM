"""Triam 22-11-2026.

- One person may be both RM and CO (or Approver). They never approve or reject a client they are the RM of, as
  Anchor or Non-anchor RM, under any of their logins, whoever submitted it.
- A Triam entity's code is required and short (2 to 6 letters / digits): it is the Client ID prefix.
"""
import pytest
from fastapi import HTTPException

from app.schemas.account import AccountUpdate
from app.schemas.master import MasterItemCreate
from app.services import account_service, amendment_service as amend, client_workflow_service as wf, master_service
from tests import flow


def _rm_co(make_user, make_role, name="Rita RM-CO", perms=("client.portfolio", "client.approve")):
    return make_user(name, business_role=make_role(f"{name} role", list(perms)))


def _action(db, acc, user, action):
    return {a["action"]: a for a in wf.allowed_actions(db, acc, user)}[action]


def test_anchor_rm_who_is_also_co_cannot_approve_even_if_someone_else_submitted(db, people, make_user, make_role):
    rita = _rm_co(make_user, make_role)
    acc = flow.complete_client(db, people["maker"])
    account_service.update_account(db, acc.id, AccountUpdate(spoc_id=rita.id), people["maker"])
    flow.submit(db, acc, people["maker"])
    flow.fill_cdd(db, acc, people["checker"])
    for action in ("approve", "reject"):
        a = _action(db, acc, rita, action)
        assert a["allowed"] is False and a["reason"] == "You are this client's RM, so another approver must review it"
    with pytest.raises(HTTPException) as e:
        wf.approve(db, acc, rita, "Looks fine")
    assert e.value.status_code == 403
    flow.compliance_approve(db, acc, people["checker"])  # another CO may
    assert acc.approval_stage == "Approver"


def test_a_non_anchor_rm_who_is_also_co_is_blocked_too(db, people, make_user, make_role):
    rita = _rm_co(make_user, make_role)
    acc = flow.complete_client(db, people["maker"])
    account_service.update_account(db, acc.id, AccountUpdate(non_anchor_rm_ids=[rita.id]), people["maker"])
    flow.submit(db, acc, people["maker"])
    flow.fill_cdd(db, acc, people["checker"])
    assert _action(db, acc, rita, "approve")["allowed"] is False


def test_the_rm_cannot_give_the_final_approval_under_another_login(db, people, make_user, make_role):
    rm = people["maker"]
    approver_login = make_user("Rita (Approver)", business_role=people["approver"].business_role)
    approver_login.person_id = rm.id  # the same person's Approver login
    db.commit()
    acc = flow.complete_client(db, people["other_rm"])
    account_service.update_account(db, acc.id, AccountUpdate(spoc_id=rm.id), people["other_rm"])
    flow.submit(db, acc, people["other_rm"])
    flow.compliance_approve(db, acc, people["checker"])
    a = _action(db, acc, approver_login, "approve")
    assert a["allowed"] is False and "client's RM" in a["reason"]
    wf.approve(db, acc, people["approver"], "Approved")  # another Approver may
    assert acc.profile_status == "Active"  # UAT 25-11-2026 row 180


def test_an_unrelated_co_still_approves(db, people, make_user, make_role):
    acc = flow.complete_client(db, people["maker"])
    flow.submit(db, acc, people["maker"])
    flow.fill_cdd(db, acc, people["checker"])
    assert _action(db, acc, people["checker"], "approve")["allowed"] is True


def test_the_clients_rm_cannot_approve_an_amendment(db, people, make_user, make_role, act_as):
    rita = _rm_co(make_user, make_role)
    acc = flow.approved_client(db, people)
    acc.non_anchor_rm_ids = [rita.id]  # Rita works on this approved client as a Non-anchor RM
    db.commit()
    amend.start(db, acc, people["maker"])
    account_service.update_account(db, acc.id, AccountUpdate(nature_of_business="Banking"), people["maker"])
    amend.submit(db, acc, people["maker"], "New business")
    assert "approve" not in amend.view(db, acc, rita)["actions"]
    with pytest.raises(HTTPException) as e:
        amend.approve(db, acc, rita)
    assert e.value.status_code == 403 and "client's RM" in e.value.detail
    act_as(people["checker2"])
    amend.approve(db, acc, people["checker2"])


@pytest.mark.parametrize("code", [None, "", "TPTL - Triam Professional & Prof Dev Mgmt LLC", "T", "TOOLONG1", "TP-TL"])
def test_a_triam_entity_needs_a_short_code(db, code):
    with pytest.raises(HTTPException) as e:
        master_service.create_item(db, "triam_entity", MasterItemCreate(label="TPTL - Triam Professional & Prof Dev Mgmt LLC", code=code))
    assert e.value.status_code == 400 and "2 to 6 letters or digits" in e.value.detail


def test_a_triam_entity_code_is_upper_cased_and_other_lists_keep_their_default(db):
    item = master_service.create_item(db, "triam_entity", MasterItemCreate(label="TPTL - Triam Professional & Prof Dev Mgmt LLC", code=" tptl "))
    assert item.code == "TPTL"
    tag = master_service.create_item(db, "tag", MasterItemCreate(label="Free Zone"))
    assert tag.code == "Free Zone"  # other lists: the code still defaults to the label
