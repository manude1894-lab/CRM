"""API routers package."""
from app.routers import (
    auth_router, users_router, cases_router, cdd_router, compliance_router,
    accounts_router, activities_router, notifications_router, dashboard_router, reports_router,
)

__all__ = [
    "auth_router", "users_router", "cases_router", "cdd_router", "compliance_router",
    "accounts_router", "activities_router", "notifications_router", "dashboard_router", "reports_router",
]
