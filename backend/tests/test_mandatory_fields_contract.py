"""The submit rule against the shared contract, which the form's asterisks are tested against too
(frontend accountForm.test.js). UAT 04/05/06-11-2026: UAT-03, UAT-10, UAT-11, UAT-21."""
import json
from pathlib import Path

import pytest

from app.models import Account
from app.services import account_service

CONTRACT = json.loads((Path(__file__).parent / "contracts" / "mandatory_fields.json").read_text(encoding="utf-8"))
NOT_FORM_FIELDS = {"parties", "documents"}


def expected(case):
    return {f for group in case["groups"] for f in CONTRACT[group]} | set(case["extra"])


@pytest.mark.parametrize("case", CONTRACT["cases"], ids=[c["name"] for c in CONTRACT["cases"]])
def test_submit_rule_matches_the_contract(case):
    account = Account(account_uid="X", **case["form"])
    missing = {m["field"] for m in account_service.missing_mandatory(account)} - NOT_FORM_FIELDS
    # A field the case fills in isn't missing, though it stays mandatory.
    filled = {f for f in case["form"] if f in expected(case)}
    assert missing | filled == expected(case)
