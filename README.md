# EZEETECH GROUP — DIFC Client Onboarding & Compliance Tracker

A client onboarding and compliance tracker for a DIFC-based corporate services consultancy. Originally a generic B2B sales CRM, repurposed to model the real onboarding workflow: inquiry → RM assignment → CDD/KYC screening → invoicing → ops handoff → regulator submission → license → recurring compliance.

**Stack:**
- **Backend:** Python 3.12 · FastAPI · SQLAlchemy 2 · PostgreSQL 16 · Alembic · JWT (access + refresh) · bcrypt · ReportLab (PDF) · fastapi-mail (SMTP) · APScheduler (in-process daily SLA sweep)
- **Frontend:** React 18 · Vite 5 · Tailwind CSS · Recharts · Zustand · Axios (with JWT auto-refresh)
- **Infra:** Docker Compose (single `up` command brings up the full stack) — no Redis/Celery, by design (cost-sensitive deployment)

---

## Quickstart — Docker (recommended)

Requires Docker + Docker Compose.

```bash
# From the repo root
docker compose up --build
```

Wait ~30s for Postgres to become healthy. The backend will auto-run migrations and seed demo data on first boot.

Then open:
- **Frontend UI:** http://localhost:3000
- **Backend API docs (Swagger):** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

Stop with `docker compose down`. To wipe the DB volume: `docker compose down -v`.

### Demo login credentials

| Role | Email | Password |
|---|---|---|
| Admin | `admin@ezeetechgroup.com` | `admin123` |
| Relationship Manager | `aisha@ezeetechgroup.com` | `rm123` |
| Relationship Manager | `imran@ezeetechgroup.com` | `rm123` |
| Ops | `fatima@ezeetechgroup.com` | `ops123` |
| Screening | `david@ezeetechgroup.com` | `screen123` |

---

## Manual (local dev) setup

### 1. PostgreSQL

```bash
# Any running Postgres 14+ works. Example with Docker:
docker run -d --name prognica-db \
  -e POSTGRES_USER=crm_user \
  -e POSTGRES_PASSWORD=crm_password \
  -e POSTGRES_DB=prognica_crm \
  -p 5432:5432 \
  postgres:16-alpine
```

### 2. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                # edit secrets + SMTP settings
alembic upgrade head                                # create tables
python -m app.seed                                  # seed demo data
uvicorn app.main:app --reload --port 8000
```

The API will be live at http://localhost:8000 with Swagger at `/docs`. On startup, APScheduler registers a daily 07:00 job that sweeps for SLA breaches (see below) — it runs in-process, no extra infra required.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev                                         # Vite dev server on :3000
```

Set `VITE_API_URL` in a `.env` file inside `frontend/` if your API isn't on `localhost:8000/api/v1`.

---

## The onboarding workflow

```
1. New Inquiry           source: Senior Mgmt referral / Social media / Referral / Other
2. RM Assigned           Relationship Manager assigned to the case
3. Docs Requested        RM contacts client to collect CDD/KYC documents
4. CDD/KYC In Review     Docs forwarded to the Screening team
5. CDD Approved          Screening approves the CDD form + KYC verification
6. Invoice Raised        Admin raises the invoice (gated: CDD must be Approved)
7. Invoice Paid          Client pays; Admin marks the invoice Paid
8. Ops Assigned          Work handed to Ops (gated: invoice must be Paid)
9. Application Submitted Ops submits the application to the regulator (DIFC)
10. License Received     Business license received — auto-creates the compliance schedule
11. Active                Recurring: annual renewal, compliance filing, tax filing
```

A case also carries an independent **status** overlay (`Active` / `Docs Pending` / `Rejected` / `On Hold`) so a stall or a screening rejection doesn't have to be modeled as a fork in the stage pipeline.

## Roles & Permissions (RBAC)

| Action | Admin | RM | Ops | Screening |
|---|:-:|:-:|:-:|:-:|
| View all cases | ✓ | only own | ✓ | ✓ |
| Create/edit cases | ✓ | ✓ (own) | ✓ | ✓ |
| Move case stage | ✓ | ✓ (own) | ✓ | ✓ |
| Raise / mark invoice paid | ✓ | ✗ | ✗ | ✗ |
| Approve/reject CDD-KYC | ✓ | ✗ | ✗ | ✓ |
| Delete cases / accounts | ✓ | ✗ | ✗ | ✗ |
| User management | ✓ | ✗ | ✗ | ✗ |

RMs have automatic row-level filtering — they only read/edit cases where they're the assigned RM. This is enforced in the service layer, not just the UI.

## Workflow gating (enforced server-side)

