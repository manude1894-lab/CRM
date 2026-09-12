"""API routers package."""
from app.routers import (
    auth_router, users_router, cases_router, cdd_router, compliance_router,
    accounts_router, activities_router, notifications_router, dashboard_router, reports_router,
    party_router, instructions_router, invoices_router, aml_router, company_router,
    documents_router, lifecycle_router, formation_router,
    action_points_router, pep_router, generation_router, jurisdictions_router,
    prospects_router, service_subscriptions_router, service_feedback_router,
)

__all__ = [
    "auth_router", "users_router", "cases_router", "cdd_router", "compliance_router",
    "accounts_router", "activities_router", "notifications_router", "dashboard_router", "reports_router",
    "party_router", "instructions_router", "invoices_router", "aml_router", "company_router",
    "documents_router", "lifecycle_router", "formation_router",
    "action_points_router", "pep_router", "generation_router", "jurisdictions_router",
    "prospects_router", "service_subscriptions_router", "service_feedback_router",
]
