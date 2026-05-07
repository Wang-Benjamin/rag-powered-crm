"""
Temporal Workflow Router
=========================

API endpoints to manually trigger Temporal workflows for testing and debugging.
"""

import os
import logging
import time
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from service_core.db import get_tenant_connection
from temporal_workflows.worker import get_temporal_client
from temporal_workflows.topology import get_temporal_topology

logger = logging.getLogger(__name__)

router = APIRouter()


def _require_admin(tenant: tuple) -> None:
    """Trigger endpoints fan out across all tenant DBs; restrict to admin."""
    _, user = tenant
    if (user or {}).get("access") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")


def _require_main_scheduler_owner(test_mode: bool = False):
    """Guard shared-DB scheduler triggers.

    Summary/signal jobs mutate shared tenant data, so only APP_ENV=main with
    explicit `TEMPORAL_SCHEDULER_OWNER=true` should trigger them. A test-mode
    override exists for deliberate debugging on non-main envs only — it is
    refused on main so a stray env var cannot weaken the production gate.
    """
    topology = get_temporal_topology()
    allow_test_override = (
        test_mode
        and topology.app_env != "main"
        and os.getenv("ALLOW_NON_MAIN_TEMPORAL_TEST_TRIGGER", "false").strip().lower()
        in ("1", "true", "yes", "on")
    )
    if topology.scheduler_owner or allow_test_override:
        return topology
    raise HTTPException(
        status_code=403,
        detail=(
            "Temporal summary/signal triggers are restricted to APP_ENV=main "
            "with TEMPORAL_SCHEDULER_OWNER=true because local/dev/main share "
            "the same database."
        ),
    )


@router.post("/temporal/trigger-summary")
async def trigger_summary_workflow(
    test_mode: bool = False,
    tenant: tuple = Depends(get_tenant_connection),
):
    """
    Manually trigger the multi-tenant summary generation workflow.

    Args:
        test_mode: If True, process fewer customers per tenant for testing

    Returns:
        Workflow execution details
    """
    try:
        _require_admin(tenant)
        topology = _require_main_scheduler_owner(test_mode=test_mode)
        logger.info(f"📝 Manual trigger: MultiTenantSummaryWorkflow (test_mode={test_mode})")

        client = await get_temporal_client()

        # Start workflow
        handle = await client.start_workflow(
            workflow="MultiTenantSummaryWorkflow",
            args=[test_mode],
            id=f"{topology.workflow_id_prefix}-manual-summary-{int(time.time())}",
            task_queue=topology.scheduler_task_queue,
            execution_timeout=timedelta(hours=3),
        )

        logger.info(f"✅ Workflow started: {handle.id}")

        return {
            "status": "started",
            "workflow_id": handle.id,
            "workflow_type": "MultiTenantSummaryWorkflow",
            "test_mode": test_mode,
            "app_env": topology.app_env,
            "temporal_namespace": topology.namespace,
            "task_queue": topology.scheduler_task_queue,
            "message": "Workflow execution started. Check Temporal Web UI for progress."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to trigger summary workflow: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/temporal/trigger-signal")
async def trigger_signal_workflow(
    tenant: tuple = Depends(get_tenant_connection),
):
    """
    Manually trigger the multi-tenant signal evaluation workflow.

    Returns:
        Workflow execution details
    """
    try:
        _require_admin(tenant)
        topology = _require_main_scheduler_owner(test_mode=False)
        logger.info("Manual trigger: MultiTenantSignalWorkflow")

        client = await get_temporal_client()

        handle = await client.start_workflow(
            workflow="MultiTenantSignalWorkflow",
            args=[],
            id=f"{topology.workflow_id_prefix}-manual-signal-{int(time.time())}",
            task_queue=topology.scheduler_task_queue,
            execution_timeout=timedelta(hours=3),
        )

        logger.info(f"Workflow started: {handle.id}")

        return {
            "status": "started",
            "workflow_id": handle.id,
            "workflow_type": "MultiTenantSignalWorkflow",
            "app_env": topology.app_env,
            "temporal_namespace": topology.namespace,
            "task_queue": topology.scheduler_task_queue,
            "message": "Workflow execution started. Check Temporal Web UI for progress."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger signal workflow: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/temporal/status")
async def get_temporal_status():
    """
    Get Temporal worker status.

    Returns:
        Worker configuration and status
    """
    temporal_host = os.getenv("TEMPORAL_HOST")
    temporal_namespace = os.getenv("TEMPORAL_NAMESPACE")
    topology = get_temporal_topology()

    return {
        "status": "configured" if temporal_host and temporal_namespace else "not_configured",
        "temporal_host": temporal_host,
        "temporal_namespace": temporal_namespace,
        "app_env": topology.app_env,
        "queue_prefix": topology.queue_prefix,
        "scheduler_owner": topology.scheduler_owner,
        "scheduler_worker_enabled": topology.scheduler_worker_enabled,
        "mass_email_worker_enabled": topology.mass_email_worker_enabled,
        "scheduler_task_queue": topology.scheduler_task_queue,
        "mass_email_task_queue": topology.mass_email_task_queue,
        "workflows": [
            "MultiTenantSummaryWorkflow",
            "MultiTenantSignalWorkflow"
        ],
        "schedules": [
            {"id": topology.summary_schedule_id, "cron": "0 2 * * *"},
            {"id": topology.signal_schedule_id, "cron": "0 3 * * *"}
        ]
    }