1. A case **cannot** be moved to `Invoice Raised` unless the CDD form **and** KYC verification are both `Approved`.
2. A case **cannot** be moved to `Ops Assigned` unless the invoice is marked `Paid`.
3. Moving to `Invoice Raised` / `Invoice Paid` happens only through the dedicated `POST /cases/{id}/invoice/raise` and `/invoice/mark-paid` endpoints (Admin-only) — this keeps the invoice fields and the stage pointer from ever drifting out of sync.
4. Moving to `License Received` auto-creates the `ComplianceSchedule` row, with renewal/compliance/tax dates computed from `license_received_date` + the configurable cadence (`RENEWAL_CADENCE_MONTHS`, `COMPLIANCE_FILING_CADENCE_MONTHS`, `TAX_FILING_CADENCE_MONTHS` in `.env` — defaults to 12 months each; adjust to your actual DIFC filing calendar).

## Notification engine

No paid SaaS notification service — SMTP via your existing org mailbox, plain in-app notifications, and an in-process scheduler:

- **Email:** `fastapi-mail`, configured via `SMTP_*` env vars. Set `SMTP_ENABLED=false` (the default) to log "would send" instead of dispatching — safe for local/demo use without real credentials.
- **In-app:** a `Notification` table surfaced via a bell icon in the header, polling `/notifications/unread-count` every 45s.
- **Scheduler:** `APScheduler` `BackgroundScheduler`, started from `app/main.py`, no Redis/Celery. Runs daily at 07:00 (`app/services/scheduler_jobs.py::run_daily_sweep`) and checks:
  - Docs pending > 3 business days → notify RM
  - CDD submitted/under review > 2 days → notify Screening
  - CDD approved → notify Admin to raise the invoice (event-driven, fires immediately on stage change, not on the daily sweep)
  - Invoice raised but unpaid > 7 days → notify RM + Admin
  - Renewal due in 60 / 30 / 7 days → notify RM + Admin
  - Compliance filing due in 30 / 7 days → notify Ops + Admin
  - Tax filing due in 30 / 7 days → notify Ops + Admin

  Each check is deduped per (case, notification type) so the daily sweep doesn't re-notify while a breach is still open.

---

## Architecture

```
prognica-crm/
├── backend/                        FastAPI application
│   ├── app/
│   │   ├── auth/                   JWT + bcrypt + role dependencies
│   │   ├── models/                 SQLAlchemy models: Case, CDDRecord, CaseDocument,
│   │   │                           ComplianceSchedule, Notification, Account, Activity, User
│   │   ├── schemas/                Pydantic schemas
│   │   ├── routers/                HTTP routes (cases, cdd, compliance, notifications, ...)
│   │   ├── services/                Business logic: stage gating, CDD review, compliance
│   │   │                           rollover, notification dispatch, scheduled SLA jobs
│   │   ├── reports/                ReportLab PDF generators (4 report types)
│   │   ├── utils/                  business_days.py, uid.py
│   │   ├── config.py               Pydantic settings (.env) — incl. SMTP + cadence config
│   │   ├── database.py             SQLAlchemy engine + session
│   │   ├── main.py                 FastAPI app assembly + APScheduler lifecycle
│   │   └── seed.py                 Demo data loader (DIFC dataset)
│   ├── alembic/                    Database migrations
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                       React SPA
│   ├── src/
│   │   ├── api/                    Axios client + endpoint wrappers (cases, cdd, compliance, notifications, ...)
│   │   ├── components/             Shared UI primitives + NotificationBell
│   │   ├── pages/                  Dashboard, Cases, CDD/Screening, Compliance, Accounts, Activities, Reports, Admin
│   │   ├── store/                  Zustand auth store (persisted)
│   │   └── utils/                  Constants (stages, colors, role labels)
│   ├── Dockerfile
│   ├── nginx.conf
│   └── package.json
├── docker-compose.yml
├── API.md                          API reference (sales-pipeline era — pending refresh)
└── README.md
```

## Production notes

Before deploying to production:

1. **Rotate secrets.** Set `JWT_SECRET_KEY` and `JWT_REFRESH_SECRET_KEY` to random 32-byte hex values:
   ```bash
   openssl rand -hex 32
   ```
   Put them in your environment (never commit `.env`).

2. **Configure real SMTP.** Set `SMTP_ENABLED=true` plus your org's `SMTP_HOST`/`SMTP_USERNAME`/`SMTP_PASSWORD` so notification emails actually send.

3. **Use managed Postgres.** Docker Compose runs Postgres for dev/demo; use RDS, Cloud SQL, or similar in prod.

4. **HTTPS + reverse proxy.** Put the whole stack behind nginx/Caddy/Traefik with TLS.

5. **Change the default admin password immediately** or disable the seed demo users via an env flag.

6. **CORS origins.** Update `CORS_ORIGINS` in the backend `.env` to only your real frontend domains.

7. **Confirm the compliance cadence.** `RENEWAL_CADENCE_MONTHS` / `COMPLIANCE_FILING_CADENCE_MONTHS` / `TAX_FILING_CADENCE_MONTHS` default to 12 — adjust to your actual DIFC filing calendar before relying on the auto-generated due dates.

## License

Private / internal project.
