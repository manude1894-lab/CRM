"""Pydantic schemas: jurisdiction registry (read-only catalog)."""
from pydantic import BaseModel


class ComplianceItemInfo(BaseModel):
    key: str
    label: str


class JurisdictionInfo(BaseModel):
    code: str
    name: str
    strike_off_years: int
    closure_methods: list[str]
    compliance_items: list[ComplianceItemInfo]
    restoration_checklist: list[ComplianceItemInfo]
