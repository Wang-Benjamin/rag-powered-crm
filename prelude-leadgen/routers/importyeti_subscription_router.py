"""ImportYeti subscription, stats, and enrichment status endpoints."""

import asyncio
import logging

from fastapi import APIRouter, Depends, Header, Query

from importyeti.clients import internal_bol_client
from importyeti.contracts.subscription import get_subscription_info
from service_core.db import get_tenant_connection

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/importyeti/subscription")
async def get_subscription(tenant=Depends(get_tenant_connection)):
    """Return current subscription/credit info without performing a search."""
    conn, user = tenant
    user_email = user.get("email", "unknown")
    sub_info = await get_subscription_info(conn, user_email)
    return {
        "tier": sub_info["tier"],
        "onboardingStatus": sub_info["onboardingStatus"],
        "trialDaysRemaining": sub_info["trialDaysRemaining"],
        "creditsUsedThisMonth": sub_info["creditsUsedThisMonth"],
        "monthlyCreditsRemaining": sub_info["monthlyCreditsRemaining"],
        "entitlements": sub_info["entitlements"],
        "onboarding": sub_info.get("onboarding"),
    }


@router.get("/importyeti/trial-stats")
async def get_trial_stats(tenant=Depends(get_tenant_connection)):
    """Return usage stats for the trial lock screen (View 6)."""
    conn, user = tenant
    user_email = user.get("email", "unknown")

    buyers_viewed = 0
    try:
        buyers_viewed = await conn.fetchval(
            "SELECT COUNT(*) FROM leads WHERE source = 'importyeti'"
        ) or 0
    except Exception as e:
        logger.warning(f"trial-stats buyers query failed: {e}")

    emails_sent = replies_received = active_conversations = 0
    try:
        from service_core.db import get_pool_manager

        pm = get_pool_manager()
        pool = await pm.get_analytics_pool()
        async with pool.acquire() as aconn:
            emails_sent = await aconn.fetchval(
                "SELECT COUNT(*) FROM outreach_messages WHERE direction = 'outbound' AND from_email IN (SELECT outreach_alias FROM user_profiles WHERE email = $1)",
                user_email,
            ) or 0
            replies_received = await aconn.fetchval(
                "SELECT COUNT(*) FROM outreach_messages WHERE direction = 'inbound' AND to_email IN (SELECT outreach_alias FROM user_profiles WHERE email = $1)",
                user_email,
            ) or 0
            active_conversations = await aconn.fetchval(
                """SELECT COUNT(*) FROM outreach_conversations
                   WHERE user_email = $1
                   AND (SELECT COUNT(*) FROM outreach_messages
                        WHERE conversation_id = outreach_conversations.id
                        AND direction = 'inbound') > 0""",
                user_email,
            ) or 0
    except Exception as e:
        logger.warning(f"trial-stats outreach query failed: {e}")

    return {
        "buyersViewed": buyers_viewed,
        "emailsSent": emails_sent,
        "repliesReceived": replies_received,
        "activeConversations": active_conversations,
    }


@router.get("/importyeti/enrichment-status")
async def get_enrichment_status(
    slugs: str = Query(..., description="Comma-separated company slugs"),
    authorization: str = Header(None),
):
    """Return enrichment status for a batch of slugs (for frontend polling)."""
    auth_token = authorization.replace("Bearer ", "") if authorization else ""
    slug_list = [s.strip() for s in slugs.split(",") if s.strip()][:100]
    if not slug_list:
        return {}

    sem = asyncio.Semaphore(10)

    async def _get_one(slug: str):
        async with sem:
            try:
                company = await internal_bol_client.get_company(slug, auth_token=auth_token)
                if company:
                    return slug, {
                        "enrichmentStatus": company.get("enrichment_status"),
                        "quickScore": company.get("quick_score"),
                        "enrichedScore": company.get("enriched_score"),
                    }
            except Exception:
                pass
            return slug, None

    results = await asyncio.gather(*[_get_one(s) for s in slug_list])
    return {slug: status for slug, status in results if status is not None}
