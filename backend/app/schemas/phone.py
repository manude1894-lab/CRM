"""Mobile number rules shared by the client, party and prospect schemas (Triam UAT 12-11-2026).

Applied when a record is created or changed, never when it is read back, so a number saved before the
rule existed still displays and can be corrected.
"""
import re
from typing import ClassVar

from pydantic import BaseModel, field_validator, model_validator


def mobile_number(v):
    """Digits only (spaces and dashes are dropped), 6 to 12 digits; blank stays blank."""
    if v in (None, ""):
        return None
    v = re.sub(r"[\s-]", "", str(v))
    if not v.isdigit():
        raise ValueError("mobile number must contain digits only")
    if not 6 <= len(v) <= 12:
        raise ValueError("mobile number must have 6 to 12 digits")
    return v


def phone(v):
    """A contact phone: digits with an optional leading + (spaces, brackets and dashes are dropped)."""
    if v in (None, ""):
        return None
    v = re.sub(r"[\s()-]", "", str(v))
    if not re.fullmatch(r"\+?\d{6,15}", v):
        raise ValueError("phone must be digits, with an optional leading +")
    return v


class MobilePairRules(BaseModel):
    """A mobile number is never saved without its country code. Subclasses list their (code, number) pairs
    in MOBILE_PAIRS and set PARTIAL for updates, where a code not sent may already be stored."""
    MOBILE_PAIRS: ClassVar[tuple] = ()
    PARTIAL: ClassVar[bool] = False

    @model_validator(mode="after")
    def _code_with_number(self):
        for code_field, number_field in self.MOBILE_PAIRS:
            if not getattr(self, number_field, None):
                continue
            code_known = not self.PARTIAL or code_field in self.model_fields_set
            if code_known and not getattr(self, code_field, None):
                raise ValueError("Select the country code for the mobile number")
        return self


def number_validator(*fields):
    """A field validator applying mobile_number to the named fields."""
    return field_validator(*fields, mode="before", check_fields=False)(classmethod(lambda cls, v: mobile_number(v)))
