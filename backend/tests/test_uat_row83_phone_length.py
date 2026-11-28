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
    with pytest.raises(ValidationError, match=r"\+44 number has 9 to 10 digits"):
        AccountPartyUpdate(mobile_country_code="+44", mobile_number="1234567")


@pytest.mark.parametrize("code, ok, bad", [
    ("+91", "9876543210", "987654321"),        # India 10
    ("+1", "2025550123", "20255501234"),       # USA / Canada 10
    ("+44", "7911123456", "79111234567"),      # UK 9 to 10
    ("+966", "501234567", "5012345678"),       # Saudi Arabia 8 to 9
    ("+974", "33123456", "331234567"),         # Qatar 8
    ("+65", "81234567", "812345678"),          # Singapore 8
    ("+49", "15123456789", "1234567"),         # any other country 8 to 12
])
def test_length_per_country(code, ok, bad):
    """Triam 28-11-2026: each country's own length; others 8 to 12."""
    assert AccountPartyUpdate(mobile_country_code=code, mobile_number=ok).mobile_number == ok
    with pytest.raises(ValidationError):
        AccountPartyUpdate(mobile_country_code=code, mobile_number=bad)


def test_screen_uses_the_same_lengths_as_the_server():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    server = json.loads((root / "backend/app/data/phone_lengths.json").read_text(encoding="utf-8"))
    screen = json.loads((root / "frontend/src/utils/phoneLengths.json").read_text(encoding="utf-8"))
    assert {k: v for k, v in server.items() if not k.startswith("_")} == {k: v for k, v in screen.items() if not k.startswith("_")}
