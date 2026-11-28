"""Service layer: Account business logic."""
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from fastapi import HTTPException
from typing import Optional
from decimal import Decimal
from datetime import date, datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta

from app.models import Account, ApprovalRequest, ApprovalStatus, User, UserRole, ClientIdSequence
from app.auth.permissions import has_permission
from app.audit import log_event
from app.schemas.account import AccountCreate, AccountUpdate, AccountImportRow, AccountImportRowResult, AccountBulkUpdateRequest, BulkUpdateResult
from app.utils.uid import next_uid
from app.utils.fuzzy_match import top_matches
from app.services import access_control, master_service, client_workflow_service

# Client-database spec §24.6 — review cadence by risk rating.
_AML_REVIEW_CADENCE_YEARS = {"High": 1, "Medium": 2, "Low": 3}


# Account field -> (master list, label, kind). kind: "one" | "many" (JSON list) | "csv" (comma string).
_MASTER_FIELDS = {
    "anchor_entity": ("triam_entity", "Anchor Triam Entity", "one"),
    "non_anchor_entities": ("triam_entity", "Non-anchor Triam Entities", "many"),
    "nature_of_services_sought": ("service", "Nature of Services Sought", "many"),
    "tags": ("tag", "Tags", "csv"),
    "regulator_name": ("regulator", "Name of Regulator", "one"),
    "licensing_authority": ("licensing_authority", "Registering Authority", "one"),
}


def _as_list(value, kind) -> list:
    if value in (None, "", []):
        return []
    if kind == "csv":
        return [t.strip() for t in str(value).split(",") if t.strip()]
    if kind == "one":
        return [value]
    return list(value)


def _validate_master_fields(db: Session, payload: dict, existing: Optional[Account] = None) -> None:
    """BRD §4/§18 — values must come from the active admin-managed lists. A value the record
    already holds stays valid even if its master item was later deactivated (so old clients
    remain editable)."""
    for field, (list_type, label, kind) in _MASTER_FIELDS.items():
        if field not in payload:
            continue
        new_values = _as_list(payload[field], kind)
        kept = set(_as_list(getattr(existing, field, None), kind)) if existing else set()
        master_service.assert_valid(db, list_type, [v for v in new_values if v not in kept], label)


# ─── BRD §3 search name / duplicates, §19 Client ID, §11 status timestamp ─────

def _norm(name: Optional[str]) -> str:
    return " ".join((name or "").split()).lower()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _same_name_query(db: Session, company_name: str, exclude_id: Optional[int] = None):
    q = db.query(Account).filter(func.lower(func.trim(Account.company_name)) == _norm(company_name))
    if exclude_id:
        q = q.filter(Account.id != exclude_id)
    return q


def _search_name_taken(db: Session, search_name: str, exclude_id: Optional[int] = None) -> bool:
    q = db.query(Account.id).filter(func.lower(Account.search_name) == _norm(search_name))
    if exclude_id:
        q = q.filter(Account.id != exclude_id)
    return q.first() is not None


def _default_search_name(db: Session, company_name: str, anchor_entity: Optional[str]) -> str:
    """Prefill from the legal name; if that's taken (only possible via the duplicate exception),
    disambiguate with the entity and then a counter."""
    base = " ".join(company_name.split())[:100]
    candidates = [base]
    if anchor_entity:
        candidates.append(f"{base} ({anchor_entity})")
    candidates += [f"{base} ({n})" for n in range(2, 50)]
    for c in candidates:
        if not _search_name_taken(db, c):
            return c
    raise HTTPException(status_code=400, detail="Please enter a Unique Search Name. The default one is already taken.")


def issue_missing_client_ids(db: Session) -> int:
    """Triam data review 21-11-2026: clients past onboarding that never got a Client ID (records from before IDs
    existed, or imported without one) get it now, from their Anchor Triam Entity. Run at every deploy; does
    nothing once all have one. A client with no entity is left for the "Client data to correct" report."""
    accs = (db.query(Account).filter(Account.client_id.is_(None), Account.anchor_entity.isnot(None),
                                     Account.profile_status.notin_(client_workflow_service.ONBOARDING))
            .order_by(Account.approved_at, Account.id).all())
    for acc in accs:
        acc.client_id = next_client_id(db, acc.anchor_entity)
        db.flush()
    db.commit()
    return len(accs)


def next_client_id(db: Session, entity_code: str) -> str:
    """BRD §19 — {ENTITY}/{00000}, separate counter per entity. The counter row is locked so
    concurrent saves can't take the same number (FOR UPDATE is a no-op on SQLite, used in tests)."""
    seq = db.query(ClientIdSequence).filter(ClientIdSequence.entity_code == entity_code).with_for_update().first()
    if seq is None:
        # First ID for this entity — start after any IDs already present (e.g. data fixed by hand),
        # so the counter can never hand out a number that's taken.
        prefix = f"{entity_code}/"
        existing = [cid for (cid,) in db.query(Account.client_id).filter(Account.client_id.like(f"{prefix}%")).all()]
        highest = max((int(c[len(prefix):]) for c in existing if c[len(prefix):].isdigit()), default=0)
        seq = ClientIdSequence(entity_code=entity_code, last_value=highest)
        db.add(seq)
        db.flush()
    while True:
        seq.last_value += 1
        candidate = f"{entity_code}/{seq.last_value:05d}"
        if not db.query(Account.id).filter(Account.client_id == candidate).first():
            return candidate


def lookup_by_name(db: Session, user: User, q: str, exclude_id: Optional[int] = None, limit: int = 10) -> list[dict]:
    """BRD §3 — from the 3rd letter, list existing clients whose legal or search name has a word
    starting with what was typed. Searches *all* clients (a duplicate is a duplicate even if another
    RM owns it) but returns only the name and ID for clients the user can't open."""
    term = _norm(q)
    if len(term) < 3:
        return []
    like_start, like_word = f"{term}%", f"% {term}%"
    query = db.query(Account).filter(or_(
        func.lower(Account.company_name).like(like_start), func.lower(Account.company_name).like(like_word),
        func.lower(Account.search_name).like(like_start), func.lower(Account.search_name).like(like_word),
    ))
    if exclude_id:
        query = query.filter(Account.id != exclude_id)
    out = []
    for acc in query.order_by(Account.company_name).limit(limit).all():
        can_open = access_control.user_can_access_account(db, acc, user)
        out.append({
            "id": acc.id,
            "client_id": acc.client_id,
            "company_name": acc.company_name,
            "search_name": acc.search_name,
            "account_type": acc.account_type,
            "exact_match": _norm(acc.company_name) == term,
            "can_open": can_open,
            "profile_status": acc.profile_status if can_open else None,
        })
    return out


