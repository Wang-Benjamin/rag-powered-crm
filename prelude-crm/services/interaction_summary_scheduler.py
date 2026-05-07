"""
Automated Interaction Summary Batch Service.

Generates interaction summaries for all customers via Google Cloud Scheduler.
Includes enhanced cleanup logic to prevent stale summary accumulation.

Enhanced Cleanup System:
- After ANY successful summary generation (automated, recovery, or manual), all previous summaries
  for that specific customer are automatically deleted
- This ensures each customer has only their most recent summary at all times
- Midnight cleanup continues as a safety net for system-wide cleanup
- Cleanup failures are logged but don't prevent summary generation from completing

Key Features:
1. Batch processing with configurable batch sizes (triggered by Cloud Scheduler)
2. Concurrent processing with rate limiting
3. Comprehensive error handling and logging
4. Performance tracking and statistics
5. Manual trigger capabilities for testing and recovery
6. Post-generation cleanup to maintain data consistency
"""

import asyncio
import logging
import json
import asyncpg
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Any

from service_core.db import get_pool_manager

logger = logging.getLogger(__name__)

class InteractionSummaryScheduler:
    """Service to generate interaction summaries for all customers (triggered by Cloud Scheduler)."""

    def __init__(self):
        self.batch_size = 10  # Process customers in batches to avoid overwhelming the system
        self.max_concurrent = 3  # Maximum concurrent summary generations

    async def _async_batch_generate_summaries(self, db_name: str, test_mode: bool = False, max_customers: Optional[int] = None, user_email: Optional[str] = None):
        """Async batch processing with cleanup of old summaries."""

        start_time = datetime.now(timezone.utc)
        logger.info(f"Starting batch summary generation at {start_time}")
        if user_email:
            logger.info(f"Database routing: Using user_email = {user_email}")

        try:
            async with get_pool_manager().acquire(db_name) as conn:
                # Clear old summaries before generating new ones (unless in test mode)
                if not test_mode:
                    cleared_count = await self._clear_old_automated_summaries(conn)
                    logger.info(f"Cleanup: Cleared {cleared_count} old summaries from previous days")

                # Get ALL customers for complete cache refresh
                customers_to_process = await self._get_customers_needing_updates(conn, test_mode, max_customers)

            if not customers_to_process:
                logger.info("No customers found for processing")
                return

            logger.info(f"Processing {len(customers_to_process)} customers for complete cache refresh")

            # Process customers in batches with concurrency control
            total_processed = 0
            total_successful = 0
            total_errors = 0

            # Create semaphore to limit concurrent processing
            semaphore = asyncio.Semaphore(self.max_concurrent)
            total_skipped = 0

            # Process in batches
            for i in range(0, len(customers_to_process), self.batch_size):
                batch = customers_to_process[i:i + self.batch_size]
                logger.info(f"Processing batch {i//self.batch_size + 1}: customers {i+1}-{min(i+self.batch_size, len(customers_to_process))}")

                # Create tasks for this batch
                tasks = []
                for customer in batch:
                    # Skip customers who already have today's summaries
                    if customer.get('update_reason') == 'has_todays_summary':
                        logger.info(f"Skipping {customer.get('name', 'Unknown')} (ID: {customer['client_id']}) - already has today's automated summary")
                        total_skipped += 1
                        continue

                    task = asyncio.create_task(
                        self._process_single_customer_with_semaphore(semaphore, customer, db_name, user_email)
                    )
                    tasks.append(task)

                # Wait for all tasks in this batch to complete
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Count results
                for result in results:
                    total_processed += 1
                    if isinstance(result, Exception):
                        total_errors += 1
                        logger.error(f"Batch processing error: {result}")
                    elif result:
                        total_successful += 1

                # Small delay between batches to avoid overwhelming the system
                if i + self.batch_size < len(customers_to_process):
                    await asyncio.sleep(2)


            # Log final results
            end_time = datetime.now(timezone.utc)
            duration = end_time - start_time

            logger.info(f"Batch summary generation completed!")
            logger.info(f"Results: {total_successful} successful, {total_errors} errors, {total_processed} processed")
            if total_skipped > 0:
                logger.info(f"Skipped: {total_skipped} customers (already had today's summaries)")
                logger.info(f"Total coverage: {total_successful + total_skipped}/{len(customers_to_process)} customers have summaries ({(total_successful + total_skipped)/len(customers_to_process)*100:.1f}%)")
            else:
                logger.info(f"Cache coverage: {total_successful}/{len(customers_to_process)} customers ({total_successful/len(customers_to_process)*100:.1f}%)")
            logger.info(f"Duration: {duration.total_seconds():.1f} seconds")

            # Store batch job statistics
            async with get_pool_manager().acquire(db_name) as conn:
                await self._store_batch_job_stats(conn, start_time, end_time, total_processed, total_successful, total_errors, 'interaction_summary_batch')

            # Log cache readiness
            total_with_summaries = total_successful + total_skipped
            if total_with_summaries == len(customers_to_process):
                logger.info("Complete cache refresh successful - all customer summaries are now pre-generated!")
            else:
                logger.warning(f"Partial cache refresh - {total_errors} customers failed summary generation")

        except Exception as e:
            logger.error(f"Critical error in batch summary generation: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    async def _process_single_customer_with_semaphore(self, semaphore: asyncio.Semaphore, customer: Dict, db_name: str, user_email: Optional[str] = None) -> bool:
        """Process a single customer with concurrency control."""
        async with semaphore:
            return await self._process_single_customer(customer, db_name, user_email)

    async def _process_single_customer(self, customer: Dict, db_name: str, user_email: Optional[str] = None) -> bool:
        """Process interaction summary for a single customer."""

        customer_id = customer['client_id']
        customer_name = customer.get('name', 'Unknown')

        try:
            logger.info(f"Processing customer {customer_id}: {customer_name}")

            # Create system user for automated processing
            # Use the provided user_email to ensure proper database routing in multi-tenant setup
            system_user = {
                'email': user_email or 'automated-batch@system.local',
                'name': 'Automated Summary System',
                'role': 'system'
            }

            # Import here to avoid circular import
            from routers.interaction_router import _generate_interaction_summary_logic, InteractionSummaryRequest

            # Generate summary using existing logic
            request = InteractionSummaryRequest(days_back=30)  # Default 30 days

            start_time = datetime.now(timezone.utc)
            summary_response = await _generate_interaction_summary_logic(
                str(customer_id),
                request,
                system_user
            )
            end_time = datetime.now(timezone.utc)

            processing_time_ms = int((end_time - start_time).total_seconds() * 1000)

            # Store the generated summary in database
            async with get_pool_manager().acquire(db_name) as conn:
                success = await self._store_generated_summary(
                    conn=conn,
                    customer_id=customer_id,
                    summary_response=summary_response,
                    processing_time_ms=processing_time_ms,
                    generation_type='automated'
                )

            if success:
                logger.info(f"Successfully processed customer {customer_id}: {customer_name}")
                return True
            else:
                logger.error(f"Failed to store summary for customer {customer_id}: {customer_name}")
                return False

        except Exception as e:
            logger.error(f"Error processing customer {customer_id} ({customer_name}): {e}")

            # Store error record
            try:
                async with get_pool_manager().acquire(db_name) as conn:
                    await self._store_error_summary(conn, customer_id, str(e))
            except Exception as store_err:
                logger.error(f"Failed to store error summary: {store_err}")
            return False

    async def _clear_old_automated_summaries(self, conn: asyncpg.Connection) -> int:
        """Clear ALL existing summaries for complete daily refresh (both manual and automated)."""

        try:
            # Delete ALL summaries older than today (both manual and automated)
            result = await conn.execute("""
            DELETE FROM interaction_summaries
            WHERE DATE(generated_at) < CURRENT_DATE
            """)

            deleted_count = int(result.split()[-1]) if result else 0

            logger.info(f"Complete daily cleanup: Cleared {deleted_count} summaries (both manual and automated) from previous days")
            return deleted_count

        except Exception as e:
            logger.error(f"Error clearing old summaries during daily cleanup: {e}")
            return 0

    async def _clear_customer_old_summaries(self, conn: asyncpg.Connection, customer_id: int) -> int:
        """Clear old summaries for a specific customer only (used for manual generation)."""

        try:
            result = await conn.execute("""
            DELETE FROM interaction_summaries
            WHERE customer_id = $1
              AND DATE(generated_at) < CURRENT_DATE
            """, customer_id)

            deleted_count = int(result.split()[-1]) if result else 0

            if deleted_count > 0:
                logger.info(f"Customer-specific cleanup: Cleared {deleted_count} old summaries for customer {customer_id}")

            return deleted_count

        except Exception as e:
            logger.error(f"Error clearing old summaries for customer {customer_id}: {e}")
            return 0

    async def _clear_customer_all_previous_summaries(self, customer_id: int, conn: asyncpg.Connection) -> int:
        """
        Clear ALL previous summaries for a specific customer (post-generation cleanup).

        This method is called after successful summary generation to ensure each customer
        has only their most recent summary, regardless of generation trigger type.

        Args:
            customer_id: Customer ID to clean up summaries for
            conn: asyncpg connection for database access

        Returns:
            int: Number of summaries deleted
        """
        try:
            # First, get the most recent summary ID for this customer
            latest_summary = await conn.fetchrow("""
                SELECT summary_id
                FROM interaction_summaries
                WHERE customer_id = $1
                ORDER BY generated_at DESC
                LIMIT 1
            """, customer_id)

            if not latest_summary:
                return 0

            latest_summary_id = latest_summary['summary_id']

            # Delete all summaries for this customer EXCEPT the most recent one
            result = await conn.execute("""
            DELETE FROM interaction_summaries
            WHERE customer_id = $1
              AND summary_id != $2
            """, customer_id, latest_summary_id)

            deleted_count = int(result.split()[-1]) if result else 0

            if deleted_count > 0:
                logger.info(f"Post-generation cleanup: Removed {deleted_count} previous summaries for customer {customer_id}, keeping latest summary {latest_summary_id}")
            else:
                logger.debug(f"Post-generation cleanup: No previous summaries to remove for customer {customer_id}")

            return deleted_count

        except Exception as e:
            logger.error(f"Error in post-generation cleanup for customer {customer_id}: {e}")
            return 0


    async def _get_customers_needing_updates(self, conn: asyncpg.Connection, test_mode: bool = False, max_customers: Optional[int] = None) -> List[Dict]:
        """Get list of ALL customers for complete cache refresh (expanded coverage for all customers)."""

        try:
            # EXPANDED COVERAGE: Get ALL customers regardless of status for complete cache refresh
            query = """
            WITH customer_summary_info AS (
                SELECT
                    ci.client_id,
                    ci.name,
                    ci.status,
                    ci.created_at as customer_created_at,
                    MAX(ints.generated_at) as last_summary_date,
                    GREATEST(
                        MAX(ic.created_at),
                        MAX(ce.created_at)
                    ) as last_interaction_date,
                    COUNT(DISTINCT ic.interaction_id) + COUNT(DISTINCT ce.email_id) as total_interactions,
                    COUNT(DISTINCT CASE WHEN ic.created_at >= CURRENT_DATE - INTERVAL '30 days' THEN ic.interaction_id END) +
                    COUNT(DISTINCT CASE WHEN ce.created_at >= CURRENT_DATE - INTERVAL '30 days' THEN ce.email_id END) as recent_interactions
                FROM clients ci
                    LEFT JOIN interaction_summaries ints ON ci.client_id = ints.customer_id
                    AND ints.status = 'success'
                    AND ints.generation_type = 'automated'
                    AND ints.generated_at >= CURRENT_DATE
                LEFT JOIN interaction_details ic ON ci.client_id = ic.customer_id
                LEFT JOIN crm_emails ce ON ci.client_id = ce.customer_id
                GROUP BY ci.client_id, ci.name, ci.status, ci.created_at
            )
            SELECT
                client_id,
                name,
                status,
                customer_created_at,
                last_summary_date,
                last_interaction_date,
                total_interactions,
                recent_interactions,
                CASE
                    WHEN last_summary_date IS NULL THEN 'needs_daily_refresh'
                    ELSE 'has_todays_summary'
                END as update_reason
            FROM customer_summary_info
            ORDER BY
                CASE WHEN last_summary_date IS NULL THEN 1 ELSE 2 END,
                recent_interactions DESC,
                total_interactions DESC,
                customer_created_at DESC
            """

            if test_mode:
                query += " LIMIT 5"
            elif max_customers:
                query += f" LIMIT {max_customers}"

            rows = await conn.fetch(query)
            result = [dict(row) for row in rows]

            # Log processing statistics
            total_customers = len(result)
            needs_refresh = sum(1 for c in result if c['update_reason'] == 'needs_daily_refresh')
            has_summary = total_customers - needs_refresh

            logger.info(f"Daily cache refresh: {total_customers} total customers")
            logger.info(f"   - {needs_refresh} need fresh summaries")
            logger.info(f"   - {has_summary} already have today's automated summary")

            # Additional statistics
            if result:
                total_interactions = sum(c['total_interactions'] or 0 for c in result)
                recent_interactions = sum(c['recent_interactions'] or 0 for c in result)
                logger.info(f"   - {total_interactions} total interactions across all customers")
                logger.info(f"   - {recent_interactions} interactions in last 30 days")

            return result

        except Exception as e:
            logger.error(f"Error getting customers for daily refresh: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    async def _store_generated_summary(self, conn: asyncpg.Connection, customer_id: int, summary_response, processing_time_ms: int, generation_type: str) -> bool:
        """Store generated summary in the database with optional zh-CN translation."""

        try:
            # Extract data from summary response
            summary_data = summary_response.summary_data
            interactions_analyzed = summary_response.interactions_analyzed
            period_analyzed = summary_response.period_analyzed

            # ENHANCED AGENT AND MODEL TRACKING
            agent_used = getattr(summary_response, 'agent_used', None)
            ai_model_used = getattr(summary_response, 'ai_model_used', None)

            # Fallback to text parsing only if the enhanced tracking is not available
            if not agent_used:
                logger.warning(f"Agent information not available in response, falling back to text parsing for customer {customer_id}")
                if 'summary' in summary_data and 'AI Agent Analysis' in summary_data['summary']:
                    if 'new customer' in summary_data['summary']:
                        agent_used = 'IcebreakerIntroAgent'
                    elif 'active customer' in summary_data['summary']:
                        agent_used = 'NextActionInsightAgent'
                    elif 'inactive' in summary_data['summary'] or 'restart momentum' in summary_data['summary'].lower():
                        agent_used = 'RestartMomentumInsightAgent'
                    elif 'deal retrospective' in summary_data['summary'].lower():
                        agent_used = 'DealRetrospectiveAgent'
                else:
                    agent_used = 'UnknownAgent'

            # Fallback for model information
            if not ai_model_used:
                logger.warning(f"Model information not available in response, using fallback for customer {customer_id}")
                ai_model_used = 'gpt-4.1-mini'

            logger.info(f"TRACKING: Customer {customer_id} - Agent: {agent_used}, Model: {ai_model_used}")

            # Get the latest interaction date for this customer
            result = await conn.fetchrow("""
                SELECT MAX(created_at) as last_interaction_date
                FROM interaction_details
                WHERE customer_id = $1
            """, customer_id)

            last_interaction_date = result['last_interaction_date'] if result else None

            # Extract days from period_analyzed (e.g., "30 days" -> 30)
            try:
                period_days = int(period_analyzed.split()[0])
            except:
                period_days = 30

            # Generate zh-CN translation
            from services.insight_translation_service import translate_summary_data, _get_source_hash
            summary_data_zh = None
            source_hash = _get_source_hash(summary_data)
            try:
                summary_data_zh = translate_summary_data(summary_data)
                if summary_data_zh:
                    logger.info(f"zh-CN translation generated for customer {customer_id}")
                else:
                    logger.warning(f"zh-CN translation returned None for customer {customer_id}")
            except Exception as zh_err:
                logger.warning(f"zh-CN translation failed for customer {customer_id}: {zh_err}")

            # Insert summary record
            await conn.execute("""
            INSERT INTO interaction_summaries (
                customer_id,
                summary_data,
                summary_data_zh,
                summary_data_zh_translated_at,
                summary_data_zh_source_hash,
                generated_by,
                generation_type,
                period_analyzed_days,
                interactions_analyzed,
                agent_used,
                ai_model_used,
                processing_time_ms,
                status,
                last_interaction_date,
                data_cutoff_date
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15
            )
            """,
                customer_id,
                summary_data,
                summary_data_zh if summary_data_zh else None,
                datetime.now(timezone.utc) if summary_data_zh else None,
                source_hash if summary_data_zh else None,
                'automated_batch_job',
                generation_type,
                period_days,
                interactions_analyzed,
                agent_used,
                ai_model_used,
                processing_time_ms,
                'success',
                last_interaction_date,
                datetime.now(timezone.utc)
            )

            # ENHANCED CLEANUP: After successful summary generation, clean up all previous summaries
            try:
                cleanup_count = await self._clear_customer_all_previous_summaries(customer_id, conn)
                logger.debug(f"Post-generation cleanup completed for customer {customer_id}: {cleanup_count} old summaries removed")
            except Exception as cleanup_error:
                logger.warning(f"Post-generation cleanup failed for customer {customer_id}: {cleanup_error}")

            return True

        except Exception as e:
            logger.error(f"Error storing summary for customer {customer_id}: {e}")
            return False

    async def _store_error_summary(self, conn: asyncpg.Connection, customer_id: int, error_message: str):
        """Store error record for failed summary generation."""

        try:
            await conn.execute("""
            INSERT INTO interaction_summaries (
                customer_id,
                summary_data,
                generated_by,
                generation_type,
                status,
                error_message,
                data_cutoff_date
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7
            )
            """,
                customer_id,
                {"error": "Summary generation failed"},
                'automated_batch_job',
                'automated',
                'error',
                error_message[:1000],
                datetime.now(timezone.utc)
            )

        except Exception as e:
            logger.error(f"Error storing error summary for customer {customer_id}: {e}")

    async def _store_batch_job_stats(self, conn: asyncpg.Connection, start_time: datetime, end_time: datetime,
                              total_processed: int, total_successful: int, total_errors: int,
                              job_type: str = 'interaction_summary_batch'):
        """Store batch job statistics for monitoring."""

        try:
            # Create batch_job_stats table if it doesn't exist
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS batch_job_stats (
                job_id SERIAL PRIMARY KEY,
                job_type VARCHAR(50) NOT NULL,
                start_time TIMESTAMP WITH TIME ZONE NOT NULL,
                end_time TIMESTAMP WITH TIME ZONE NOT NULL,
                duration_seconds INTEGER,
                total_processed INTEGER,
                total_successful INTEGER,
                total_errors INTEGER,
                success_rate DECIMAL(5,2),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """)

            duration_seconds = int((end_time - start_time).total_seconds())
            success_rate = (total_successful / total_processed * 100) if total_processed > 0 else 0

            await conn.execute("""
            INSERT INTO batch_job_stats (
                job_type, start_time, end_time, duration_seconds,
                total_processed, total_successful, total_errors, success_rate
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
                job_type,
                start_time,
                end_time,
                duration_seconds,
                total_processed,
                total_successful,
                total_errors,
                success_rate
            )

        except Exception as e:
            logger.error(f"Error storing batch job stats: {e}")

    async def force_run_now(self, db_name: str, test_mode: bool = False, max_customers: Optional[int] = None) -> Dict[str, Any]:
        """Manually trigger batch summary generation immediately."""

        logger.info("Manual batch summary generation triggered")

        try:
            await self._async_batch_generate_summaries(db_name, test_mode, max_customers)
            return {"status": "success", "message": "Batch job completed successfully"}
        except Exception as e:
            logger.error(f"Error in manual batch job: {e}")
            return {"status": "error", "message": str(e)}

    async def generate_single_customer_summary(self, customer_id: int, authenticated_user: dict,
                                             days_back: int = 30, clear_old: bool = True) -> Dict[str, Any]:
        """
        Generate summary for a single customer with enhanced cleanup.

        This method now uses the same post-generation cleanup logic as automated batch processing
        to ensure consistent behavior regardless of generation trigger type.

        Uses pool_manager directly since this is called from scheduled/manual contexts
        that may not have a pre-existing connection.
        """

        try:
            logger.info(f"Manual summary generation for customer {customer_id}")

            # Extract user email for database routing
            user_email = authenticated_user.get('email', '')

            # Import here to avoid circular import
            from routers.interaction_router import _generate_interaction_summary_logic, InteractionSummaryRequest
            db_name = await get_pool_manager().lookup_db_name(user_email)

            # Optional pre-generation cleanup (legacy behavior for compatibility)
            if clear_old:
                async with get_pool_manager().acquire(db_name) as conn:
                    cleared_count = await self._clear_customer_old_summaries(conn, customer_id)
                    if cleared_count > 0:
                        logger.info(f"Pre-generation cleanup: Cleared {cleared_count} old summaries for customer {customer_id}")

            # Generate summary using existing logic
            request = InteractionSummaryRequest(days_back=days_back)

            start_time = datetime.now(timezone.utc)
            summary_response = await _generate_interaction_summary_logic(
                str(customer_id),
                request,
                authenticated_user
            )
            end_time = datetime.now(timezone.utc)

            processing_time_ms = int((end_time - start_time).total_seconds() * 1000)

            # Store the generated summary (this will automatically trigger post-generation cleanup)
            async with get_pool_manager().acquire(db_name) as conn:
                success = await self._store_generated_summary(
                    conn,
                    customer_id,
                    summary_response,
                    processing_time_ms,
                    generation_type='manual'
                )

            if success:
                logger.info(f"Successfully generated manual summary for customer {customer_id}")
                return {
                    "status": "success",
                    "message": "Summary generated successfully",
                    "summary_response": summary_response,
                    "processing_time_ms": processing_time_ms
                }
            else:
                return {"status": "error", "message": "Failed to store generated summary"}

        except Exception as e:
            logger.error(f"Error generating manual summary for customer {customer_id}: {e}")
            return {"status": "error", "message": str(e)}

    async def get_batch_status(self, db_name: str) -> Dict[str, Any]:
        """Get batch job status information for monitoring."""

        try:
            async with get_pool_manager().acquire(db_name) as conn:
                rows = await conn.fetch("""
                SELECT
                    job_type,
                    start_time,
                    end_time,
                    total_processed,
                    total_successful,
                    total_errors,
                    success_rate
                FROM batch_job_stats
                WHERE DATE(start_time) = CURRENT_DATE
                ORDER BY start_time DESC
                LIMIT 5
                """)

                recent_jobs = [dict(job) for job in rows]

            return {
                "recent_batch_jobs_today": recent_jobs,
                "manual_trigger_available": True
            }

        except Exception as e:
            logger.error(f"Error getting batch status: {e}")
            return {
                "recent_batch_jobs_today": [],
                "manual_trigger_available": False,
                "error": str(e)
            }

# Global scheduler instance
summary_scheduler = InteractionSummaryScheduler()
