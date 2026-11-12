"""Triam UAT 12-11-2026: mobile numbers took letters, and a number could be saved with the "Code"
placeholder instead of a country code."""
import pytest
from pydantic import ValidationError

from app.schemas.account import AccountRead, AccountUpdate
from app.schemas.account_party import AccountPartyCreate, AccountPartyUpdate
from app.schemas.prospect import ProspectCreate, ProspectUpdate


@pytest.mark.parametrize("number", ["50abc1234", "five0123456", "123", "1234567890123"])
def test_mobile_numbers_are_6_to_12_digits(number):
    with pytest.raises(ValidationError):
        AccountPartyCreate(party_role="Director", full_name="Dina", mobile_country_code="+971", mobile_number=number)
    with pytest.raises(ValidationError):
        AccountUpdate(contact_mobile_country_code="+971", contact_mobile_number=number)


def test_spaces_and_dashes_are_tidied():
    p = AccountPartyCreate(party_role="Director", full_name="Dina", mobile_country_code="+971", mobile_number="50 123-4567")
    assert p.mobile_number == "501234567"


def test_a_number_needs_its_country_code():
    with pytest.raises(ValidationError, match="Select the country code"):
        AccountPartyCreate(party_role="Director", full_name="Dina", mobile_number="501234567")
    with pytest.raises(ValidationError, match="Select the country code"):
        AccountUpdate(individual_mobile_country_code="", individual_mobile_number="501234567")
    with pytest.raises(ValidationError, match="Select the country code"):
        AccountPartyUpdate(mobile_country_code=None, mobile_number="501234567")
    # A partial update that doesn't send the code keeps the stored one.
    assert AccountPartyUpdate(mobile_number="501234567").mobile_number == "501234567"


def test_prospect_phone_is_digits_with_an_optional_plus():
    assert ProspectCreate(company_name="X Ltd", contact_phone="+971 (50) 123-4567").contact_phone == "+971501234567"
    for bad in ("call me", "+971abc4567", "12+34567"):
        with pytest.raises(ValidationError):
            ProspectUpdate(contact_phone=bad)


def test_numbers_saved_before_the_rule_still_read_back():
    """The rule applies to create and update only: reading a client never fails on an old value."""
    from app.schemas.account import AccountCreate
    from app.schemas.account_party import AccountPartyRead
    assert "_mobile_digits" in AccountCreate.__pydantic_decorators__.field_validators
    assert "_mobile_digits" not in AccountRead.__pydantic_decorators__.field_validators
    assert "_code_with_number" not in AccountRead.__pydantic_decorators__.model_validators
    assert "_mobile_digits" not in AccountPartyRead.__pydantic_decorators__.field_validators
