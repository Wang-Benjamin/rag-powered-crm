"""
Temporal Worker for CRM Service
================================

Starts Temporal workers that execute workflows and activities.
The workers run inside the CRM service process.

Workers:
1. Scheduler Worker (<env>-crm-schedulers): Handles shared-DB scheduled tasks
2. Mass Email Worker (<env>-crm-mass-email): Handles user-triggered email workflows
"""

import asyncio
import logging
import os
from temporalio.client import Client, TLSConfig
from temporalio.worker import Worker

# Import scheduler workflows and activities
from temporal_workflows.workflows import (
    MultiTenantSummaryWorkflow,
    MultiTenantSignalWorkflow,
    PersonalizedMassEmailWorkflow
)
# Scheduler activities (safe for sandbox)
from temporal_workflows.activities import (
    discover_all_tenants,
    generate_summaries_for_tenant,
    evaluate_signals_for_tenant,
)
# Email activities imported directly (not through __init__ to avoid sandbox issues)
from temporal_workflows.activities.email_activities import (
    send_single_email_activity,
    update_writing_style_activity,
    update_campaign_email_status_activity,
    finalize_campaign_status_activity,
)
from temporal_workflows.topology import get_temporal_topology

logger = logging.getLogger(__name__)

# Task queue names. These are resolved once at import so routers and workers
# share the same queue values in a given process. Defaults are environment
# prefixed inside the shared Temporal namespace; explicit env var overrides are
# still supported for migration/rollback.
_TOPOLOGY = get_temporal_topology()
SCHEDULER_TASK_QUEUE = _TOPOLOGY.scheduler_task_queue
MASS_EMAIL_TASK_QUEUE = _TOPOLOGY.mass_email_task_queue
WORKFLOW_ID_PREFIX = _TOPOLOGY.workflow_id_prefix

# Client for FastAPI's event loop (used by routers/endpoints)
_api_client: Client = None


def _read_temporal_config():
    """Read and validate Temporal connection config from environment.

    Returns:
        Tuple of (host, namespace, api_key)

    Raises:
        RuntimeError: If required env vars are missing or invalid
    """
    temporal_host = os.getenv("TEMPORAL_HOST", "").strip()
    temporal_namespace = os.getenv("TEMPORAL_NAMESPACE", "").strip()
    temporal_api_key = os.getenv("TEMPORAL_API_KEY", "").replace('\n', '').replace('\r', '').strip()

    if not all([temporal_host, temporal_namespace, temporal_api_key]):
        raise RuntimeError("Missing Temporal configuration in .env (TEMPORAL_HOST, TEMPORAL_NAMESPACE, TEMPORAL_API_KEY)")

    if not all(32 <= ord(c) <= 126 for c in temporal_api_key):
        raise RuntimeError("Temporal API key contains non-printable characters")

    return temporal_host, temporal_namespace, temporal_api_key


async def _build_client() -> Client:
    """Create a new Temporal client from environment config."""
    host, namespace, api_key = _read_temporal_config()
    tls_config = TLSConfig(client_cert=None, client_private_key=None)
    return await Client.connect(
        target_host=host,
        namespace=namespace,
        tls=tls_config,
        rpc_metadata={
            "temporal-namespace": namespace,
            "Authorization": f"Bearer {api_key}",
        },
    )


async def get_temporal_client() -> Client:
    """
    Get or create a Temporal client bound to FastAPI's event loop.
    Used by routers and endpoints — NOT by the worker background thread.

    Returns:
        Temporal Client instance

    Raises:
        RuntimeError: If Temporal is not configured
    """
    global _api_client

    if _api_client is not None:
        return _api_client

    _api_client = await _build_client()
    return _api_client


async def start_scheduler_worker(client: Client):
    """
    Start the scheduler worker for scheduled tasks.

    Handles:
    - MultiTenantSummaryWorkflow (daily at 2 AM)
    - MultiTenantSignalWorkflow (daily at 3 AM)
    """
    logger.info(f"[Scheduler Worker] Creating worker on queue: {SCHEDULER_TASK_QUEUE}")

    worker = Worker(
        client,
        task_queue=SCHEDULER_TASK_QUEUE,
        workflows=[
            MultiTenantSummaryWorkflow,
            MultiTenantSignalWorkflow,
        ],
        activities=[
            discover_all_tenants,
            generate_summaries_for_tenant,
            evaluate_signals_for_tenant,
        ]
    )

    logger.info("[Scheduler Worker] Registered workflows and activities:")
    logger.info("   Workflows: MultiTenantSummaryWorkflow, MultiTenantSignalWorkflow")
    logger.info("   Activities: discover_all_tenants, generate_summaries_for_tenant, evaluate_signals_for_tenant")

    await worker.run()


