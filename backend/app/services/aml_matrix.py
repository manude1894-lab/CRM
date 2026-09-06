"""AML Risk Rating Matrix — factor catalog + scoring logic.

Transcribed from Triam's "AML RISK RATING MATRIX" (Annexure 6, version 8.0/6-25):
its factor lists, per-factor weights, the option->rating lookup tables, the
Score(1/3/5) mapping, the total-score bands, and the override rules.

Pure logic — the only DB touch is the CountryRisk lookup, passed in as a dict.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

AML_MATRIX_VERSION = "8.0/6-25"

RATING_SCORE = {"Low": 1, "Medium": 3, "High": 5, "Prohibited": 5}

# Total weighted score -> overall rating band (paper form's "Legend").
BANDS = [
    (Decimal("0"), Decimal("1.99"), "Low"),
    (Decimal("2"), Decimal("2.74"), "Medium"),
    (Decimal("2.75"), Decimal("999"), "High"),
]

# The PEP dropdown option that forces the overall rating to High.
PEP_HIGH_OPTION = "PEP Risk Assessment Completed - High Risk"

# ─── Option -> rating lookup tables (from the document's reference sheets) ──────

BUSINESS_SECTOR = {
    "Salaried Individual": "Low",
    "Student": "Low",
    "Retired Individual": "Low",
    "Dependent Spouse/Child": "Low",
    "Employed with a DFSA/FSRA/similar regulated Firm": "Low",
    "Any other business/employment not falling under Medium or High risk activities": "Low",
    "Practicing professionals (such as Accountants, Lawyers)": "Medium",
    "Non-cash intensive business": "Medium",
    "Any other business/employment not falling under Low or High risk activities": "Medium",
    "Business": "Medium",
    "Cash Intensive business": "High",
    "Real estate broker": "High",
    "Dealers in precious metals and stones or High Value Items": "High",
    "Any other High Risk business/employment": "High",
}

CUSTOMER_INTERFACE = {
    "Face-to-Face KYC (Physical meeting)": "Low",
    "Face-to-Face KYC via Zoom meeting": "Medium",
    "Non-Face-to-Face KYC": "High",
}

PRODUCTS_SERVICES = {
    "Management Consulting": "Medium",
    "Compliance & Risk management": "Medium",
    "Administrative Management Activities": "Medium",
    "Accounting, Book-keeping or Auditing Services": "High",
    "Legal Services": "High",
    "Real Estate Brokerage, Property Development": "High",
    "Dealers in Precious Metals and Stones": "High",
    "Money Services Businesses": "High",
    "Luxury Goods and High Value Items": "High",
    "Trust & Secretarial Services": "High",
    "Company Service Providers": "High",
}

PEP_RISK = {
    "Client/UBO is not a PEP": "Low",
    "Client/UBO is not a PEP but may have a high profile": "Medium",
    "PEP Risk Assessment Completed - Low Risk": "Low",
    "PEP Risk Assessment Completed - Medium Risk": "Medium",
    "PEP Risk Assessment Completed - High Risk": "High",
}

# Wording/ratings inferred from the sample + the Score column — confirm with client.
PROLIFERATION_RISK = {
    "Client confirmed that he does not deal in any dual-use products as per UAE control list": "Low",
    "Client confirmed import of dual-use products (as per UAE control list) & sells in the local (UAE) market only": "Medium",
    "Client confirmed that it is engaged in the business of import & export of dual-use goods (as per UAE control list)": "High",
}

CUSTOMER_INTRODUCTION = {
    "Known to the Firm or one of its employees for more than 3 yrs": "Low",
    "Known to the Firm or one of its employees for less than 3 yrs": "Medium",
    "Referred by an existing/previous Customer": "Medium",
    "Referred by an introducer (not known by the Firm or its employees)": "High",
}

TAX_CRIME_RISK = {
    "Customer is regulated and has policies and procedures in place with regards to tax compliance": "Low",
    "Customer does not fall into one of the medium or high risk factors": "Low",
    "Customer does not fall into one of the low or high risk factors": "Medium",
    "Customer being unable or unwilling to disclose the source of funds or wealth": "High",
    "Customer does not have requisite policies & procedures to mitigate tax crime risks": "High",
    "Customer's business not located where Customer is incorporated without adequate explanation": "High",
    "Reluctance by Customer to communicate directly with the Firm": "High",
    "Use of tax havens without adequate explanation": "High",
    "Use of complex and unusual structure without adequate explanation": "High",
}

REPUTATIONAL_RISK = {
    "No adverse information found": "Low",
    "Adverse information found on the Customer - not material or not proven": "Medium",
    "Adverse information found on the Customer - material and/or proven": "High",
}

BUSINESS_RISK_ASSESSMENT = {
    "Most recent AML Business Risk Assessment concluded overall risk as low": "Low",
    "Most recent AML Business Risk Assessment concluded overall risk as medium": "Medium",
    "Most recent AML Business Risk Assessment concluded overall risk as high": "High",
}

# The document only fully shows one option ("Any other structure..." = Low). The rest
# is a reasonable default set — flagged in the plan for client confirmation.
CUSTOMER_TYPE = {
    "Regulated / listed entity": "Low",
    "Any other structure which does not fall under High or Medium": "Low",
    "Private limited company": "Medium",
    "Partnership / LLP": "Medium",
    "Trust or foundation": "High",
    "Company with bearer shares or nominee shareholders": "High",
    "Complex multi-layer / multi-jurisdiction structure": "High",
}

_COUNTRY = "country"

# ─── Factor catalogs: (key, label, weight %, kind) ─────────────────────────────
# kind is _COUNTRY (resolved via CountryRisk) or an option->rating dict above.

ENTITY_FACTORS = [
    ("country_incorporation", "Country of Incorporation/Registration", Decimal("15"), _COUNTRY),
    ("country_operations", "Country of Operations/Residence", Decimal("15"), _COUNTRY),
    ("ubo_nationality", "UBO's Country of Nationality", Decimal("15"), _COUNTRY),
    ("ubo_residence", "UBO's Country of Residence", Decimal("15"), _COUNTRY),
    ("customer_type", "Customer Type (legal structure)", Decimal("10"), CUSTOMER_TYPE),
    ("business_activity", "Customer's Business activity/sector", Decimal("10"), BUSINESS_SECTOR),
    ("customer_interface", "Customer interface", Decimal("2.5"), CUSTOMER_INTERFACE),
    ("products_services", "Products & services offered", Decimal("2.5"), PRODUCTS_SERVICES),
    ("pep_risk", "Ownership/Control (PEP risk)", Decimal("2.5"), PEP_RISK),
    ("proliferation_risk", "Proliferation Risk", Decimal("2.5"), PROLIFERATION_RISK),
    ("customer_introduction", "Customer Introduction", Decimal("2.5"), CUSTOMER_INTRODUCTION),
    ("tax_crime_risk", "Tax Crime Risk", Decimal("2.5"), TAX_CRIME_RISK),
    ("reputational_risk", "Reputational risk", Decimal("2.5"), REPUTATIONAL_RISK),
    ("business_risk", "Business Risk Assessment (from latest assessment)", Decimal("2.5"), BUSINESS_RISK_ASSESSMENT),
]

INDIVIDUAL_FACTORS = [
    ("country_nationality", "Country of citizenship/nationality", Decimal("20"), _COUNTRY),
    ("country_residence", "Country of residence", Decimal("20"), _COUNTRY),
    ("business_sector", "Customer's Business/employment sector", Decimal("20"), BUSINESS_SECTOR),
    ("customer_interface", "Customer interface", Decimal("5"), CUSTOMER_INTERFACE),
    ("products_services", "Products & services offered", Decimal("5"), PRODUCTS_SERVICES),
    ("pep_risk", "PEP Risk", Decimal("5"), PEP_RISK),
    ("proliferation_risk", "Proliferation Risk", Decimal("5"), PROLIFERATION_RISK),
    ("customer_introduction", "Customer Introduction", Decimal("5"), CUSTOMER_INTRODUCTION),
    ("tax_crime_risk", "Tax Crime Risk", Decimal("5"), TAX_CRIME_RISK),
    ("reputational_risk", "Reputational risk", Decimal("5"), REPUTATIONAL_RISK),
    ("business_risk", "Business Risk Assessment (from latest assessment)", Decimal("5"), BUSINESS_RISK_ASSESSMENT),
]


def factors_for(subject_type: str):
    return ENTITY_FACTORS if subject_type == "Entity" else INDIVIDUAL_FACTORS


def band(total: Decimal) -> str:
    for lo, hi, label in BANDS:
        if lo <= total <= hi:
            return label
    return "High"


@dataclass
class MatrixResult:
    factors: list[dict]
    total_weighted_score: Decimal
    calculated_rating: str
    override_reason: str | None = None
    onboarding_blocked: bool = False
    missing_keys: list[str] = field(default_factory=list)


def calculate(
    subject_type: str,
    selections: dict[str, str],
    country_lookup: dict[str, dict],
) -> MatrixResult:
    """Score a matrix.

    selections     — {factor_key: chosen option string}
    country_lookup — {country_name: {"risk_level", "score", "default_to_high"}}
    """
    rows: list[dict] = []
    total = Decimal("0")
    override_reasons: list[str] = []
    blocked = False
    missing: list[str] = []

    for key, label, weight, kind in factors_for(subject_type):
        chosen = selections.get(key)
        if not chosen:
            missing.append(key)

        if kind is _COUNTRY:
            cr = country_lookup.get(chosen or "")
            if cr:
                rating = cr["risk_level"]
                score = int(cr["score"])
                if cr["risk_level"] == "Prohibited":
                    blocked = True
                    override_reasons.append(f"{label}: {chosen} is a prohibited jurisdiction")
                elif cr.get("default_to_high"):
                    override_reasons.append(f"{label}: {chosen} is FATF-listed")
            else:
                # Unknown / unselected country — conservative default.
                rating, score = "High", 5
        else:
            rating = kind.get(chosen or "", "Medium")
            score = RATING_SCORE[rating]

        weighted = (Decimal(score) * weight / Decimal("100")).quantize(Decimal("0.001"))
        total += weighted
        rows.append({
            "key": key,
            "label": label,
            "input": chosen,
            "rating": rating,
            "score": score,
            "weight": float(weight),
            "weighted_score": float(weighted),
        })

    total = total.quantize(Decimal("0.01"))
    rating = band(total)

    if selections.get("pep_risk") == PEP_HIGH_OPTION:
        override_reasons.append("PEP risk assessed as High")

    if override_reasons:
        rating = "High"

    return MatrixResult(
        factors=rows,
        total_weighted_score=total,
        calculated_rating=rating,
        override_reason="; ".join(override_reasons) or None,
        onboarding_blocked=blocked,
        missing_keys=missing,
    )


def catalog() -> dict:
    """Factor definitions + option lists, for the frontend to render the form
    and mirror the live-preview calculation."""
    def serialise(defs):
        out = []
        for key, label, weight, kind in defs:
            out.append({
                "key": key,
                "label": label,
                "weight": float(weight),
                "kind": "country" if kind is _COUNTRY else "options",
                "options": None if kind is _COUNTRY
                else [{"value": k, "rating": v} for k, v in kind.items()],
            })
        return out

    return {
        "version": AML_MATRIX_VERSION,
        "rating_score": RATING_SCORE,
        "bands": [[float(lo), float(hi), label] for lo, hi, label in BANDS],
        "pep_high_option": PEP_HIGH_OPTION,
        "entity_factors": serialise(ENTITY_FACTORS),
        "individual_factors": serialise(INDIVIDUAL_FACTORS),
    }
