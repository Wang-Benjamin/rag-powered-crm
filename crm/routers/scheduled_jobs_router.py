"""
Scheduled Jobs Router - API endpoints for automated background jobs

This router provides HTTP endpoints that can be triggered by Google Cloud Scheduler.
Authentication is handled at the infrastructure level via OIDC tokens.

Endpoints:
Single-tenant (process one tenant):
- POST /scheduled-jobs/deal-stage-progression - Run deal stage progression analysis
- POST /scheduled-jobs/summary-batch - Run batch interaction summary generation

Multi-tenant (process all tenants):
- POST /scheduled-jobs/multi-tenant/summary-batch - Run summary generation across ALL tenants
- POST /scheduled-jobs/multi-tenant/deal-stage-progression - Run deal stage progression across ALL tenants
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import Optional
import logging
import asyncio
import os
from datetime import datetime, timezone

# Import services
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.deal_stage_progression_service import process_deal_stage_progression
from service_core.auth import verify_auth_token

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/scheduled-jobs",
    tags=["Scheduled Jobs"]
)


# DEPRECATED: deal stage progression disabled — replaced by event-driven room_status
@router.post("/deal-stage-progression")
async def trigger_deal_stage_progression(
    background_tasks: BackgroundTasks,
    user_email: str,
    batch_size: int = 10,
    days_lookback: int = 30,
    dry_run: bool = False
):
    """
    Trigger deal stage progression analysis.

    This endpoint runs the deal stage progression service which:
    1. Fetches all active deals (excluding Closed-Won and Closed-Lost)
    2. Analyzes recent emails and notes for each deal
    3. Uses AI to detect stage progression signals
    4. Updates deal stages when clear evidence is found

    **Authentication:**
    - Requires user_email as a query parameter for database routing
    - Can be called by Cloud Scheduler with user_email in the URL

    **Parameters:**
    - user_email: User email for database routing (required)
    - batch_size: Number of deals to process concurrently (default: 10)
    - days_lookback: Days to look back for communications (default: 30)
    - dry_run: If true, only log recommendations without updating database

    **Usage with Cloud Scheduler:**
    ```
    POST https://your-service.run.app/api/scheduled-jobs/deal-stage-progression?user_email=user@example.com
    Body:
      {
        "batch_size": 10,
        "days_lookback": 30,
        "dry_run": false
      }
    ```

    **Manual Testing:**
    ```bash
    curl -X POST "http://localhost:8003/api/crm/scheduled-jobs/deal-stage-progression?user_email=prelude@preludeos.com&dry_run=true" \\
         -H "Content-Type: application/json"
    ```

    **Returns:**
    - 200 OK: Job completed successfully (sync mode)
    - 422: Validation error (missing user_email)
    - 500: Job execution failed
    """

    if not user_email:
        raise HTTPException(status_code=422, detail="user_email is required")

    logger.info("=" * 80)
    logger.info("SCHEDULED JOB TRIGGERED: Deal Stage Progression")
    logger.info(f"Triggered at: {datetime.now(timezone.utc)}")
    logger.info(f"User email: {user_email}")
    logger.info(f"Parameters: batch_size={batch_size}, days_lookback={days_lookback}, dry_run={dry_run}")
    logger.info("=" * 80)
    
    try:
        # Option 1: Run synchronously (wait for completion)
        # Good for: Small workloads, immediate feedback needed
        # Timeout: Cloud Run allows up to 60 minutes

        logger.info("Starting deal stage progression (synchronous mode)...")

        from service_core.db import get_pool_manager
        db_name = await get_pool_manager().lookup_db_name(user_email)

        stats = await process_deal_stage_progression(
            db_name=db_name,
            batch_size=batch_size,
            days_lookback=days_lookback,
            dry_run=dry_run,
            user_email=user_email
        )
        
        logger.info("Deal stage progression completed successfully")
        
        return {
            "status": "completed",
            "message": "Deal stage progression completed successfully",
            "statistics": stats,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": "synchronous"
        }
        
        # Option 2: Run asynchronously (return immediately)
        # Uncomment this section if you want async mode
        """
        def run_job():
            asyncio.run(process_deal_stage_progression(
                batch_size=batch_size,
                days_lookback=days_lookback,
                dry_run=dry_run,
                user_email=None
            ))
        
        background_tasks.add_task(run_job)
        
        logger.info("Deal stage progression started in background")
        
        return {
            "status": "accepted",
            "message": "Deal stage progression job started in background",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": "asynchronous"
        }
        """
        
    except Exception as e:
        logger.error(f"Failed to run deal stage progression: {e}")
        logger.error("Full traceback:", exc_info=True)
        
        raise HTTPException(
            status_code=500,
            detail=f"Job execution failed: {str(e)}"
        )


# DEPRECATED: deal stage progression disabled — replaced by event-driven room_status
@router.get("/deal-stage-progression/status")
async def get_deal_stage_progression_status():
    """
    Get status of the deal stage progression service.

    This is a health check endpoint to verify the service is available.

    **Returns:**
    - Service status and configuration
    """
    return {
        "service": "deal-stage-progression",
        "status": "available",
        "description": "AI-powered deal stage progression analysis",
        "default_config": {
            "batch_size": 10,
            "days_lookback": 30,
            "ai_provider": "openai",
            "ai_model": "gpt-4.1-mini"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.post("/summary-batch")
async def trigger_summary_batch(
    user_email: str,
    test_mode: bool = False,
    max_customers: Optional[int] = None,
):
    """
    Trigger batch interaction summary generation for all customers.

    This endpoint runs the automated summary generation service which:
    1. Fetches all customers requiring summary updates
    2. Generates AI-powered interaction summaries for each customer
    3. Caches summaries for fast retrieval
    4. Performs cleanup of old summaries

    **Authentication:**
    - Handled at infrastructure level via Cloud Run OIDC tokens
    - No authentication required in FastAPI code

    **Parameters:**
    - test_mode: Run in test mode with fewer customers (default: False)
    - max_customers: Optional limit on number of customers to process
    - user_email: Optional email for database routing (for multi-tenant support)

    **Usage with Cloud Scheduler:**
    ```
    POST https://your-service.run.app/api/scheduled-jobs/summary-batch
    Body:
      {
        "test_mode": false,
        "max_customers": null
      }
    ```

    **Manual Testing:**
    ```bash
    curl -X POST "http://localhost:8003/api/scheduled-jobs/summary-batch?test_mode=true" \\
         -H "Content-Type: application/json"
    ```

    **Returns:**
    - Job execution result with status and statistics
    - 500: Job execution failed
    """
    logger.info("=" * 80)
    logger.info("SCHEDULED JOB TRIGGERED: Batch Summary Generation")
    logger.info(f"Triggered at: {datetime.now(timezone.utc)}")
    logger.info(f"Parameters: test_mode={test_mode}, max_customers={max_customers}, user_email={user_email}")
    logger.info("=" * 80)

    from services.interaction_summary_scheduler import summary_scheduler

    try:
        logger.info(f"Starting batch summary generation for user: {user_email}...")

        # Resolve tenant database from user email
        from service_core.db import get_pool_manager
        pm = get_pool_manager()
        db_name = await pm.lookup_db_name(user_email)

        # Call the async method directly (we're already in an async context)
        await summary_scheduler._async_batch_generate_summaries(db_name, test_mode, max_customers, user_email)

        logger.info("Batch summary generation completed successfully")

        return {
            "status": "success",
            "message": "Batch summary generation completed successfully",
            "user_email": user_email,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to run batch summary generation: {e}")
        logger.error("Full traceback:", exc_info=True)

        raise HTTPException(
            status_code=500,
            detail=f"Batch job failed: {str(e)}"
        )

@router.post("/signal-evaluation")
async def trigger_signal_evaluation(user_email: str):
    """
    Run LLM-based signal evaluation for all active customers in a tenant.

    This endpoint runs the SignalEvaluationAgent which:
    1. Finds customers with interactions in the last 30 days
    2. Gathers email, deal room, and interaction history per customer
    3. Sends batches of 5 customers to LLM for signal analysis
    4. Persists signal_level, signal_label, urgency_score, and reasoning
    5. Clears stale signals for inactive customers

    **Parameters:**
    - user_email: User email for database routing (required)

    **Manual Testing:**
    ```bash
    curl -X POST "http://localhost:8003/api/crm/scheduled-jobs/signal-evaluation?user_email=user@example.com"
    ```
    """
    if not user_email:
        raise HTTPException(status_code=422, detail="user_email is required")

    logger.info("=" * 80)
    logger.info("SCHEDULED JOB TRIGGERED: Signal Evaluation")
    logger.info(f"Triggered at: {datetime.now(timezone.utc)}")
    logger.info(f"User email: {user_email}")
    logger.info("=" * 80)

    try:
        from agents.analysis.signal_evaluation_agent import SignalEvaluationAgent
        from service_core.db import get_pool_manager

        pm = get_pool_manager()
        db_name = await pm.lookup_db_name(user_email)
        agent = SignalEvaluationAgent()

        async with pm.acquire(db_name) as conn:
            stats = await agent.evaluate_signals_for_tenant(conn)

        logger.info(f"Signal evaluation completed: {stats}")

        return {
            "status": "success",
            "message": "Signal evaluation completed",
            "statistics": stats,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to run signal evaluation: {e}")
        logger.error("Full traceback:", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Signal evaluation failed: {str(e)}",
        )


# ============================================
# MULTI-TENANT ENDPOINTS - REMOVED
# ============================================
#
# Multi-tenant orchestration has been moved to a separate scheduler service.
# Schedulers now run as Cloud Run Jobs and call the single-tenant endpoints above.
#
# See: prelude/scripts/crm_schedulers/ for the scheduler implementation
# Deployment: Schedulers are deployed separately as Cloud Run Jobs
#
# Previous endpoints (now deprecated):
# - POST /multi-tenant/summary-batch
# - POST /multi-tenant/deal-stage-progression
#
# Scheduler architecture:
# Cloud Scheduler → Scheduler Service (Cloud Run Job) → CRM single-tenant endpoints
#

