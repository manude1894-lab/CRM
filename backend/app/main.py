"""FastAPI application entrypoint."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.routers import (
    auth_router, users_router, cases_router, cdd_router, compliance_router,
    accounts_router, activities_router, notifications_router, dashboard_router, reports_router,
    party_router, instructions_router, invoices_router,
)
from app.services.scheduler_jobs import run_daily_sweep

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
    description="EZEETECH GROUP — DIFC client onboarding & compliance tracker API.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
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
    auth_router.router, users_router.router, cases_router.router, cdd_router.router,
    compliance_router.router, accounts_router.router, activities_router.router,
    notifications_router.router, dashboard_router.router, reports_router.router,
    party_router.router, instructions_router.router, invoices_router.router,
):
    app.include_router(r, prefix=settings.API_V1_PREFIX)
