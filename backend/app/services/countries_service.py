"""Service layer: Countries master (BRD §17) — the list behind every country drop-down."""
import json
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import CountryRisk
from app.schemas.country import CountryCreate

_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "country_risk.json"


def seed_countries(db: Session) -> int:
    """Idempotently load the country list. Returns rows inserted."""
    if db.query(CountryRisk).count() > 0:
        return 0
    payload = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    rows = [
        CountryRisk(
            name=c["name"],
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
    c = CountryRisk(name=name, risk_level="Low", score=1)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c
