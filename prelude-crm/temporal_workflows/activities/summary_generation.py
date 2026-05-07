"""
Summary Generation Activity
============================

Temporal activity to generate interaction summaries for a single tenant database.
Calls the CRM service API endpoint (works with both local and GCP deployments).
"""

import logging
import os
import httpx
from typing import Dict, Any
from temporalio import activity

logger = logging.getLogger(__name__)


@activity.defn(name="generate_summaries_for_tenant")
async def generate_summaries_for_tenant(user_email: str, test_mode: bool = False) -> Dict[str, Any]:
    """
    Generate interaction summaries for all customers in a single tenant database.

    Args:
        user_email: Representative user email for database routing
        test_mode: If True, process fewer customers for testing

    Returns:
        Dictionary with statistics:
        {
            'status': 'success',
            'tenant': 'prelude_techcorp',
            'user_email': 'admin@techcorp.com',
            'customers_processed': 150,
            'timestamp': '2025-12-19T02:00:00'
        }
    """
    try:
        logger.info(f"📝 [Temporal Activity] Generating summaries for tenant: {user_email}")

        # Get CRM service URL from environment (supports both local and GCP)
        crm_service_url = os.getenv("CRM_SERVICE_URL", "http://localhost:8003")
        endpoint = f"{crm_service_url}/api/crm/scheduled-jobs/summary-batch"

        logger.info(f"   Calling CRM service at: {endpoint}")

        # Call the CRM service API endpoint
        async with httpx.AsyncClient(timeout=3600.0) as client:  # 1 hour timeout
            response = await client.post(
                endpoint,
                params={
                    "test_mode": test_mode,
                    "user_email": user_email
                }
            )
            response.raise_for_status()
            result = response.json()

        logger.info(f"✅ [Temporal Activity] Summary generation completed for: {user_email}")
        logger.info(f"   API Response: {result.get('status')}")

        return {
            'status': 'success',
            'user_email': user_email,
            'test_mode': test_mode,
            'api_response': result
        }

    except httpx.HTTPStatusError as e:
        logger.error(f"❌ [Temporal Activity] HTTP error for {user_email}: {e.response.status_code}")
        logger.error(f"   Response: {e.response.text}")
        raise
    except httpx.RequestError as e:
        logger.error(f"❌ [Temporal Activity] Request error for {user_email}: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ [Temporal Activity] Error generating summaries for {user_email}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise  # Re-raise to allow Temporal to retry

