"""
Signal Evaluation Activity
============================

Temporal activity to run LLM-based signal evaluation for a single tenant database.
Calls the CRM service API endpoint (works with both local and GCP deployments).
"""

import logging
import os
from typing import Dict, Any

import httpx
from temporalio import activity

logger = logging.getLogger(__name__)


@activity.defn(name="evaluate_signals_for_tenant")
async def evaluate_signals_for_tenant(user_email: str) -> Dict[str, Any]:
    """
    Run signal evaluation for all active customers in a single tenant database.

    Args:
        user_email: Representative user email for database routing

    Returns:
        Dictionary with evaluation statistics
    """
    try:
        logger.info(
            f"[Temporal Activity] Running signal evaluation for tenant: {user_email}"
        )

        crm_service_url = os.getenv("CRM_SERVICE_URL", "http://localhost:8003")
        endpoint = f"{crm_service_url}/api/crm/scheduled-jobs/signal-evaluation"

        logger.info(f"   Calling CRM service at: {endpoint}")

        async with httpx.AsyncClient(timeout=3600.0) as client:
            response = await client.post(
                endpoint, params={"user_email": user_email}
            )
            response.raise_for_status()
            result = response.json()

        logger.info(
            f"[Temporal Activity] Signal evaluation completed for: {user_email}"
        )
        logger.info(f"   API Response: {result.get('status')}")

        return {
            "status": "success",
            "user_email": user_email,
            "api_response": result,
        }

    except httpx.HTTPStatusError as e:
        logger.error(
            f"[Temporal Activity] HTTP error for {user_email}: "
            f"{e.response.status_code}"
        )
        logger.error(f"   Response: {e.response.text}")
        raise
    except httpx.RequestError as e:
        logger.error(
            f"[Temporal Activity] Request error for {user_email}: {e}"
        )
        raise
    except Exception as e:
        logger.error(
            f"[Temporal Activity] Error running signal evaluation for "
            f"{user_email}: {e}"
        )
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        raise
