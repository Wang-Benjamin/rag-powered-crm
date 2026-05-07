"""
Multi-Tenant Deal Stage Progression Workflow
=============================================

Temporal workflow that processes deal stage progression for ALL tenant databases.
Replaces: prelude/scripts/crm_schedulers/multi_tenant_deal_stage_scheduler.py

Scheduled to run daily at 3 AM UTC via Temporal Schedule.
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
        process_deal_stages_for_tenant
    )

logger = logging.getLogger(__name__)


@workflow.defn(name="MultiTenantDealStageWorkflow")
class MultiTenantDealStageWorkflow:
    """
    Workflow to process deal stage progression for all tenant databases.

    This workflow:
    1. Discovers all tenant databases from user_profiles table
    2. Iterates through each tenant sequentially
    3. Analyzes deals and updates stages based on AI recommendations
    4. Aggregates results and returns statistics
    """

    @workflow.run
    async def run(
        self,
        batch_size: int = 10,
        days_lookback: int = 30,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Execute multi-tenant deal stage progression.

        Args:
            batch_size: Number of deals to process concurrently per tenant
            days_lookback: Days to look back for communications
            dry_run: If True, only log recommendations without updating database

        Returns:
            Dictionary with aggregated statistics across all tenants
        """
        workflow.logger.info("🚀 [Workflow] Starting multi-tenant deal stage progression")
        workflow.logger.info(f"   Parameters: batch_size={batch_size}, days_lookback={days_lookback}, dry_run={dry_run}")

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
        workflow.logger.info("🔄 [Workflow] Step 2: Processing deal stages for each tenant...")

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
                    process_deal_stages_for_tenant,
                    args=[user_email, batch_size, days_lookback, dry_run],
                    start_to_close_timeout=timedelta(hours=1),  # Allow up to 1 hour per tenant
                    retry_policy=RetryPolicy(
                        maximum_attempts=2,  # Retry once on failure
                        initial_interval=timedelta(seconds=30),
                        maximum_interval=timedelta(minutes=5),
                    )
                )

                # Check if the result has database-level errors (e.g., missing tables)
                stats = result.get('statistics', {})
                has_errors = stats.get('errors', 0) > 0

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
        workflow.logger.info("🎉 [Workflow] Multi-tenant deal stage progression completed")
        workflow.logger.info(f"   Total tenants: {len(tenant_databases)}")
        workflow.logger.info(f"   Successful: {successful}")
        workflow.logger.info(f"   Skipped (database errors): {skipped}")
        workflow.logger.info(f"   Failed: {failed}")

        return {
            'workflow': 'MultiTenantDealStageWorkflow',
            'total_tenants': len(tenant_databases),
            'successful': successful,
            'skipped': skipped,
            'failed': failed,
            'batch_size': batch_size,
            'days_lookback': days_lookback,
            'dry_run': dry_run,
            'results': results
        }

