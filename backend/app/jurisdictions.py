"""Per-jurisdiction rules registry.

The CRM was built BVI-first; this module makes the jurisdiction-specific bits
(compliance calendar, restoration checklist, strike-off period, statute names for
generated documents) data-driven. BVI is the fully-specified reference; every other
jurisdiction falls back to one BVI-shaped generic spec until its real rules are added.

Pure data — imports nothing from app.models / app.services.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ComplianceItemSpec:
    key: str                       # renewal | esr_filing | ar_filing | bo_filing
    label: str
    anchor: str                    # "anniversary" | "fixed:MM-DD" | "annual" | "event"
    cadence_months: int = 12
    reminder_days: tuple = (60, 30, 7)


@dataclass(frozen=True)
class JurisdictionSpec:
    code: str
    name: str
    company_law_name: str
    registry_name: str
    law_short: str
    strike_off_years: int
    rod_filing_days: int
    compliance_items: tuple
    restoration_checklist: tuple   # ((key, label), ...)
    closure_methods: tuple

    def item(self, key: str) -> ComplianceItemSpec | None:
        return next((i for i in self.compliance_items if i.key == key), None)


_BVI_RESTORATION = (
    ("ci", "Certificate of Incorporation (CI)"),
    ("rom", "Register of Members (ROM)"),
    ("rod", "Register of Directors (ROD)"),
    ("rod_stamped", "Register of Directors — stamped (ROD Stamped)"),
    ("moa", "Memorandum & Articles of Association (M&A)"),
    ("resolution_carrying_business", "Resolution on carrying on business"),
    ("es_fy_start_confirmation", "ES financial year start-date confirmation"),
    ("es_filing_2020_2024", "2020–2024 Economic Substance filing status"),
    ("ar_2023_form", "2023 Annual Return submission form"),
    ("ar_2024_form", "2024 Annual Return submission form"),
    ("bo_form", "BO / ROM-RBO form"),
    ("indemnity_letter", "Indemnity letter"),
    ("resolution_appointing_vistra", "Resolution appointing Vistra / RORA"),
    ("bvi_record_keeping_resolution", "BVI record-keeping resolution"),
    ("rom_bvi_form", "ROM BVI form"),
)

_GENERIC_RESTORATION = (
    ("ci", "Certificate of Incorporation"),
    ("rom", "Register of Members"),
    ("rod", "Register of Directors"),
    ("moa", "Memorandum & Articles of Association"),
    ("good_standing", "Certificate of Good Standing"),
    ("resolution_restore", "Resolution approving restoration"),
    ("outstanding_fees", "Outstanding fees & penalties settled"),
    ("indemnity_letter", "Indemnity letter"),
    ("agent_appointment", "Resolution appointing registered agent / office"),
)

_CLOSURE_METHODS = ("Voluntary Liquidation", "Voluntary Strike Off", "Lapse by Non-Payment")

_BVI = JurisdictionSpec(
    code="BVI",
    name="British Virgin Islands",
    company_law_name="BVI Business Companies Act, 2004",
    registry_name="Registrar of Corporate Affairs of the British Virgin Islands",
    law_short="British Virgin Islands law",
    strike_off_years=7,
    rod_filing_days=21,
    compliance_items=(
        ComplianceItemSpec("renewal", "Annual Licence Fee renewal", "anniversary", 12, (60, 30, 7)),
        ComplianceItemSpec("esr_filing", "Economic Substance (ESR) filing", "annual", 12, (30, 7)),
        ComplianceItemSpec("ar_filing", "Annual Return filing", "fixed:09-30", 12, (30, 7)),
        ComplianceItemSpec("bo_filing", "BO / ROM-RBO filing", "event", 12, (14, 7, 3)),
    ),
    restoration_checklist=_BVI_RESTORATION,
    closure_methods=_CLOSURE_METHODS,
)

_GENERIC = JurisdictionSpec(
    code="GENERIC",
    name="Offshore (generic)",
    company_law_name="the applicable Companies Act",
    registry_name="the Registrar of Companies",
    law_short="the laws of the jurisdiction of incorporation",
    strike_off_years=7,
    rod_filing_days=21,
    compliance_items=(
        ComplianceItemSpec("renewal", "Annual renewal / licence fee", "anniversary", 12, (60, 30, 7)),
        ComplianceItemSpec("esr_filing", "Economic substance filing", "annual", 12, (30, 7)),
        ComplianceItemSpec("ar_filing", "Annual return filing", "annual", 12, (30, 7)),
        ComplianceItemSpec("bo_filing", "Beneficial ownership filing", "event", 12, (14, 7, 3)),
    ),
    restoration_checklist=_GENERIC_RESTORATION,
    closure_methods=_CLOSURE_METHODS,
)

_REGISTRY = {"BVI": _BVI}

ALL_SPECS = (_BVI, _GENERIC)


def get(jurisdiction: str | None) -> JurisdictionSpec:
    return _REGISTRY.get((jurisdiction or "").strip(), _GENERIC)


def list_specs() -> list[dict]:
    return [
        {
            "code": s.code,
            "name": s.name,
            "strike_off_years": s.strike_off_years,
            "closure_methods": list(s.closure_methods),
            "compliance_items": [{"key": i.key, "label": i.label} for i in s.compliance_items],
            "restoration_checklist": [{"key": k, "label": lbl} for k, lbl in s.restoration_checklist],
        }
        for s in ALL_SPECS
    ]
