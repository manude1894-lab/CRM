"""Report IDs, the Administrator's report settings, and each user's favourite reports (Triam 26-11-2026).

As other CRMs do (Zoho folders shared by role, Salesforce / HubSpot report access, favourites with a star): every
standard report has a short ID (e.g. KYC-01) used on screen, in downloads and when people refer to it; the
Administrator may rename a report, hide it, choose the roles that may run it and set its default period; and each
user stars the reports they use most. Administrators and Inquiry & Reports always see every report.
"""
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.audit import log_event
from app.models import User, UserRole
from app.models.report_setting import ReportFavourite, ReportSetting

# The report IDs, by group: Onboarding, Compliance & KYC, Documents, Calls & visits, Prospects, Finance.
CODES = {
    "onboarding-approved": "ONB-01", "onboarding-in-progress": "ONB-02", "under-formation": "ONB-03", "rejected-with-rm": "ONB-04",
    "clients-risk": "KYC-01", "aml-reviews-due": "KYC-02", "aml-reviews-expired": "KYC-03", "amendments": "KYC-04", "data-quality": "KYC-05",
    "documents-expiring": "DOC-01", "documents-expired": "DOC-02",
    "visits-recorded": "VIS-01", "visits-not-done": "VIS-02",
    "prospects-assigned": "PRO-01", "prospects-unassigned": "PRO-02",
    "invoices-onboarding": "FIN-01", "invoices-service-requests": "FIN-02", "invoices-pending": "FIN-03", "service-requests-ageing": "FIN-04",
}
GROUPS = {"ONB": "Onboarding", "KYC": "Compliance & KYC", "DOC": "Documents", "VIS": "Calls & visits", "PRO": "Prospects",
          "FIN": "Finance & service requests"}
TAKES_DAYS = {"documents-expiring": 30, "aml-reviews-due": 30, "under-formation": 30}
# Who runs a report when the Administrator hasn't chosen (Triam UAT 19-11-2026).
STANDARD_ACCESS = {
    "amendments": "Compliance & Approver",
    "invoices-onboarding": "Accounts & Sales Manager", "invoices-service-requests": "Accounts & Sales Manager",
    "invoices-pending": "Accounts & Sales Manager", "service-requests-ageing": "Accounts & Sales Manager",
}
EVERYONE = "Everyone"  # each still sees only the clients they may see
MAX_DAYS = 3650


def settings(db: Session) -> dict[str, ReportSetting]:
    return {s.report_key: s for s in db.query(ReportSetting).all()}


def always_sees(user: User) -> bool:
    from app.auth.permissions import has_permission
    return user.role == UserRole.ADMIN or has_permission(user, "read_only")


def allowed(user: User, key: str, s: Optional[ReportSetting], standard_rule) -> bool:
    """May this user run the report? Hidden reports: Administrators only. Roles chosen: those roles (and those who
    always see). Otherwise the standard access."""
    if user.role == UserRole.ADMIN:
        return True
    if s is not None and s.hidden:
        return False
    if always_sees(user):
        return True
    if s is not None and s.role_ids is not None:
        return user.business_role_id in set(s.role_ids)
    return standard_rule is None or standard_rule(user)


def display_name(key: str, standard: str, s: Optional[ReportSetting]) -> str:
    return (s.name or "").strip() or standard if s is not None else standard


def favourites(db: Session, user: User) -> set[str]:
    return {f.report_key for f in db.query(ReportFavourite).filter(ReportFavourite.user_id == user.id).all()}


def set_favourite(db: Session, user: User, key: str, on: bool) -> None:
    if key not in CODES:
        raise HTTPException(status_code=404, detail="Unknown report")
    row = db.query(ReportFavourite).filter(ReportFavourite.user_id == user.id, ReportFavourite.report_key == key).first()
    if on and row is None:
        db.add(ReportFavourite(user_id=user.id, report_key=key))
    elif not on and row is not None:
        db.delete(row)
    db.commit()


def admin_list(db: Session, reports: dict) -> list[dict]:
    st = settings(db)
    out = []
    for key, standard in reports.items():
        s = st.get(key)
        out.append({"key": key, "code": CODES.get(key, ""), "group": GROUPS.get(CODES.get(key, "")[:3], "Other"),
                    "standard_title": standard, "name": s.name if s else None, "hidden": bool(s and s.hidden),
                    "role_ids": s.role_ids if s else None, "standard_access": STANDARD_ACCESS.get(key, EVERYONE),
                    "takes_days": key in TAKES_DAYS, "default_days": s.default_days if s else None,
                    "standard_days": TAKES_DAYS.get(key)})
    return out


def save(db: Session, key: str, data, user: User, reports: dict) -> dict:
    if key not in reports:
        raise HTTPException(status_code=404, detail="Unknown report")
    name = (data.name or "").strip() or None
    if name and len(name) > 150:
        raise HTTPException(status_code=400, detail="The name can be at most 150 characters")
    if data.default_days is not None and (key not in TAKES_DAYS or not 0 <= data.default_days <= MAX_DAYS):
        raise HTTPException(status_code=400, detail=f"Default days must be between 0 and {MAX_DAYS}, for a report that takes days")
    role_ids = None if data.role_ids is None else sorted({int(r) for r in data.role_ids})
    s = db.get(ReportSetting, key) or ReportSetting(report_key=key)
    before = {"name": s.name, "hidden": bool(s.hidden), "role_ids": s.role_ids, "default_days": s.default_days}
    s.name, s.hidden, s.role_ids, s.default_days, s.updated_by_id = name, bool(data.hidden), role_ids, data.default_days, user.id
    db.add(s)
    after = {"name": name, "hidden": bool(data.hidden), "role_ids": role_ids, "default_days": data.default_days}
    changed = {k: {"old": before[k], "new": after[k]} for k in after if before[k] != after[k]}
    log_event(db, "report_setting", f"Report {CODES.get(key, key)} settings changed", user_id=user.id,
              subject_type="Report", changes=changed or None)
    db.commit()
    return next(r for r in admin_list(db, reports) if r["key"] == key)
