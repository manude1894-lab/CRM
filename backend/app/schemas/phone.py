"""Mobile number rules shared by the client, party and prospect schemas (Triam UAT 12-11-2026, 13-11-2026 row 83).

- Digits only, always with a country code.
- Length, counted without the country code: a UAE number (+971) is 9 digits (mobile, 50 123 4567) or 8 (landline,
  4 333 4444); any other country 8 to 12 digits. Triam asked for 9 to 12; 8 is kept because GCC mobiles (Bahrain,
  Qatar, Kuwait, Oman) and UAE landlines are 8 digits. A leading trunk 0 (050 ...) is dropped.

Applied when a record is created or changed, never when it is read back, so a number saved before the
rule existed still displays and can be corrected. Same rules on the form: frontend/src/utils/mobile.js.
"""
import json
import re
from pathlib import Path
from typing import ClassVar, Optional

from pydantic import BaseModel, field_validator, model_validator

UAE_CODE = "+971"
MIN_DIGITS, MAX_DIGITS = 8, 12
_DIAL_CODES = sorted(set(json.loads((Path(__file__).resolve().parents[1] / "data" / "dial_codes.json").read_text(encoding="utf-8")).values()),
                     key=len, reverse=True)


def length_problem(code: Optional[str], number: str) -> Optional[str]:
    """Why a national number (no country code) has the wrong length for its country code, or None."""
    if code == UAE_CODE:
        return None if len(number) in (8, 9) else "a UAE number has 9 digits (mobile, e.g. 501234567) or 8 (landline)"
    return None if MIN_DIGITS <= len(number) <= MAX_DIGITS else f"mobile number must have {MIN_DIGITS} to {MAX_DIGITS} digits"


def mobile_number(v):
    """Digits only (spaces and dashes are dropped), at most 12; blank stays blank. The length for the country
    is checked with the country code (MobilePairRules)."""
    if v in (None, ""):
        return None
    v = re.sub(r"[\s-]", "", str(v))
    if not v.isdigit():
        raise ValueError("mobile number must contain digits only")
    if len(v) > MAX_DIGITS + 1:  # one more for a leading 0, dropped with the code
        raise ValueError(f"mobile number must have {MIN_DIGITS} to {MAX_DIGITS} digits")
    return v


def split_phone(v: str) -> tuple[Optional[str], str]:
    """'+971501234567' -> ('+971', '501234567'): the longest known country code that starts the number."""
    code = next((c for c in _DIAL_CODES if v.startswith(c)), None)
    return code, v[len(code):] if code else v


def phone(v):
    """A prospect's contact phone, one value with its country code: '+971501234567' (spaces, brackets and
    dashes are dropped). Same length rules as a mobile number."""
    if v in (None, ""):
        return None
    v = re.sub(r"[\s()-]", "", str(v))
    if not re.fullmatch(r"\+\d+", v):
        raise ValueError("phone must start with the country code, e.g. +971501234567, then digits only")
    code, number = split_phone(v)
    if code is None:
        raise ValueError("phone: the country code isn't recognised")
    number = number.lstrip("0")
    problem = length_problem(code, number)
    if problem:
        raise ValueError(f"phone: {problem}")
    return code + number


class MobilePairRules(BaseModel):
    """A mobile number is never saved without its country code, and has the length for that country. Subclasses
    list their (code, number) pairs in MOBILE_PAIRS and set PARTIAL for updates, where a code not sent may already
    be stored (then only the general 8 to 12 digits is checked)."""
    MOBILE_PAIRS: ClassVar[tuple] = ()
    PARTIAL: ClassVar[bool] = False

    @model_validator(mode="after")
    def _code_with_number(self):
        for code_field, number_field in self.MOBILE_PAIRS:
            number = getattr(self, number_field, None)
            if not number:
                continue
            code_known = not self.PARTIAL or code_field in self.model_fields_set
            code = getattr(self, code_field, None) if code_known else None
            if code_known and not code:
                raise ValueError("Select the country code for the mobile number")
            number = number.lstrip("0") or number
            setattr(self, number_field, number)
            problem = length_problem(code, number) if code else length_problem(None, number)
            if problem:
                raise ValueError(problem[0].upper() + problem[1:])
        return self


def number_validator(*fields):
    """A field validator applying mobile_number to the named fields."""
    return field_validator(*fields, mode="before", check_fields=False)(classmethod(lambda cls, v: mobile_number(v)))
