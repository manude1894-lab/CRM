# Staging environment

A staging copy of the CRM is where a change is tried before it reaches UAT, which Triam's users work in. It has
its own database with demo data only, so nothing done there touches UAT or production.

## Order of a change

1. A pull request runs the automatic checks (GitHub → Actions → Tests). These are the backend tests (with coverage
   of at least 88%), the frontend tests (logic coverage of at least 80%) and the build. A browser test then signs in
   as each desk on a fresh copy of the CRM and opens every page that desk has. The pull request is merged only when
   all of them pass.
2. Merging to `main` deploys to **staging**. Check the change there.
3. Promote to **UAT**, and after Triam's sign-off to **production**.

## Setting up staging on Railway (once)

1. In the Railway project, open the environment menu → **New Environment** → name it `staging` and choose
   **Duplicate** from the UAT environment. Railway copies the services (frontend, backend, Postgres) and their
   variables. The new Postgres starts empty.
2. On the staging **backend** service, check the variables:
   - `DATABASE_URL`: the staging Postgres (Railway's reference variable `${{Postgres.DATABASE_URL}}`), never UAT's.
   - `JWT_SECRET_KEY` and `JWT_REFRESH_SECRET_KEY`: new values (`openssl rand -hex 32`), different from UAT.
   - `APP_URL`: the staging frontend address.
   - `SMTP_ENABLED=false`, so staging never emails real people.
   - `ALERT_WEBHOOK_URL` / `ALERT_EMAILS`: optional. A separate channel keeps staging errors apart from UAT's.
3. On the staging **frontend** service, set `API_URL` to the staging backend address followed by `/api/v1`.
4. Under each staging service's **Settings → Source**, deploy from the `main` branch. Then set the UAT services to
   deploy only when you choose: turn off automatic deploys, or point them at a `uat` branch you merge into after
   checking staging.
5. Give staging demo users once. In the staging backend's shell, run `python -m app.seed`; it adds the demo
   desks with the password `Demo-2026-pass` and the support account. Never run it on UAT or production.

## Checking a deploy

`GET <backend>/health` returns the commit the server was built from. Admin → System Health shows the same
commit. If it is not the latest commit on `main`, the deploy did not happen. Redeploy the service.
