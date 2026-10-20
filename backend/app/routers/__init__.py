"""API routers package."""
from app.routers import (
    auth_router, users_router, accounts_router, account_party_router, workflow_router,
    prospects_router, activities_router, instructions_router, invoices_router, documents_router,
    notifications_router, dashboard_router, reports_router, countries_router, department_router,
    masters_router, roles_router, audit_router, system_router,
)

__all__ = [
    "auth_router", "users_router", "accounts_router", "account_party_router", "workflow_router",
    "prospects_router", "activities_router", "instructions_router", "invoices_router", "documents_router",
    "notifications_router", "dashboard_router", "reports_router", "countries_router", "department_router",
    "masters_router", "roles_router", "audit_router", "system_router",
]
