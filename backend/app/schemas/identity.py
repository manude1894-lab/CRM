"""Passport number format (Triam 20-11-2026), shared by the client and party schemas and the CSV import.

Letters and digits only, 6 to 12 characters; spaces and dashes are dropped and letters are upper-cased, so
"n 123-4567" is saved as "N1234567". Checked when a number is entered or changed; a blank stays blank (the
number is required at Submit, not on every save). Same rule on the form: frontend/src/utils/passport.js.
"""
import re
from typing import Optional

from pydantic import field_validator

MIN_PASSPORT, MAX_PASSPORT = 6, 12


def passport_number(v) -> Optional[str]:
    if v in (None, ""):
        return None
    v = re.sub(r"[\s-]", "", str(v)).upper()
    if not v:
        return None
    if not re.fullmatch(r"[A-Z0-9]+", v):
        raise ValueError("Passport Number takes letters and digits only")
    if not MIN_PASSPORT <= len(v) <= MAX_PASSPORT:
        raise ValueError(f"Passport Number must have {MIN_PASSPORT} to {MAX_PASSPORT} letters or digits")
    return v


def passport_validator(*fields):
    """A field validator applying passport_number to the named fields."""
    return field_validator(*fields, mode="before", check_fields=False)(classmethod(lambda cls, v: passport_number(v)))