def _set_status(acc: Account, user: User) -> None:
    acc.status_updated_at = _now()
    acc.status_updated_by_id = user.id


def _compute_next_aml_review_date(acc: Account) -> None:
    """Recompute Account.next_aml_review_date from risk_rating + cdd_completion_date.

    Server-computed, not user-editable — cleared if either input is missing.
    """
    years = _AML_REVIEW_CADENCE_YEARS.get(acc.risk_rating or "")
    if acc.cdd_completion_date and years:
        acc.next_aml_review_date = acc.cdd_completion_date + relativedelta(years=years)
    else:
        acc.next_aml_review_date = None


# Sort orders for client lists (review 22-11-2026, package 4: lists are paged, filtered and sorted on the server).
# Triam 22-11-2026: every column of the list sorts; "-" in front reverses the order (e.g. "-name").
LIST_SORTS = ("name", "approved", "aml", "recent", "client_id", "status", "risk", "rm", "pep")


def _list_order(sort: str):
    from sqlalchemy import case
    desc = sort.startswith("-")
    key = sort.lstrip("-")
    # "x" sorts up (A to Z, oldest date first, risk High first, PEPs first); "-x" sorts down. Blanks always last.
    columns = {
        "name": [func.lower(Account.company_name)],
        "client_id": [Account.client_id, Account.account_uid],
        "status": [Account.profile_status],
        "approved": [Account.approved_at],
        "aml": [Account.next_aml_review_date],
        "risk": [case({"High": 0, "Medium": 1, "Low": 2}, value=Account.risk_rating, else_=None)],
        "rm": [func.lower(User.name)],
        "pep": [case((Account.is_pep.is_(True), 0), else_=1)],
    }
    if key == "recent":
        return [Account.created_at.desc(), Account.id.desc()], False
    cols = columns.get(key, columns["name"])
    ordered = [(c.desc() if desc else c.asc()).nulls_last() for c in cols]
    return [*ordered, func.lower(Account.company_name), Account.id], key == "rm"


def list_accounts(
    db: Session,
    user: User,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    country: Optional[str] = None,
    statuses: Optional[list[str]] = None,
    risk: Optional[str] = None,
    approved_since: Optional[date] = None,
    sort: str = "name",
) -> tuple[list[Account], int]:
    from app.models import Prospect
    query = db.query(Account)
    # BRD §13 RM privacy + supervisor visibility.
    visibility = access_control.account_visibility_clause(db, user)
    if visibility is not None:
        query = query.filter(visibility)

    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(
            Account.company_name.ilike(pattern),
            Account.search_name.ilike(pattern),
            Account.client_id.ilike(pattern),
            Account.account_uid.ilike(pattern),
            Account.prospect.has(Prospect.prospect_uid.ilike(pattern)),  # the temporary ID people search by
        ))
    if country:
        query = query.filter(Account.country == country)
    if statuses:
        query = query.filter(Account.profile_status.in_(statuses))
    if risk:
        query = query.filter(Account.risk_rating == risk)
    if approved_since:
        query = query.filter(Account.approved_at >= datetime.combine(approved_since, datetime.min.time(), tzinfo=timezone.utc))

    total = query.count()
    order, needs_rm = _list_order(sort or "name")
    if needs_rm:
        query = query.outerjoin(User, User.id == Account.spoc_id)
    items = query.order_by(*order).offset(skip).limit(limit).all()
    # Triam UAT 05-11-2026: the list says at which level a case awaiting approval is pending.
    awaiting = {a.id: a for a in items if a.profile_status == client_workflow_service.AWAITING}
    if awaiting:
        for req in db.query(ApprovalRequest).filter(ApprovalRequest.account_id.in_(awaiting), ApprovalRequest.status == ApprovalStatus.PENDING.value).all():
            awaiting[req.account_id].approval_stage = client_workflow_service.stage_of(req)
    return items, total


def find_similar_accounts(db: Session, name: str, exclude_id: Optional[int] = None) -> list[tuple[int, str, int]]:
    query = db.query(Account.id, Account.company_name)
    if exclude_id:
        query = query.filter(Account.id != exclude_id)
    return top_matches(name, query.all())


def get_account(db: Session, account_id: int, user: User) -> Account:
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    if not access_control.user_can_access_account(db, acc, user):
        raise HTTPException(status_code=403, detail="Access denied")
    return acc


PASSPORT_GRACE_DAYS = 30


def passport_too_old(expiry: Optional[date]) -> bool:
    """Triam UAT 05-11-2026: a passport may be accepted up to 30 days past its expiry, not more."""
    return bool(expiry) and expiry < date.today() - timedelta(days=PASSPORT_GRACE_DAYS)


def assert_passport_acceptable(expiry: Optional[date], whose: str = "The passport") -> None:
    if passport_too_old(expiry):
        raise HTTPException(status_code=400, detail=f"{whose} expired more than {PASSPORT_GRACE_DAYS} days ago. Ask for the renewed passport.")


ADULT_AGE = 18
MAX_AGE = 120
VISA_GRACE_DAYS = 30
MEETING_BACK_DAYS = 30  # Biz Rationale meeting date (Triam UAT 26-11-2026)


def age_on(dob: date, today: Optional[date] = None) -> int:
    today = today or date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def is_minor(dob: Optional[date]) -> bool:
    return bool(dob) and age_on(dob) < ADULT_AGE


def assert_birth_date(dob: Optional[date], whose: str, adult: bool = True) -> None:
    """Triam 16-11-2026: a date of birth isn't in the future nor more than 120 years ago, and an adult is 18 or over."""
    if not dob:
        return
    if dob > date.today():
        raise HTTPException(status_code=400, detail=f"{whose}: Date of Birth cannot be in the future")
    if age_on(dob) > MAX_AGE:
        raise HTTPException(status_code=400, detail=f"{whose}: Date of Birth is more than {MAX_AGE} years ago. Check the date")
    if adult and age_on(dob) < ADULT_AGE:
        raise HTTPException(status_code=400, detail=f"{whose} must be at least {ADULT_AGE} years old (a minor can't be onboarded in this role)")


def _is_uae(country: Optional[str]) -> bool:
    c = (country or "").lower()
    return "united arab emirates" in c or c.strip() in ("uae", "ae")


