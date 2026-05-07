"""
Multi-Tenant Signal Evaluation Workflow
========================================

Temporal workflow that runs LLM-based signal evaluation for ALL tenant databases.
Replaces the deprecated deal-stage progression workflow.

Scheduled to run daily at 3 AM UTC via Temporal Schedule.
"""

import logging
from datetime import timedelta
from typing import Dict, Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from temporal_workflows.activities import (
        discover_all_tenants,
    )
    from temporal_workflows.activities.signal_evaluation import (
        evaluate_signals_for_tenant,
    )

logger = logging.getLogger(__name__)


@workflow.defn(name="MultiTenantSignalWorkflow")
class MultiTenantSignalWorkflow:
    """
    Workflow to evaluate customer signals for all tenant databases.

    This workflow:
    1. Discovers all tenant databases from user_profiles table
    2. Iterates through each tenant sequentially
    3. Runs LLM-based signal evaluation for each tenant's active customers
    4. Aggregates results and returns statistics
    """

    @workflow.run
    async def run(self) -> Dict[str, Any]:
        """
        Execute multi-tenant signal evaluation.

        Returns:
            Dictionary with aggregated statistics across all tenants
        """
        workflow.logger.info(
            "[Workflow] Starting multi-tenant signal evaluation"
        )

        # Activity 1: Discover all tenant databases
        workflow.logger.info(
            "[Workflow] Step 1: Discovering tenant databases..."
        )

        tenant_databases = await workflow.execute_activity(
            discover_all_tenants,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=10),
                maximum_interval=timedelta(minutes=1),
            ),
        )

        workflow.logger.info(
            f"[Workflow] Found {len(tenant_databases)} tenant databases"
        )

        # Activity 2: Evaluate signals for each tenant sequentially
        workflow.logger.info(
            "[Workflow] Step 2: Evaluating signals for each tenant..."
        )

        results = []
        successful = 0
        failed = 0

        for idx, tenant in enumerate(tenant_databases, 1):
            db_name = tenant["db_name"]
            user_email = tenant["user_email"]

            workflow.logger.info(
                f"   Processing tenant {idx}/{len(tenant_databases)}: {db_name}"
            )

            try:
                result = await workflow.execute_activity(
                    evaluate_signals_for_tenant,
                    args=[user_email],
                    start_to_close_timeout=timedelta(hours=1),
                    retry_policy=RetryPolicy(
                        maximum_attempts=2,
                        initial_interval=timedelta(seconds=30),
                        maximum_interval=timedelta(minutes=5),
                    ),
                )

                results.append(
                    {
                        "db_name": db_name,
                        "user_email": user_email,
                        "status": "success",
                        "result": result,
                    }
                )
                successful += 1
                workflow.logger.info(f"   Completed: {db_name}")

            except Exception as e:
                workflow.logger.error(f"   Failed: {db_name} - {str(e)}")
                results.append(
                    {
                        "db_name": db_name,
                        "user_email": user_email,
                        "status": "failed",
                        "error": str(e),
                    }
                )
                failed += 1

        workflow.logger.info(
            "[Workflow] Multi-tenant signal evaluation completed"
        )
        workflow.logger.info(f"   Total tenants: {len(tenant_databases)}")
        workflow.logger.info(f"   Successful: {successful}")
        workflow.logger.info(f"   Failed: {failed}")

        return {
            "workflow": "MultiTenantSignalWorkflow",
            "total_tenants": len(tenant_databases),
            "successful": successful,
            "failed": failed,
            "results": results,
        }
