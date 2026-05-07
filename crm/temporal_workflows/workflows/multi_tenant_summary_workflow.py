"""
Multi-Tenant Summary Generation Workflow
=========================================

Temporal workflow that generates interaction summaries for ALL tenant databases.
Replaces: prelude/scripts/crm_schedulers/multi_tenant_summary_scheduler.py

Scheduled to run daily at 2 AM UTC via Temporal Schedule.
"""

import logging
from datetime import timedelta
from typing import Dict, Any
from temporalio import workflow
from temporalio.common import RetryPolicy

# Import activity type hints
with workflow.unsafe.imports_passed_through():
    from temporal_workflows.activities import (
        discover_all_tenants,
        generate_summaries_for_tenant
    )

logger = logging.getLogger(__name__)


@workflow.defn(name="MultiTenantSummaryWorkflow")
class MultiTenantSummaryWorkflow:
    """
    Workflow to generate interaction summaries for all tenant databases.

    This workflow:
    1. Discovers all tenant databases from user_profiles table
    2. Iterates through each tenant sequentially
    3. Generates interaction summaries for each tenant's customers
    4. Aggregates results and returns statistics
    """

    @workflow.run
    async def run(self, test_mode: bool = False) -> Dict[str, Any]:
        """
        Execute multi-tenant summary generation.

        Args:
            test_mode: If True, process fewer customers per tenant for testing

        Returns:
            Dictionary with aggregated statistics across all tenants
        """
        workflow.logger.info("🚀 [Workflow] Starting multi-tenant summary generation")
        workflow.logger.info(f"   Test mode: {test_mode}")

        # Activity 1: Discover all tenant databases
        workflow.logger.info("📋 [Workflow] Step 1: Discovering tenant databases...")
        
        tenant_databases = await workflow.execute_activity(
            discover_all_tenants,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=10),
                maximum_interval=timedelta(minutes=1),
            )
        )

        workflow.logger.info(f"✅ [Workflow] Found {len(tenant_databases)} tenant databases")

        # Activity 2: Process each tenant sequentially
        workflow.logger.info("📝 [Workflow] Step 2: Generating summaries for each tenant...")

        results = []
        successful = 0
        skipped = 0
        failed = 0

        for idx, tenant in enumerate(tenant_databases, 1):
            db_name = tenant['db_name']
            user_email = tenant['user_email']

            workflow.logger.info(f"   Processing tenant {idx}/{len(tenant_databases)}: {db_name}")

            try:
                result = await workflow.execute_activity(
                    generate_summaries_for_tenant,
                    args=[user_email, test_mode],
                    start_to_close_timeout=timedelta(hours=1),  # Allow up to 1 hour per tenant
                    retry_policy=RetryPolicy(
                        maximum_attempts=2,  # Retry once on failure
                        initial_interval=timedelta(seconds=30),
                        maximum_interval=timedelta(minutes=5),
                    )
                )

                # Check if the result has database-level errors (e.g., missing tables)
                has_errors = result.get('status') == 'error' or result.get('errors', 0) > 0

                if has_errors:
                    results.append({
                        'db_name': db_name,
                        'user_email': user_email,
                        'status': 'skipped',
                        'reason': 'database_error',
                        'result': result
                    })
                    skipped += 1
                    workflow.logger.warning(f"   ⚠️ Skipped: {db_name} (database error, check logs)")
                else:
                    results.append({
                        'db_name': db_name,
                        'user_email': user_email,
                        'status': 'success',
                        'result': result
                    })
                    successful += 1
                    workflow.logger.info(f"   ✅ Completed: {db_name}")

            except Exception as e:
                workflow.logger.error(f"   ❌ Failed: {db_name} - {str(e)}")
                results.append({
                    'db_name': db_name,
                    'user_email': user_email,
                    'status': 'failed',
                    'error': str(e)
                })
                failed += 1

        # Return aggregated results
        workflow.logger.info("🎉 [Workflow] Multi-tenant summary generation completed")
        workflow.logger.info(f"   Total tenants: {len(tenant_databases)}")
        workflow.logger.info(f"   Successful: {successful}")
        workflow.logger.info(f"   Skipped (database errors): {skipped}")
        workflow.logger.info(f"   Failed: {failed}")

        return {
            'workflow': 'MultiTenantSummaryWorkflow',
            'total_tenants': len(tenant_databases),
            'successful': successful,
            'skipped': skipped,
            'failed': failed,
            'test_mode': test_mode,
            'results': results
        }