def _assert_date_sanity(data, acc: Optional[Account] = None) -> None:
    """Date and number rules for an interactive create/update (CSV import of historical data is exempt, since
    expired licences are legitimate there). `acc` is the record being updated: a rule comparing two fields uses
    its stored value for the one not being sent. A "not before today" rule applies only to a date being entered
    or changed, so an old date on record doesn't block saving something else.

    BRD §5: Incorporation Date isn't in the future; License Expiry isn't in the past. Triam 16-11-2026: the
    licence starts on or before today and not before incorporation, and expires after it starts; regulatory
    licence, LEI and engagement letter aren't already expired; the UAE visa within 30 days; an individual
    client is an adult; a passport expires after its holder was born; a UAE TRN / Corporate Tax number is 15 digits."""
    today = date.today()
    sent = data.model_dump(exclude_unset=True)

    def val(f):
        return sent[f] if f in sent else getattr(acc, f, None)

    def changed(f):
        return sent.get(f) is not None and (acc is None or sent[f] != getattr(acc, f, None))

    def fail(msg):
        raise HTTPException(status_code=400, detail=msg)

    if changed("incorporation_date") and sent["incorporation_date"] > today:
        fail("Incorporation Date cannot be in the future")
    if changed("screening_date") and sent["screening_date"] > today:
        fail("Screening Date cannot be in the future")
    # Triam UAT 27-11-2026: CDD is completed on or before today (UAE date); the next AML review is counted from it.
    if changed("cdd_completion_date"):
        from app.services.standard_reports_service import BUSINESS_TZ
        if sent["cdd_completion_date"] > datetime.now(BUSINESS_TZ).date():
            fail("CDD Completion Date cannot be in the future")
    # Triam UAT 25-11-2026 row 202: the Biz Rationale meeting has happened: not a future date, nor a later time today.
    # Triam UAT 26-11-2026: "now" by the clock of whoever enters it (UAE or India), and at most 30 days back.
    if changed("br_meeting_date") or changed("br_meeting_time"):
        from app.request_context import user_now
        now = user_now()
        met_on, met_at = val("br_meeting_date"), val("br_meeting_time")
        if met_on and met_on > now.date():
            fail("Date of Meeting cannot be in the future")
        if changed("br_meeting_date") and met_on < now.date() - timedelta(days=MEETING_BACK_DAYS):
            fail(f"Date of Meeting cannot be more than {MEETING_BACK_DAYS} days back")
        if met_on == now.date() and met_at and str(met_at)[:5] > now.strftime("%H:%M"):
            fail("Time of Meeting cannot be later than now for a meeting today")
    start, expiry, incorporated = val("license_start_date"), val("license_expiry_date"), val("incorporation_date")
    if changed("license_start_date") and start > today:
        fail("License Start Date cannot be in the future")
    if (changed("license_start_date") or changed("incorporation_date")) and start and incorporated and start < incorporated:
        fail("License Start Date cannot be before the Incorporation Date")
    if changed("license_expiry_date") and expiry < today:
        fail("License Expiry Date cannot be before today")
    if (changed("license_start_date") or changed("license_expiry_date")) and start and expiry and expiry <= start:
        fail("License Expiry Date must be after the License Start Date")
    for field, label in (("regulatory_license_expiry_date", "Current regulatory license expiry"),
                         ("lei_expiry_date", "LEI Expiry Date")):
        if changed(field) and sent[field] < today:
            fail(f"{label} cannot be before today")
    if changed("uae_visa_expiry") and sent["uae_visa_expiry"] < today - timedelta(days=VISA_GRACE_DAYS):
        fail(f"The UAE visa expired more than {VISA_GRACE_DAYS} days ago. Ask for the renewed visa")
    dob, passport = val("date_of_birth"), val("passport_expiry_date")
    if changed("date_of_birth"):
        assert_birth_date(dob, "The individual client")
    if (changed("date_of_birth") or changed("passport_expiry_date")) and dob and passport and passport <= dob:
        fail("Passport Expiry Date must be after the Date of Birth")
    if _is_uae(val("country")):
        for field, label in (("trn_vat_number", "TRN / VAT Registration No."), ("corp_tax_registration_number", "Corp Tax Registration No.")):
            v = val(field)
            if (changed(field) or changed("country")) and v and not (len(v) == 15 and v.isdigit()):
                fail(f"{label}: a UAE number is 15 digits")


def asks_one_time(account) -> bool:
    """Triam 14-11-2026: "Is this a one-time service?" is asked of an Existing company (not one Under
    Formation, nor before the category is chosen) and of every individual client."""
    return account.account_type == "Individual" or account.client_category == "Existing"


def _normalize_one_time(acc: Account) -> None:
    """The answer doesn't apply when the question isn't asked (e.g. the company is Under Formation)."""
    if not asks_one_time(acc):
        acc.is_one_time_service = None


def one_time_services(db: Session) -> dict[str, list[str]]:
    """Admin's one-time services table: service -> the Triam entities for which it is a one-time service."""
    return {i.code: list((i.meta or {}).get("one_time_entities") or [])
            for i in master_service.list_items(db, "service") if (i.meta or {}).get("one_time_entities")}


def one_time_problems(db: Session, account) -> list[dict]:
    """Triam 14-11-2026: a one-time client takes only the one-time services of its Triam entities, and
    only Triam entities that offer one-time services. Checked at Submit, like the other mandatory rules."""
    if not account.is_one_time_service or not asks_one_time(account):
        return []
    table = one_time_services(db)
    offering = {e for ents in table.values() for e in ents}
    entities = [e for e in [account.anchor_entity, *(account.non_anchor_entities or [])] if e]
    problems = []
    for e in entities:
        if e not in offering:
            problems.append({"section": "Triam assignment", "field": "anchor_entity" if e == account.anchor_entity else "non_anchor_entities",
                             "label": f"{e} does not offer one-time services. A one-time client can only be handled by "
                                      f"{', '.join(sorted(offering)) or 'an entity with one-time services'}"})
    for s in account.nature_of_services_sought or []:
        if not set(table.get(s, [])) & set(entities):
            problems.append({"section": "Client info", "field": "nature_of_services_sought",
                             "label": f"'{s}' is not a one-time service of the client's Triam entities. Remove it, or answer "
                                      f"'Is this a one-time service?' with No"})
    return problems


