"""v1 API aggregator — mounts every FEAT-* router under ``/api/v1``."""

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    agreements,
    applications,
    brands,
    campaigns,
    clerk_webhook,
    collaborations,
    creators,
    deliverables,
    files,
    health,
    mock_payments,
    notifications,
    payments,
    payout_methods,
    reports,
    users,
    webhooks,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(users.router)
api_router.include_router(creators.router)
api_router.include_router(brands.router)
api_router.include_router(files.router)
api_router.include_router(campaigns.router)
api_router.include_router(applications.router)
api_router.include_router(collaborations.router)
api_router.include_router(agreements.router)
api_router.include_router(deliverables.router)
api_router.include_router(payments.router)
api_router.include_router(payout_methods.router)
api_router.include_router(webhooks.router)
api_router.include_router(clerk_webhook.router)
api_router.include_router(notifications.router)
api_router.include_router(reports.router)
api_router.include_router(admin.router)
# Mock endpoints are always mounted; the handlers themselves check the
# ENABLE_MOCK_PAYMENT_ENDPOINTS flag and 404 when disabled so the production
# startup check can still refuse boot with the flag on in prod.
api_router.include_router(mock_payments.router)

__all__ = ["api_router"]