async def start_mass_email_worker(client: Client):
    """
    Start the mass email worker for user-triggered email workflows.

    Handles:
    - PersonalizedMassEmailWorkflow (AI-generated personalized emails)
    """
    logger.info(f"[Mass Email Worker] Creating worker on queue: {MASS_EMAIL_TASK_QUEUE}")

    worker = Worker(
        client,
        task_queue=MASS_EMAIL_TASK_QUEUE,
        workflows=[
            PersonalizedMassEmailWorkflow
        ],
        activities=[
            send_single_email_activity,
            update_writing_style_activity,
            update_campaign_email_status_activity,
            finalize_campaign_status_activity,
        ]
    )

    logger.info("[Mass Email Worker] Registered workflows and activities:")
    logger.info("   Workflows: PersonalizedMassEmailWorkflow")
    logger.info("   Activities: send_single_email_activity, update_writing_style_activity, update_campaign_email_status_activity, finalize_campaign_status_activity")

    await worker.run()


async def start_temporal_workers():
    """
    Start enabled Temporal workers concurrently.

    This function:
    1. Connects to Temporal Cloud using credentials from .env
    2. Starts only the configured scheduler and/or mass email workers
    3. Runs indefinitely until the service shuts down
    """
    try:
        logger.info("🔧 [Temporal Workers] Initializing Temporal workers...")

        topology = get_temporal_topology()
        topology.validate_worker_startup()

        if not topology.any_worker_enabled:
            logger.info("⏸  [Temporal Workers] No Temporal workers enabled")
            return

        host, namespace, _ = _read_temporal_config()
        logger.info(f"   Temporal Host: {host}")
        logger.info(f"   Temporal Namespace: {namespace}")
        logger.info(f"   App Env: {topology.app_env}")
        logger.info(f"   Queue Prefix: {topology.queue_prefix}")
        logger.info(f"   Scheduler Owner: {topology.scheduler_owner}")
        logger.info(f"   Scheduler Worker Enabled: {topology.scheduler_worker_enabled}")
        logger.info(f"   Mass Email Worker Enabled: {topology.mass_email_worker_enabled}")
        logger.info(f"   Scheduler Queue: {topology.scheduler_task_queue}")
        logger.info(f"   Mass Email Queue: {topology.mass_email_task_queue}")

        # Create a dedicated client for the worker's own event loop.
        # Must NOT reuse _api_client — that belongs to FastAPI's event loop.
        client = await _build_client()
        logger.info("✅ [Temporal Workers] Connected to Temporal Cloud")

        worker_tasks = []
        if topology.scheduler_worker_enabled:
            worker_tasks.append(start_scheduler_worker(client))
        if topology.mass_email_worker_enabled:
            worker_tasks.append(start_mass_email_worker(client))

        # Start configured workers concurrently.
        logger.info("🚀 [Temporal Workers] Starting workers... (listening for workflow executions)")
        await asyncio.gather(*worker_tasks)

    except Exception as e:
        logger.error(f"❌ [Temporal Workers] Failed to start workers: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")


def start_worker_in_background():
    """
    Start the Temporal workers in a background thread.
    Called from main.py during service startup.
    """
    import threading

    def run_workers():
        """Run the workers in a new event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(start_temporal_workers())
        except Exception as e:
            logger.error(f"❌ [Temporal Workers] Worker thread failed: {e}")
        finally:
            loop.close()

    # Start workers in background thread
    worker_thread = threading.Thread(target=run_workers, daemon=True, name="TemporalWorkers")
    worker_thread.start()

    logger.info("✅ [Temporal Workers] Worker thread started in background")
    topology = get_temporal_topology()
    logger.info(f"   App env: {topology.app_env}")
    logger.info(f"   Shared namespace: {topology.namespace or '(not configured)'}")
    logger.info(f"   Scheduler worker enabled: {topology.scheduler_worker_enabled}")
    logger.info(f"   Mass email worker enabled: {topology.mass_email_worker_enabled}")
    logger.info(f"   Scheduler queue: {topology.scheduler_task_queue}")
    logger.info(f"   Mass email queue: {topology.mass_email_task_queue}")