def entity_service_problems(db: Session, account) -> list[dict]:
    """Triam 20-11-2026: a corporate client's services are those its Triam entities offer (Admin -> Masters ->
    Services, "Entities"). A service left over after the entity was changed is refused at Submit. A service with no
    entity list is offered by every entity; individual clients and one-time clients have their own rules."""
    if account.account_type == "Individual" or (account.is_one_time_service and asks_one_time(account)):
        return []
    entities = {e for e in [account.anchor_entity, *(account.non_anchor_entities or [])] if e}
    if not entities:
        return []
    items = master_service.list_items(db, "service", include_inactive=True)
    offered_by = {i.code: set((i.meta or {}).get("entities") or []) for i in items}
    label = {i.code: i.label for i in items}
    return [{"section": "Client info", "field": "nature_of_services_sought",
             "label": f"'{label.get(s, s)}' is not offered by {' / '.join(sorted(entities))}. Remove it, or add the Triam entity that offers it"}
            for s in account.nature_of_services_sought or [] if offered_by.get(s) and not offered_by[s] & entities]


def _normalize_non_anchor_rms(acc: Account) -> None:
    """Client spec §I — the Anchor RM (spoc_id) can't also be a Non-anchor RM. Enforced
    server-side too, since bulk-update can change the anchor without touching the list."""
    if acc.non_anchor_rm_ids:
        acc.non_anchor_rm_ids = list(dict.fromkeys(i for i in acc.non_anchor_rm_ids if i != acc.spoc_id)) or None


MAX_CLIENT_NAME = 50  # BRD §5: "50 char long, alpha-num-Spl. Char."


def _dropped_note(acc: Account) -> str:
    """A dropped client still holds its name (Triam UAT 18-11-2026): say so, so the RM reopens it."""
    return " and was dropped: reopen it instead" if acc.profile_status == client_workflow_service.DROPPED else ""


def create_account(db: Session, data: AccountCreate, user: User) -> Account:
    if len(data.company_name.strip()) > MAX_CLIENT_NAME:
        raise HTTPException(status_code=400, detail=f"Client name can be at most {MAX_CLIENT_NAME} characters")
    # BRD §3 — an ordinary duplicate is blocked; an approver may create it with a recorded reason.
    existing = _same_name_query(db, data.company_name).first()
    override_reason = None
    if existing:
        if not data.allow_duplicate:
            raise HTTPException(status_code=409, detail=f"A client named '{existing.company_name}' already exists ({existing.client_id or existing.account_uid}){_dropped_note(existing)}. An approver can create it anyway with a reason.")
        if not has_permission(user, "client.approve"):
            raise HTTPException(status_code=403, detail="Only an approver (CO / MLRO / Admin) can create a duplicate client")
        override_reason = (data.duplicate_reason or "").strip()
        if len(override_reason) < 10:
            raise HTTPException(status_code=400, detail="Give a meaningful reason (at least 10 characters) for creating a duplicate client")

    # BRD §19 — the Client ID is built from the Anchor Triam Entity (issued at the Final approval).
    if not (data.anchor_entity or "").strip():
        raise HTTPException(status_code=400, detail="Anchor Triam Entity is required, as it determines the Client ID")

    search_name = data.search_name
    if search_name:
        if _search_name_taken(db, search_name):
            raise HTTPException(status_code=400, detail=f"Unique Search Name '{search_name}' is already used by another client")
    else:
        search_name = _default_search_name(db, data.company_name, data.anchor_entity)

    _assert_date_sanity(data)
    assert_passport_acceptable(data.passport_expiry_date)
    if any(getattr(data, f, None) not in (None, "") for f in CDD_FIELDS) and not has_permission(user, "client.cdd_edit"):
        raise HTTPException(status_code=403, detail="Only Compliance (MLRO) can complete the CDD / risk assessment section")

    prospect = None
    if data.prospect_id:
        from app.services import prospect_service
        prospect = prospect_service.assert_ready_for_client(db, data.prospect_id, user)

    owner_id = data.owner_id or user.id
    payload = data.model_dump(exclude={"owner_id", "allow_duplicate", "duplicate_reason", "search_name", "prospect_id"})
    if prospect is not None and not payload.get("spoc_id"):
        payload["spoc_id"] = prospect.owner_id  # the RM the prospect was assigned to
    payload["profile_status"] = client_workflow_service.NEW  # BRD §11 — status only moves via the workflow
    _validate_master_fields(db, payload)
    acc = Account(
        account_uid=next_uid(db, Account, "account_uid", "ACC"),
        search_name=search_name,
        duplicate_override_reason=override_reason,
        **payload,
        owner_id=owner_id,
    )
    _set_status(acc, user)
    _compute_next_aml_review_date(acc)
    _normalize_non_anchor_rms(acc)
    _normalize_one_time(acc)
    if prospect is not None:
        acc.prospect_id = prospect.id
    db.add(acc)
    db.flush()
    if prospect is not None:
        from app.models import ProspectStatus
        prospect.converted_account_id = acc.id
        prospect.status = ProspectStatus.WON.value
        log_event(db, "create", f"Client {acc.company_name} created from prospect {prospect.prospect_uid}",
                  subject_type="Account", subject_id=acc.id, account_id=acc.id, changes={"prospect": prospect.prospect_uid})
    if override_reason:
        log_event(db, "duplicate_override", f"Duplicate client '{acc.company_name}' created by exception: {override_reason}",
                  subject_type="Account", subject_id=acc.id, account_id=acc.id,
                  changes={"existing_client": existing.client_id or existing.account_uid, "reason": override_reason})
    db.commit()
    db.refresh(acc)
    return acc


# BRD §7/§11: the CDD / risk assessment section is completed only by Compliance (MLRO).
CDD_FIELDS = ("risk_rating", "aml_classification", "edd_reason", "kyc_verified_by", "cdd_completion_date")


def update_account(db: Session, account_id: int, data: AccountUpdate, user: User):
    """Save a section of the client profile.

    Before approval the change applies directly. Once the client is approved (BRD §13) the change is
    staged in the user's open amendment instead and only reaches the live record when Compliance
    approves it — the staged view of the client is returned so the form keeps showing it."""
    acc = get_account(db, account_id, user)
    if _compliance_cdd_save(db, acc, data, user):
        return acc
    client_workflow_service.assert_editable(acc)
    from app.services import amendment_service  # local: amendment_service imports this module
    if amendment_service.is_amendable(acc):
        return amendment_service.stage_account_update(db, acc, data, user)
    update_data = apply_update(db, acc, data, user)
    if update_data:
        client_workflow_service.note_edit(acc, user)
    db.commit()
    db.refresh(acc)
    return acc


