"""Service layer: Countries master (BRD §17) — the list behind every country drop-down."""
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.audit import log_event
from app.models import CountryRisk
from app.schemas.country import CountryCreate, CountryUpdate

SCORE = {"Low": 1, "Medium": 3, "High": 5}

_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "country_risk.json"


def seed_countries(db: Session) -> int:
    """Idempotently load the country list. Returns rows inserted."""
    if db.query(CountryRisk).count() > 0:
        return 0
    payload = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    rows = [
        CountryRisk(
            name=c["name"],
            code=c.get("code"),
            kyc_score=Decimal(str(c["kyc_score"])) if c.get("kyc_score") is not None else None,
            risk_level=c["risk_level"],
            score=int(c["score"]),
            default_to_high=bool(c.get("default_to_high", False)),
        )
        for c in payload["countries"]
    ]
    db.add_all(rows)
    db.commit()
    return len(rows)


def list_countries(db: Session) -> list[CountryRisk]:
    return db.query(CountryRisk).order_by(CountryRisk.name).all()


def create_country(db: Session, data: CountryCreate) -> CountryRisk:
    name = data.name.strip()
    if db.query(CountryRisk).filter(CountryRisk.name == name).first():
        raise HTTPException(status_code=400, detail="Country already exists")
    c = CountryRisk(name=name, code=(data.code or "").upper() or None, risk_level=data.risk_level,
                    score=SCORE[data.risk_level], changed_at=datetime.now(timezone.utc))
    db.add(c)
    db.flush()
    log_event(db, "country_add", f"Country {name} added ({c.code or 'no code'}, {c.risk_level} risk)",
              subject_type="Country", subject_id=c.id)
    db.commit()
    db.refresh(c)
    return c


def update_country(db: Session, country_id: int, data: CountryUpdate) -> CountryRisk:
    """Admin changes a country's name, code or risk; the change is stamped and kept in the audit log."""
    c = db.get(CountryRisk, country_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Country not found")
    new = data.model_dump(exclude_unset=True)
    if "name" in new:
        new["name"] = new["name"].strip()
        other = db.query(CountryRisk).filter(CountryRisk.name == new["name"], CountryRisk.id != c.id).first()
        if other:
            raise HTTPException(status_code=400, detail="Country already exists")
    if "code" in new:
        new["code"] = (new["code"] or "").upper() or None
    changes = {k: {"old": getattr(c, k), "new": v} for k, v in new.items() if v is not None and getattr(c, k) != v}
    if not changes:
        return c
    for k, v in changes.items():
        setattr(c, k, v["new"])
    if "risk_level" in changes:
        c.score = SCORE[c.risk_level]
    c.changed_at = datetime.now(timezone.utc)
    summary = "; ".join(f"{k.replace('_', ' ')} {v['old'] or '—'} → {v['new']}" for k, v in changes.items())
    log_event(db, "country_update", f"Country {c.name}: {summary}", subject_type="Country", subject_id=c.id, changes=changes)
    db.commit()
    db.refresh(c)
    return c


def high_risk_links(db: Session, account) -> list[dict]:
    """Where the client and its parties touch a High-risk country (registration, addresses, nationality,
    residence, birth), for Compliance when setting the CDD/AML risk level."""
    high = {c.name.strip().lower(): c.name for c in db.query(CountryRisk).filter(CountryRisk.risk_level == "High")}
    found = []

    def add(country, who, field):
        name = high.get((country or "").strip().lower())
        if name:
            found.append({"country": name, "who": who, "field": field})

    client = account.company_name
    for field, label in (("country", "Country of registration"), ("nationality", "Nationality"),
                         ("country_of_residence", "Country of residence"), ("country_of_birth", "Country of birth")):
        add(getattr(account, field), client, label)
    for field, label in (("registered_address", "Registered address"), ("operating_address", "Operating address"),
                         ("residential_address", "Residential address")):
        add((getattr(account, field) or {}).get("country"), client, label)
    for p in account.parties:
        who = f"{p.party_role}: {p.full_name}"
        for field, label in (("country_of_incorp_or_birth", "Country of incorporation / birth"),
                             ("nationality", "Nationality"), ("country_of_residence", "Country of residence")):
            add(getattr(p, field), who, label)
        add((p.residential_address or {}).get("country"), who, "Residential address")
    return found
