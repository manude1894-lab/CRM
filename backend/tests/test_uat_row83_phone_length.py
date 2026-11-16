"""Triam UAT 13-11-2026 row 83: contact number length. UAE 9 digits (mobile) or 8 (landline); others 8 to 12."""
import pytest
from pydantic import ValidationError

from app.schemas.account_party import AccountPartyUpdate
from app.schemas.prospect import ProspectCreate


def test_prospect_phone_has_its_country_code_and_length():
    assert ProspectCreate(company_name="A", contact_phone="+971 050 123 4567").contact_phone == "+971501234567"
    assert ProspectCreate(company_name="A", contact_phone="+97343334444").contact_phone == "+97343334444"  # Bahrain, 8
    for bad in ("+97150123", "+9715012345678", "0501234567", "+44 1234567"):
        with pytest.raises(ValidationError):
            ProspectCreate(company_name="A", contact_phone=bad)


def test_mobile_length_follows_the_country_code():
    assert AccountPartyUpdate(mobile_country_code="+971", mobile_number="0501234567").mobile_number == "501234567"
    assert AccountPartyUpdate(mobile_country_code="+971", mobile_number="43334444").mobile_number == "43334444"
    assert AccountPartyUpdate(mobile_country_code="+974", mobile_number="33123456").mobile_number == "33123456"
    with pytest.raises(ValidationError, match="UAE number has 9 digits"):
        AccountPartyUpdate(mobile_country_code="+971", mobile_number="5012345678")
    with pytest.raises(ValidationError, match="8 to 12 digits"):
        AccountPartyUpdate(mobile_country_code="+44", mobile_number="1234567")