def _compliance_cdd_save(db: Session, acc: Account, data: AccountUpdate, user: User) -> bool:
    """While a new client is at the Compliance step the profile is locked, except that Compliance
    completes the CDD section. Returns True when this save was that case (and is done)."""
    if acc.profile_status != client_workflow_service.AWAITING:
        return False
    fields = set(data.model_dump(exclude_unset=True))
    req = client_workflow_service.pending_request(db, acc.id)
    if not fields or not fields <= set(CDD_FIELDS) or client_workflow_service.stage_of(req) != client_workflow_service.STAGE_COMPLIANCE \
            or not has_permission(user, "client.cdd_edit"):
        return False
    before = {f: getattr(acc, f) for f in fields}
    apply_update(db, acc, data, user)
    changed = {f: {"old": str(before[f]) if before[f] is not None else None, "new": str(getattr(acc, f)) if getattr(acc, f) is not None else None}
               for f in fields if before[f] != getattr(acc, f)}
    if changed:
        log_event(db, "cdd_update", f"CDD section of {acc.company_name} completed by Compliance", subject_type="Account",
                  subject_id=acc.id, account_id=acc.id, changes=changed)
    db.commit()
    db.refresh(acc)
    return True


def apply_update(db: Session, acc: Account, data: AccountUpdate, user: User) -> dict:
    """Validate and apply a profile update to `acc` without committing. Shared by direct saves and
    by amendments (staged on save, then applied for real when Compliance approves)."""
    _assert_date_sanity(data, acc)
    if data.passport_expiry_date != acc.passport_expiry_date:
        assert_passport_acceptable(data.passport_expiry_date)
    update_data = data.model_dump(exclude_unset=True)
    if user.role == UserRole.RM:
        update_data.pop("owner_id", None)
    # BRD §11/§15 — status changes only through Submit / Approve / Reject / status actions.
    requested_status = update_data.pop("profile_status", None)
    if requested_status is not None and requested_status != acc.profile_status:
        raise HTTPException(status_code=400, detail="Status can't be edited directly. Use Submit, Approve or Reject, or the status actions on the client profile.")
    cdd_changes = [f for f in CDD_FIELDS if f in update_data and update_data[f] != getattr(acc, f)]
    if cdd_changes and not has_permission(user, "client.cdd_edit"):
        raise HTTPException(status_code=403, detail="Only Compliance (MLRO) can complete the CDD / risk assessment section")
    _validate_master_fields(db, update_data, existing=acc)
    if "search_name" in update_data:
        if not update_data["search_name"]:
            raise HTTPException(status_code=400, detail="Unique Search Name can't be empty")
        if _search_name_taken(db, update_data["search_name"], exclude_id=acc.id):
            raise HTTPException(status_code=400, detail=f"Unique Search Name '{update_data['search_name']}' is already used by another client")
    if update_data.get("company_name") and len(update_data["company_name"].strip()) > MAX_CLIENT_NAME and \
            update_data["company_name"].strip() != (acc.company_name or "").strip():
        raise HTTPException(status_code=400, detail=f"Client name can be at most {MAX_CLIENT_NAME} characters")
    if update_data.get("company_name") and _norm(update_data["company_name"]) != _norm(acc.company_name):
        clash = _same_name_query(db, update_data["company_name"], exclude_id=acc.id).first()
        if clash:
            raise HTTPException(status_code=409, detail=f"A client named '{clash.company_name}' already exists ({clash.client_id or clash.account_uid}){_dropped_note(clash)}")
    for field, value in update_data.items():
        setattr(acc, field, value)
    # The Client ID is issued at the Final approval (BRD §18; UAT 18-11 row 90); until then the
    # temporary ID is shown. Approved clients that pre-date Client IDs get one on their next save.
    # Once issued, a Client ID never changes (even if the Anchor Entity later does).
    if not acc.client_id and acc.anchor_entity and acc.profile_status not in client_workflow_service.ONBOARDING:
        acc.client_id = next_client_id(db, acc.anchor_entity)
    if not acc.search_name:
        acc.search_name = _default_search_name(db, acc.company_name, acc.anchor_entity)
    if "risk_rating" in update_data or "cdd_completion_date" in update_data:
        _compute_next_aml_review_date(acc)
    _normalize_non_anchor_rms(acc)
    _normalize_one_time(acc)
    return update_data


def bulk_update_accounts(db: Session, user: User, data: AccountBulkUpdateRequest) -> list[BulkUpdateResult]:
    patch_fields = {k: v for k, v in data.model_dump(exclude={"ids"}).items() if v is not None}
    patch = AccountUpdate(**patch_fields)
    results = []
    for account_id in data.ids:
        try:
            update_account(db, account_id, patch, user)
            results.append(BulkUpdateResult(id=account_id, status="ok"))
        except HTTPException as e:
            results.append(BulkUpdateResult(id=account_id, status="error", message=e.detail))
    return results


# Imported clients are existing relationships, so only the existing-client statuses (BRD §9).
IMPORT_STATUSES = ("Active", "Approved", "Inactive", "Marked for Exit", "Exited")
RISK_LEVELS = ("High", "Medium", "Low")


def _match(value: str, allowed) -> Optional[str]:
    """The allowed value matching `value` case-insensitively, or None."""
    v = value.strip().lower()
    return next((a for a in allowed if a.lower() == v), None)


def _import_mobiles(row: AccountImportRow) -> tuple[dict, Optional[str]]:
    """Triam UAT 18-11-2026 row 88: an imported mobile number follows the same rules as one typed on the form
    (digits only, the length for its country code). Returns the cleaned numbers, or why the row is refused."""
    from app.schemas.phone import length_problem, mobile_number
    cleaned = {}
    for code_field, number_field, label in (("contact_mobile_country_code", "contact_mobile_number", "Contact Mobile"),
                                            ("individual_mobile_country_code", "individual_mobile_number", "Individual Mobile")):
        raw = getattr(row, number_field)
        try:
            number = mobile_number(raw)
        except ValueError as e:
            return {}, f"{label} '{raw}': {e}"
        if number is None:
            continue
        number = number.lstrip("0") or number
        problem = length_problem(getattr(row, code_field) or None, number)
        if problem:
            return {}, f"{label} '{raw}': {problem}"
        cleaned[number_field] = number
    return cleaned, None


