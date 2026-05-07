"""
Deal Stage Progression Activity
================================

Temporal activity to process deal stage progression for a single tenant database.
Calls the CRM service API endpoint (works with both local and GCP deployments).
"""

import logging
import os
import httpx
from typing import Dict, Any
from temporalio import activity

logger = logging.getLogger(__name__)


@activity.defn(name="process_deal_stages_for_tenant")
async def process_deal_stages_for_tenant(
    user_email: str,
    batch_size: int = 10,
    days_lookback: int = 30,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Process deal stage progression for all active deals in a single tenant database.

    Args:
        user_email: Representative user email for database routing
        batch_size: Number of deals to process concurrently
        days_lookback: Days to look back for communications
        dry_run: If True, only log recommendations without updating database

    Returns:
        Dictionary with statistics:
        {
            'status': 'success',
            'user_email': 'admin@techcorp.com',
            'deals_processed': 25,
            'deals_updated': 5,
            'timestamp': '2025-12-19T03:00:00'
        }
    """
    try:
        logger.info(f"🔄 [Temporal Activity] Processing deal stages for tenant: {user_email}")
        logger.info(f"   Parameters: batch_size={batch_size}, days_lookback={days_lookback}, dry_run={dry_run}")

        # Get CRM service URL from environment (supports both local and GCP)
        crm_service_url = os.getenv("CRM_SERVICE_URL", "http://localhost:8003")
        endpoint = f"{crm_service_url}/api/crm/scheduled-jobs/deal-stage-progression"

        logger.info(f"   Calling CRM service at: {endpoint}")

        # Call the CRM service API endpoint
        async with httpx.AsyncClient(timeout=3600.0) as client:  # 1 hour timeout
            response = await client.post(
                endpoint,
                params={
                    "user_email": user_email,
                    "batch_size": batch_size,
                    "days_lookback": days_lookback,
                    "dry_run": dry_run
                }
            )
            response.raise_for_status()
            result = response.json()

        logger.info(f"✅ [Temporal Activity] Deal stage progression completed for: {user_email}")
        logger.info(f"   API Response: {result.get('status')}")

        return {
            'status': 'success',
            'user_email': user_email,
            'statistics': result.get('statistics', {}),
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
        logger.error(f"❌ [Temporal Activity] Error processing deal stages for {user_email}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise  # Re-raise to allow Temporal to retry

