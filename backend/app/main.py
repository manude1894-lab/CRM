"""FastAPI application entrypoint."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.routers import (
    auth_router, users_router, accounts_router, account_party_router, workflow_router,
    prospects_router, activities_router, instructions_router, invoices_router, documents_router,
    notifications_router, dashboard_router, reports_router, countries_router, department_router,
    masters_router, roles_router, audit_router, system_router,
)
from app.services.scheduler_jobs import run_daily_sweep
import app.audit  # noqa: F401  registers the audit-trail listener (BRD §15)

logger = logging.getLogger("ezeetech")

scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(run_daily_sweep, trigger="cron", hour=7, id="daily_sla_sweep", replace_existing=True)
    scheduler.start()
    logger.info("APScheduler started — daily SLA sweep scheduled for 07:00")
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Triam CRM API.",
    docs_url="/docs" if settings.API_DOCS_ENABLED else None,
    redoc_url="/redoc" if settings.API_DOCS_ENABLED else None,
    openapi_url="/openapi.json" if settings.API_DOCS_ENABLED else None,
    lifespan=lifespan,
)

# CORS — allow all origins when CORS_ALLOW_ALL=true (useful for Railway demos)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.CORS_ALLOW_ALL else settings.CORS_ORIGINS,
    allow_credentials=not settings.CORS_ALLOW_ALL,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)


# ─── Security headers ─────────────────────────────────────────────────
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


# ─── Root / Health ─────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "api_prefix": settings.API_V1_PREFIX,
    }


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}


# ─── Routers ───────────────────────────────────────────────────────────────
for r in (
    auth_router.router, users_router.router, accounts_router.router, account_party_router.router,
    workflow_router.router, prospects_router.router, activities_router.router,
    instructions_router.router, invoices_router.router, documents_router.router,
    notifications_router.router, dashboard_router.router, reports_router.router,
    countries_router.router, department_router.router, masters_router.router,
    roles_router.router, audit_router.router, system_router.router,
):
    app.include_router(r, prefix=settings.API_V1_PREFIX)