def import_accounts(
    db: Session, user: User, rows: list[AccountImportRow], dry_run: bool,
) -> list[AccountImportRowResult]:
    existing_names = {_norm(name) for (name,) in db.query(Account.company_name).all()}
    seen_in_batch: set[str] = set()
    results: list[AccountImportRowResult] = []

    for idx, row in enumerate(rows):
        name = (row.company_name or "").strip()
        if not name:
            results.append(AccountImportRowResult(row_index=idx, company_name=name, status="error", message="Company name is required"))
            continue
        if _norm(name) in existing_names or _norm(name) in seen_in_batch:
            results.append(AccountImportRowResult(row_index=idx, company_name=name, status="duplicate", message="Client with this company name already exists"))
            continue

        # Existing clients Triam already services: a blank status means Active (new clients come
        # through Prospects). Status and risk level must be values the CRM knows.
        status = _match(row.profile_status, IMPORT_STATUSES) if row.profile_status else "Active"
        risk = _match(row.risk_rating, RISK_LEVELS) if row.risk_rating else None
        problem = (f"Status '{row.profile_status}' is not one of {', '.join(IMPORT_STATUSES)}" if status is None
                   else f"Risk rating '{row.risk_rating}' is not one of {', '.join(RISK_LEVELS)}" if row.risk_rating and risk is None
                   else None)
        mobiles, mobile_problem = _import_mobiles(row)
        problem = problem or mobile_problem
        # Triam data review 21-11-2026: an existing client gets its Client ID from the Anchor Triam Entity, so the
        # entity is required; and dates follow the form's rules.
        today = date.today()
        if not problem and not (row.anchor_entity or "").strip():
            problem = "Anchor Triam Entity is required (the Client ID is made from it)"
        if not problem and row.license_start_date and row.license_start_date > today:
            problem = f"License Start Date {row.license_start_date.isoformat()} is in the future"
        if not problem and row.incorporation_date and row.incorporation_date > today:
            problem = f"Incorporation Date {row.incorporation_date.isoformat()} is in the future"
        if not problem and row.passport_number:  # Triam 20-11-2026: same format as on the form
            from app.schemas.identity import passport_number
            try:
                mobiles["passport_number"] = passport_number(row.passport_number)
            except ValueError as e:
                problem = f"Passport Number '{row.passport_number}': {e}"
        if problem:
            results.append(AccountImportRowResult(row_index=idx, company_name=name, status="error", message=problem))
            continue

        seen_in_batch.add(_norm(name))
        if dry_run:
            results.append(AccountImportRowResult(row_index=idx, company_name=name, status="ok"))
            continue

        payload = {**row.model_dump(exclude_none=True), **mobiles}
        payload["company_name"] = name
        payload["profile_status"], payload["risk_rating"] = status, risk
        search_name = payload.pop("search_name", None)
        if search_name and _search_name_taken(db, search_name):
            search_name = None  # fall back to a generated one rather than failing the row
        acc = Account(
            account_uid=next_uid(db, Account, "account_uid", "ACC"),
            owner_id=user.id,
            **payload,
        )
        acc.search_name = search_name or _default_search_name(db, name, acc.anchor_entity)
        if acc.anchor_entity:
            acc.client_id = next_client_id(db, acc.anchor_entity)
        _set_status(acc, user)
        _compute_next_aml_review_date(acc)
        _normalize_non_anchor_rms(acc)
        db.add(acc)
        db.flush()
        results.append(AccountImportRowResult(row_index=idx, company_name=name, status="ok", account_id=acc.id))

    if not dry_run:
        db.commit()

    return results


# ─── BRD §5 / §9 / §10 / §11 mandatory-field checklist ──────────────────────────
# Sections are saved one at a time, so "mandatory" can't be enforced on every save. This list
# drives the on-screen checklist now and becomes a hard block at Submit (P2, BRD §12 step 11).

def _blank(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, (list, dict)) and not v)


# The form section where shareholders are entered (BRD §5.1, named the same in the UI).
PARTIES_SECTION = "Shareholder / UBO Information"
BIZ_RATIONALE_SECTION = "Biz Rationale Report"


def is_offshore(account) -> bool:
    """Triam UAT 06-11-2026: tax fields don't apply to offshore companies, BVI or not. Offshore means:
    registered in the BVI, anchored in the BVI entity, or an offshore service, tag or registering authority.
    The form applies the same rule (isOffshore in accountForm.js); both are tested against one contract."""
    country = (account.country or "").lower()
    if "virgin islands" in country and "brit" in country:
        return True
    if (account.anchor_entity or "").upper() == "TBVI":
        return True
    values = [*(account.nature_of_services_sought or []), *_as_list(account.tags, "csv"),
              account.licensing_authority, account.licensing_authority_other]
    return any(word in (v or "").lower() for v in values for word in ("offshore", "bvi"))


def _onboarding_documents(account):
    """Invoice and service request files aren't onboarding documents."""
    return [d for d in account.documents if d.removed_at is None and d.invoice_id is None and d.instruction_id is None]


def has_supporting_document(account) -> bool:
    """A document filed for the client itself (the firm, or the individual client), not for one of its people."""
    return any(d.party_id is None for d in _onboarding_documents(account))


def same_person(a, b) -> bool:
    """One person in several roles (UBO and Director, say): the same name and the same date of birth /
    incorporation. Triam UAT 13-11-2026 row 79 (two Shareholders both named "Daniel", no date of birth): a blank
    date is not a match, and two records in the same role are always two people. Same rule as samePerson on the form."""
    return (a.party_role != b.party_role and a.dob_or_incorp_date is not None
            and a.dob_or_incorp_date == b.dob_or_incorp_date
            and (a.full_name or "").strip().lower() == (b.full_name or "").strip().lower())


def group_people(parties) -> list[list]:
    """The client's parties grouped by person (see same_person), in the order given."""
    groups: list[list] = []
    for p in parties:
        for g in groups:
            if all(same_person(r, p) for r in g):
                g.append(p)
                break
        else:
            groups.append([p])
    return groups


PASSPORT_CATEGORY = "PASSPORT"  # the "Passport" document category (document_category master)


def has_passport_copy(account) -> bool:
    """Triam 20-11-2026: an individual client files its passport copy for itself."""
    return any(d.party_id is None and d.category == PASSPORT_CATEGORY for d in _onboarding_documents(account))


def people_without_documents(account) -> list[list]:
    """Triam UAT 09/10-11-2026: each individual / non-individual needs a document of their own; for an individual
    it is their passport copy (Triam 20-11-2026). Returns the people without it, each as the list of their
    records. A document on any of a person's records covers all of them."""
    docs = [d for d in _onboarding_documents(account) if d.party_id is not None]
    any_doc = {d.party_id for d in docs}
    passport = {d.party_id for d in docs if d.category == PASSPORT_CATEGORY}
    return [records for records in group_people(account.parties)
            if not any(r.id in (any_doc if records[0].constitution == "Entity" else passport) for r in records)]


