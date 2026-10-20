# Triam CRM

Client onboarding and servicing CRM for the Triam group of companies, built by Ezee Tech Group. The scope is defined by two documents, which are the source of truth for every feature:

- **Triam CRM – Business Requirements, Scope & Client Sign-Off** (`docs/Triam_CRM_Biz_Req_Scope_stk%20b(1)(1).pdf`)
- **Service Requests – Triam Entities** (request types and statuses for each Triam entity)

**Stack:**
- **Backend:** Python 3.12 · FastAPI · SQLAlchemy 2 · PostgreSQL 16 · Alembic · JWT (access + refresh) · bcrypt · fastapi-mail (SMTP) · APScheduler (in-process daily reminders)
- **Frontend:** React 18 · Vite 5 · Tailwind CSS · Zustand · Axios (with JWT auto-refresh)
- **Infra:** Docker Compose; no Redis or Celery

---

## The flow (BRD)

```
Prospect (BRD §4A)
  Prospecting Coordinator assigns an RM (optional Assignor's comments), or an RM takes it.
  The Prospect ID is the temporary ID.
        │  "Create client" on the assigned prospect (the only way to create a client)
        ▼
Client (BRD §3–§9)                                         status: New → WIP
  RM completes the profile, parties (UBOs / directors / signatories, or joint holders),
  documents and engagement letter, and submits with RM/Sales comments + KYC declaration.
        ▼
Compliance (MLRO) — checker (BRD §8, §10)                  status: Awaiting Approval
  Completes the CDD section (risk level, EDD reason, CDD date → next AML review),
  approves with Compliance comments or rejects back to the RM. Client ID issued here.
        ▼
Approver — final approval (BRD §8)                         status: Approved → Active
        ▼
Existing client (BRD §11, §15, §16)                        Active / Inactive / Marked for Exit / Exited
  Amendments (approved by Compliance, old and new values shown), Visit / Call Reports,
  Service Requests by Triam entity, invoices through the Accounts team.
```

A person who submitted something can never approve it. Records are never deleted; they are cancelled, removed or deactivated with a reason.

## Roles

Each user is an **Administrator** or a **staff user**. A staff user's access comes from their business roles (one person may hold several), maintained in Admin → Roles:

| Role (BRD §13) | What it allows |
|---|---|
| Rel. Manager, Sales Manager, RO, FO | Their own clients (and their team's, for supervisors); create clients from assigned prospects; reports, requests, invoice requests |
| Prospecting Coordinator | Assign prospects to RMs |
| CO / MLRO / Dy MLRO (Compliance) | CDD section, approve or reject new clients and amendments, see all clients |
| Approver | Final approval of new clients; remove submitted documents |
| Accountant | Invoice module: record invoice details and payments |
| Inquiry | Read-only, all clients and reports |

The Ezee Tech support account (`admin@ezeetechgroup.com`) is hidden from every other user and is the only account that can delete a user login.

## Notifications

- **In-app** bell and **email** (`SMTP_*` settings; `SMTP_ENABLED=false` logs instead of sending). **SMS** for the event types in `SMS_NOTIFICATION_TYPES`, once a provider is configured.
- Events: prospect assigned, client submitted / approved / rejected, amendment decisions, invoice requested / raised / paid.
- **Daily 07:00 reminders** (`app/services/scheduler_jobs.py`): next AML review due in 30 / 7 days or overdue (Anchor RM + Compliance), and trade licence expiring in 30 / 7 days or expired (Anchor RM). Each reminder is sent once while unread.

---

## Quickstart — Docker

```bash
docker compose up --build
```

On start the backend runs the migrations and creates only the support account (`admin@ezeetechgroup.com` / `admin123`; change it at once). Then open:
- **Frontend:** http://localhost:3000
- **API docs (Swagger):** http://localhost:8000/docs

For demo users and prospects, run `docker compose exec backend python -m app.seed`. It prints the demo logins: one user per desk (Triam admin, Prospecting Coordinator, two RMs, MLRO, Approver, Accounts, Inquiry).

To clear prospects and clients but keep users and master data: `python -m app.reset_db`.

## Local development

```bash
# PostgreSQL 14+ (e.g. docker run -d -e POSTGRES_USER=crm_user -e POSTGRES_PASSWORD=crm_password -e POSTGRES_DB=prognica_crm -p 5432:5432 postgres:16-alpine)

cd backend
python -m venv .venv && .venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --port 8000

cd ../frontend
npm install
npm run dev                                            # http://localhost:3000
```

Set `VITE_API_URL` in `frontend/.env` if the API isn't on `localhost:8000/api/v1`.

### Tests

```bash
cd backend && pytest -q          # API and business rules (SQLite in memory)
cd frontend && npm test          # Vitest
```

## Project layout

```
backend/app/
  auth/          JWT, password hashing, permission checks
  models/        Prospect, Account (client), AccountParty, ApprovalRequest, Document, Activity,
                 Instruction (service request), Invoice, Notification, User, Role, Department,
                 MasterItem, CountryRisk (countries master), AuditLog
  routers/       one per area: prospects, accounts, account parties, workflow (approvals and
                 amendments), documents, activities, instructions, invoices, dashboard, reports,
                 masters, countries, roles, departments, users, audit, system
  services/      business rules for each area, access control, notifications, daily reminders
  seed.py        support account, countries, optional demo users and prospects
backend/alembic/ migrations (0056 removed the pre-BRD case pipeline)
frontend/src/
  pages/         Dashboard, Prospects, Clients (+ client page), Compliance, Visit & Call Reports,
                 Service Requests, Invoices, Reports, Admin
  components/    shared UI, client form, parties, document folder, workflow bar
docs/            BRD and related documents, architecture.md, data-model.md, go-live-checklist.md
```

## Production notes

See `docs/go-live-checklist.md`: secrets (`JWT_SECRET_KEY`, `JWT_REFRESH_SECRET_KEY`), CORS, SMTP and SMS, backups, master data, users and roles, and loading existing clients.

## License

Private / internal project.
