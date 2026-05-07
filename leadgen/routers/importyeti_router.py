"""ImportYeti router — compatibility aggregator for split route modules."""

from fastapi import APIRouter

from .importyeti_buyers_router import router as buyers_router
from .importyeti_competitors_router import router as competitors_router
from .importyeti_onboarding_router import router as onboarding_router
from .importyeti_subscription_router import router as subscription_router

router = APIRouter()
router.include_router(subscription_router)
router.include_router(buyers_router)
router.include_router(onboarding_router)
router.include_router(competitors_router)