FOUNDATION_SERVICE = "Set up Foundations"
FOUNDATION_ROLES = ("Founder", "Council Member", "Beneficiary", "Guardian")
MIN_COUNCIL_MEMBERS = 2


def is_foundation(account) -> bool:
    """Triam UAT 05-11-2026: a foundation has Founders, Council Members, Beneficiaries and Guardians
    instead of Shareholders and Directors."""
    return FOUNDATION_SERVICE in (account.nature_of_services_sought or [])


def counts_towards_ownership(party) -> bool:
    """Triam UAT 06-11-2026: an entity's share is looked through to the individuals behind it, so only
    individual shareholders count towards 100% (ABC Ltd: A 25, B 25, C Ltd's owners C1 30, C2 20)."""
    return party.party_role == "Shareholder" and party.constitution != "Entity"


def missing_mandatory(account: Account) -> list[dict]:
    missing: list[dict] = []

    def need(section, field, label, value=None, when=True):
        if when and _blank(getattr(account, field) if value is None else value):
            missing.append({"section": section, "field": field, "label": label})

    # §4 Triam assignment — common to both types.
    need("Triam assignment", "anchor_entity", "Anchor Triam Entity")
    need("Triam assignment", "spoc_id", "Anchor RM")
    need("Client info", "search_name", "Unique Search Name")

    if account.account_type == "Individual":
        # §9
        need("Individual details", "company_name", "Full Name")
        need("Individual details", "date_of_birth", "Date of Birth")
        need("Individual details", "passport_number", "Passport Number")
        need("Individual details", "passport_expiry_date", "Passport Expiry Date")
        if passport_too_old(account.passport_expiry_date):
            missing.append({"section": "Individual details", "field": "passport_expiry_date",
                            "label": f"The passport expired more than {PASSPORT_GRACE_DAYS} days ago. A renewed passport is needed"})
        need("Individual details", "country_of_birth", "Country of Birth")
        need("Individual details", "nationality", "Nationality")
        need("Individual details", "country_of_residence", "Country of Residence")
        need("Individual details", "individual_mobile_number", "Contact Mobile")
        need("Individual details", "individual_mobile_country_code", "Contact Mobile country code")
        need("Individual details", "individual_email", "Contact Email")
        need("Individual details", "nature_of_services_sought", "Nature of Services sought")
        need("Individual details", "is_one_time_service", "Is this a one-time service? (Yes / No)")
        addr = account.residential_address or {}
        if not all((addr.get(f) or "").strip() for f in ("line1", "city", "country")):
            missing.append({"section": "Individual details", "field": "residential_address", "label": "Residential Address (line 1, city and country)"})
    else:
        # BRD §5 — New Client Category: licence and incorporation details are mandatory for existing
        # companies. Triam UAT 05-11-2026: only when Under Formation is chosen, these and the addresses
        # and tax details may be blank. Keep in step with mandatoryFields in accountForm.js.
        forming = account.client_category == "Under Formation"
        taxable = not forming and not is_offshore(account)
        need("Client info", "client_category", "New Client Category (Under Formation / Existing)")
        need("Client info", "company_name", "Client Name")
        need("Client info", "country", "Country of Incorporation / Registration")
        need("Client info", "contact_mobile_number", "Contact Mobile (company)")
        need("Client info", "contact_mobile_country_code", "Contact Mobile country code (company)")
        need("Client info", "contact_email", "Contact Email (company)")
        need("Client info", "nature_of_services_sought", "Nature of Services sought")
        need("Client info", "is_one_time_service", "Is this a one-time service? (Yes / No)", when=asks_one_time(account))
        need("Client info", "registration_number", "Incorporation Certificate No.", when=not forming)
        need("Client info", "incorporation_date", "Incorporation Date", when=not forming)
        need("Client info", "license_number", "Trade / Commercial License Number", when=not forming)
        need("Licensing & Regulatory", "licensing_authority", "Registering Authority")
        need("Licensing & Regulatory", "licensing_authority_other", "Registering Authority (Other) details",
             when=account.licensing_authority == "Other")
        need("Licensing & Regulatory", "license_start_date", "License Start / Registration Date", when=not forming)
        need("Licensing & Regulatory", "license_expiry_date", "License Expiry Date", when=not forming)
        # Triam data review 21-11-2026: a date entered before the rule existed (e.g. 2099) is caught at Submit.
        today = date.today()
        if account.license_start_date and account.license_start_date > today:
            missing.append({"section": "Licensing & Regulatory", "field": "license_start_date",
                            "label": "License Start Date is in the future. Correct it"})
        if account.incorporation_date and account.incorporation_date > today:
            missing.append({"section": "Client info", "field": "incorporation_date",
                            "label": "Incorporation Date is in the future. Correct it"})
        if account.license_start_date and account.incorporation_date and account.license_start_date < account.incorporation_date:
            missing.append({"section": "Licensing & Regulatory", "field": "license_start_date",
                            "label": "License Start Date is before the Incorporation Date. Correct it"})
        if not forming and account.license_expiry_date and account.license_expiry_date < date.today():
            missing.append({"section": "Licensing & Regulatory", "field": "license_expiry_date",
                            "label": "Trade licence has expired. A valid licence is needed to onboard the client"})
        need("Licensing & Regulatory", "license_activities", "License Activities", when=not forming)
        need("Licensing & Regulatory", "is_regulated", "Is entity regulated (Yes / No)")
        need("Licensing & Regulatory", "regulator_name", "Name of Regulator", when=account.is_regulated)
        need("Licensing & Regulatory", "regulator_other", "Other Regulator details",
             when=account.is_regulated and account.regulator_name == "Other")
        need("Licensing & Regulatory", "license_category", "License Category", when=account.is_regulated)
        need("Licensing & Regulatory", "regulatory_license_expiry_date", "Current regulatory license expiry",
             when=account.is_regulated and not forming)
        for key, label in (("registered_address", "Registered Address"), ("operating_address", "Operating Address")):
            addr = getattr(account, key) or {}
            if not forming and not all((addr.get(f) or "").strip() for f in ("line1", "city", "country")):
                missing.append({"section": label, "field": key, "label": f"{label} (line 1, city and country)"})
        need("Tax", "financial_year_end", "Financial Year End", when=taxable)
        need("Tax", "corp_tax_registered", "Corporate Tax Registered (Yes / No)", when=taxable)
        need("Introducer", "has_introducer", "Introducer (Yes / No)")
        need("Introducer", "introducer_name", "Introducer Name", when=account.has_introducer)

        # §6 — shareholders must exist and the individuals among them add up to 100%.
        shareholders = [p for p in account.parties if p.party_role == "Shareholder"]
        if is_foundation(account):
            # No shares in a foundation, so no 100% rule; it needs its Founder.
            if not any(p.party_role == "Founder" for p in account.parties):
                missing.append({"section": "Founders", "field": "parties", "label": "At least one Founder"})
            # Triam UAT 10-11-2026: at least two Council Members.
            council = sum(1 for p in account.parties if p.party_role == "Council Member")
            if council < MIN_COUNCIL_MEMBERS:
                missing.append({"section": "Council Members", "field": "parties",
                                "label": f"At least {MIN_COUNCIL_MEMBERS} Council Members (currently {council})"})
            # Triam UAT row 32: the foundation's roles replace Shareholders and Directors. Records made before
            # the client became a foundation are kept, but must go before it is submitted.
            leftover = sorted({p.party_role for p in account.parties if p.party_role in ("Shareholder", "Director")}, reverse=True)
            if leftover:
                missing.append({"section": "Founders", "field": "parties",
                                "label": f"Remove the {' and '.join(leftover)} records: a foundation has Founders, "
                                         "Council Members, Beneficiaries and Guardians instead"})
        elif not shareholders:
            missing.append({"section": PARTIES_SECTION, "field": "parties", "label": "At least one Shareholder / UBO"})
        else:
            total = sum((Decimal(str(p.effective_ownership_percent or 0)) for p in shareholders if counts_towards_ownership(p)), Decimal("0"))
            if abs(total - Decimal("100")) > Decimal("0.01"):
                missing.append({"section": PARTIES_SECTION, "field": "parties",
                                "label": f"Individual shareholding must total 100% (currently {total}%)"})

    # §10 KYC / AML is completed by Compliance after submission — see missing_cdd.

    # Biz Rationale Report (Triam UAT 26-10-2026) — mandatory for every new client.
    for field, label in (("br_person_met", "Full Name of the Person Met"), ("br_meeting_date", "Date of Meeting"),
                         ("br_meeting_time", "Time of Meeting"), ("br_meeting_place", "Place of Meeting"),
                         ("br_meeting_mode", "Mode of Meeting"), ("br_rationale", "Business Rationale for the Relationship")):
        need(BIZ_RATIONALE_SECTION, field, label)

    for p in account.parties:
        # Triam UAT 09-11-2026: a person's address needs Line 1 and City too (the country is Country of Residence).
        addr = p.residential_address or {}
        if not all((addr.get(f) or "").strip() for f in ("line1", "city")):
            missing.append({"section": PARTIES_SECTION, "field": "parties",
                            "label": f"Residential Address of {p.full_name} ({p.party_role}): line 1 and city"})
        from app.services.account_party_service import minor_needs_guardian  # local: that module imports this one
        if minor_needs_guardian(p) and not ((p.guardian_name or "").strip() and (p.guardian_relationship or "").strip()):
            missing.append({"section": PARTIES_SECTION, "field": "parties",
                            "label": f"{p.full_name} ({p.party_role}) is a minor: Parent / Guardian name and relationship"})
        if p.constitution != "Entity" and passport_too_old(p.id_or_license_expiry):
            missing.append({"section": PARTIES_SECTION, "field": "parties",
                            "label": f"The passport of {p.full_name} expired more than {PASSPORT_GRACE_DAYS} days ago"})

    # Triam 20-11-2026: every individual person (UBO, Director, Signatory, Joint Holder, Founder, ...) gives their
    # passport number and expiry. One person in several roles gives them once.
    for records in group_people(account.parties):
        if records[0].constitution == "Entity":
            continue
        who = f"{records[0].full_name} ({', '.join(dict.fromkeys(r.party_role for r in records))})"
        if not any((r.passport_number or "").strip() for r in records):
            missing.append({"section": PARTIES_SECTION, "field": "parties", "label": f"Passport Number of {who}"})
        if not any(r.id_or_license_expiry for r in records):
            missing.append({"section": PARTIES_SECTION, "field": "parties", "label": f"Passport Expiry of {who}"})

    # Triam UAT 04-11-2026, for individual and non-individual clients alike: a document for the client itself;
    # for an individual client, its passport copy (Triam 20-11-2026).
    if account.account_type == "Individual" and not has_passport_copy(account):
        missing.append({"section": "Documents", "field": "documents", "label": "Passport copy of the client"})
    elif not has_supporting_document(account):
        missing.append({"section": "Documents", "field": "documents", "label": "At least one supporting document"})
    # Triam UAT 09/10-11-2026: and one for each person or entity on the client (UBO, Director, Signatory,
    # Joint Holder, Founder, ...). One person in several roles needs one document; for an individual person it is
    # their passport copy (Triam 20-11-2026).
    for records in people_without_documents(account):
        roles = ", ".join(dict.fromkeys(r.party_role for r in records))
        individual = records[0].constitution != "Entity"
        missing.append({"section": "Documents", "field": "party_documents",
                        "label": f"{'Passport copy' if individual else 'A document'} for {records[0].full_name} ({roles})"})

    # §9 engagement — a Yes / No answer, then the validity date when signed
    need("Profile Status & Engagement", "engagement_letter_signed", "Engagement Letter Signed (Yes / No)")
    need("Profile Status & Engagement", "engagement_letter_valid_until", "Engagement Letter valid upto",
         when=account.engagement_letter_signed)
    from sqlalchemy.orm import object_session
    db = object_session(account)
    if db is not None:
        missing.extend(one_time_problems(db, account))
        missing.extend(entity_service_problems(db, account))
    return missing


def missing_cdd(account: Account) -> list[dict]:
    """BRD §10 — the CDD section Compliance (MLRO) must complete before approving.
    (The AML Risk Level Standard / SDD / EDD was removed; EDD applies to High-risk clients.)"""
    missing: list[dict] = []

    def need(field, label, when=True):
        if when and _blank(getattr(account, field)):
            missing.append({"section": "Customer Risk Assessment / KYC & AML", "field": field, "label": label})

    need("risk_rating", "CDD/AML Risk Level")
    need("edd_reason", "Reason for EDD", when=account.risk_rating == "High")
    need("kyc_verified_by", "KYC Verification performed by")
    need("cdd_completion_date", "CDD Completion Date")
    return missing
