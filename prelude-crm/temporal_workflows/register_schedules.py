"""
Temporal Schedule Registration
================================

Script to register Temporal schedules for CRM automated tasks.

Schedules:
1. Summary Generation: Daily at 2 AM UTC (cron: "0 2 * * *")
2. Deal Stage Progression: Daily at 3 AM UTC (cron: "0 3 * * *")

Usage:
    python -m temporal_workflows.register_schedules
"""

import asyncio
import logging
import os
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv
from temporalio.client import Client, Schedule, ScheduleActionStartWorkflow, ScheduleSpec, TLSConfig
from temporal_workflows.topology import require_scheduler_owner

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_temporal_config():
    """Get and sanitize Temporal configuration from environment."""
    temporal_host = os.getenv("TEMPORAL_HOST", "").strip()
    temporal_namespace = os.getenv("TEMPORAL_NAMESPACE", "").strip()
    # Sanitize API key: remove newlines, carriage returns, and whitespace
    temporal_api_key = os.getenv("TEMPORAL_API_KEY", "").replace('\n', '').replace('\r', '').strip()
    return temporal_host, temporal_namespace, temporal_api_key


async def _build_client() -> Client:
    temporal_host, temporal_namespace, temporal_api_key = get_temporal_config()
    tls_config = TLSConfig(
        client_cert=None,
        client_private_key=None,
    )
    return await Client.connect(
        target_host=temporal_host,
        namespace=temporal_namespace,
        tls=tls_config,
        rpc_metadata={
            "temporal-namespace": temporal_namespace,
            "Authorization": f"Bearer {temporal_api_key}"
        }
    )


async def register_summary_schedule(client: Client, topology):
    """
    Register Temporal schedule for multi-tenant summary generation.
    Runs daily at 2 AM UTC.
    """
    try:
        logger.info("📅 Registering summary generation schedule...")

        schedule_id = topology.summary_schedule_id
        
        await client.create_schedule(
            id=schedule_id,
            schedule=Schedule(
                action=ScheduleActionStartWorkflow(
                    workflow="MultiTenantSummaryWorkflow",
                    args=[False],  # test_mode=False
                    id=f"{topology.workflow_id_prefix}-summary-generation-{schedule_id}",
                    task_queue=topology.scheduler_task_queue,
                    execution_timeout=timedelta(hours=3),  # Allow 3 hours for all tenants
                ),
                spec=ScheduleSpec(
                    cron_expressions=["0 2 * * *"],  # 2 AM UTC daily
                ),
            ),
        )

        logger.info(f"✅ Schedule registered: {schedule_id}")
        logger.info(f"   Workflow: MultiTenantSummaryWorkflow")
        logger.info(f"   Cron: 0 2 * * * (2 AM UTC daily)")
        logger.info(f"   Task Queue: {topology.scheduler_task_queue}")

    except Exception as e:
        logger.error(f"❌ Failed to register summary schedule: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise

async def register_signal_evaluation_schedule(client: Client, topology):
    """
    Register Temporal schedule for multi-tenant signal evaluation.
    Runs daily at 3 AM UTC (replaces the deprecated deal-stage slot).
    """
    try:
        logger.info("Registering signal evaluation schedule...")

        schedule_id = topology.signal_schedule_id

        await client.create_schedule(
            id=schedule_id,
            schedule=Schedule(
                action=ScheduleActionStartWorkflow(
                    workflow="MultiTenantSignalWorkflow",
                    id=f"{topology.workflow_id_prefix}-signal-evaluation-{schedule_id}",
                    task_queue=topology.scheduler_task_queue,
                    execution_timeout=timedelta(hours=3),
                ),
                spec=ScheduleSpec(
                    cron_expressions=["0 3 * * *"],  # 3 AM UTC daily
                ),
            ),
        )

        logger.info(f"Schedule registered: {schedule_id}")
        logger.info(f"   Workflow: MultiTenantSignalWorkflow")
        logger.info(f"   Cron: 0 3 * * * (3 AM UTC daily)")
        logger.info(f"   Task Queue: {topology.scheduler_task_queue}")

    except Exception as e:
        logger.error(f"Failed to register signal evaluation schedule: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise


async def main():
    """Register all schedules."""
    logger.info("="*80)
    logger.info("TEMPORAL SCHEDULE REGISTRATION")
    logger.info("="*80)

    topology = require_scheduler_owner()
    logger.info("Scheduler owner confirmed")
    logger.info(f"   App Env: {topology.app_env}")
    logger.info(f"   Shared Namespace: {topology.namespace or '(not configured)'}")
    logger.info(f"   Scheduler Queue: {topology.scheduler_task_queue}")
    logger.info(f"   Summary Schedule: {topology.summary_schedule_id}")
    logger.info(f"   Signal Schedule: {topology.signal_schedule_id}")

    client = await _build_client()
    await register_summary_schedule(client, topology)
    await register_signal_evaluation_schedule(client, topology)

    logger.info("="*80)
    logger.info("All schedules registered successfully")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())
