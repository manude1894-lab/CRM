# Triam CRM – Go-live checklist

Work through this list in order before Triam's users start using the system with real client data.
Admin → **System Health** in the CRM shows which of the security and configuration items are still open.

## 1. Security settings (hosting platform → backend service → Variables)

| Variable | Value | Why |
|---|---|---|
| `JWT_SECRET_KEY` | a long random value, e.g. output of `openssl rand -hex 32` | Signs login sessions. The default value is public. |
| `JWT_REFRESH_SECRET_KEY` | a **different** long random value | Signs "stay signed in" tokens. |
| `CORS_ALLOW_ALL` | `false` | Only the CRM's own web address may call the API. |
| `CORS_ORIGINS` | `["https://<the CRM web address>"]` | The allowed web address. |

Changing the two secrets signs everyone out once; they simply sign in again.

## 2. Accounts

- [ ] Sign in as `admin@ezeetechgroup.com` and change the password (**Password**, bottom of the menu). The CRM shows a reminder until this is done.
- [ ] Create a named administrator account for Triam's own system owner, then deactivate or rename the generic admin if Triam prefers.
- [ ] Create users (Admin → Users & Departments) with their department, supervisor, business role and mobile number.
- [ ] Give the CO, MLRO and Dy MLRO roles to at least two people, so no one has to approve their own work. Name the Approver(s), the Accountant(s) and the Prospecting Coordinator.
- [ ] Passwords for new users: at least 10 characters with letters and numbers. Ask users to change the first password you give them.

Five wrong passwords in a row lock an account for 15 minutes. An administrator can unlock it at once by setting a new password for the user.

## 3. Email and SMS

- [ ] Email: `SMTP_ENABLED=true`, `SMTP_HOST`, `SMTP_PORT` (587), `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` (Triam's mailbox). Send a test by submitting a test client for approval.
- [ ] SMS (when Triam has chosen a provider): `SMS_ENABLED=true`, `SMS_PROVIDER=http`, `SMS_API_URL`, `SMS_API_KEY`, `SMS_SENDER_ID`. Which events send an SMS is set by `SMS_NOTIFICATION_TYPES`.

## 4. Backups

- [ ] Turn on daily backups for the database on the hosting platform, with weekly copies kept.
- [ ] Or run `scripts/backup_db.sh` once a day from a scheduled job (keeps 14 daily and 8 weekly backups).
- [ ] On a Windows machine/server: put the Railway public database address in `scripts/backup.config` (`DATABASE_URL=postgresql://...`, never committed), then run `scripts/register_backup_task.ps1 -PgDump "<path to pg_dump.exe>"` once. It backs up daily at 02:00 to `D:\Backups\TriamCRM` (14 daily + 8 weekly copies). Test a restore into an empty database once.
- [ ] **Test a restore** into a spare database before go-live, and note how long it took.

## 5. Master data (Admin → Master Data)

Replace the starter values with Triam's final lists: Triam entities, services, licensing authorities, regulators, tags, document categories, rejection reasons and service request types.

## 6. Loading existing clients

Clients → Import CSV (administrators). The import shows a preview first. Fix any rows marked *Error* in the spreadsheet and import the file again; rows already loaded are recognised and skipped. New clients are always entered through Prospects.

## 7. Acceptance and parallel run

- [ ] UAT round 2 with Triam's users, one session per role (Prospecting Coordinator, RM, Compliance, Approver, Accounts, Administrator).
- [ ] Two weeks running the CRM alongside the Excel trackers, then retire the trackers.
- [ ] Sign-off of the Business Requirements & Scope document and its open items (Section 22).
