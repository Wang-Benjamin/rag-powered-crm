"""
Cached Summary Service for retrieving pre-generated interaction summaries.
Provides fast access to cached summaries with fallback to real-time generation.
"""

import logging
import json
import asyncpg
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

class CachedSummaryService:
    """Service for managing cached interaction summaries."""

    def __init__(self):
        self.cache_expiry_hours = 24  # Consider summaries stale after 24 hours
        self.fallback_enabled = True  # Enable fallback to real-time generation

    async def get_summary(self, customer_id: int, authenticated_user: dict,
                         conn: asyncpg.Connection,
                         days_back: int = 30, force_refresh: bool = False,
                         locale: str = "en"):
        """
        Get interaction summary for a customer.

        Args:
            customer_id: Customer ID
            authenticated_user: Authenticated user info
            conn: asyncpg connection for database access
            days_back: Number of days to analyze
            force_refresh: Force real-time generation instead of using cache
            locale: User locale (e.g. 'en', 'zh-CN') — serves zh translation when available

        Returns:
            InteractionSummaryResponse: Summary data
        """

        # If force_refresh is requested, skip cache and generate real-time with selective cleanup
        if force_refresh:
            logger.info(f"Force refresh requested for customer {customer_id}")
            return await self._generate_realtime_summary_with_cleanup(customer_id, authenticated_user, days_back)

        # Try to get cached summary first
        cached_summary = await self._get_cached_summary(customer_id, days_back, conn)

        if cached_summary and self._is_cache_valid(cached_summary):
            logger.info(f"Using cached summary for customer {customer_id}")
            return await self._convert_cached_to_response(cached_summary, customer_id, conn, locale=locale)

        # Cache miss or stale - check if fallback is enabled
        if self.fallback_enabled:
            logger.info(f"Cache miss/stale for customer {customer_id}, generating real-time summary")

            # Generate real-time summary and cache it
            summary_response = await self._generate_realtime_summary(customer_id, authenticated_user, days_back)

            # Store the new summary in cache (mark as manual generation)
            await self._store_manual_summary(customer_id, summary_response, conn)

            return summary_response
        else:
            # No fallback - return empty/error response
            logger.warning(f"No cached summary available for customer {customer_id} and fallback disabled")
            raise Exception("No cached summary available and real-time generation is disabled")

    async def _get_cached_summary(self, customer_id: int, days_back: int, conn: asyncpg.Connection) -> Optional[Dict]:
        """Get the most recent cached summary for a customer (prioritize today's automated summaries)."""

        try:
            # OPTIMIZATION: Prioritize today's automated summaries for instant cache hits
            query = """
            SELECT
                summary_id,
                customer_id,
                summary_data,
                summary_data_zh,
                generated_at,
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
            FROM interaction_summaries
            WHERE customer_id = $1
                AND status = 'success'
                AND period_analyzed_days >= $2
            ORDER BY
                CASE
                    WHEN generation_type = 'automated' AND DATE(generated_at) = CURRENT_DATE THEN 1
                    WHEN generation_type = 'automated' THEN 2
                    WHEN generation_type = 'manual' THEN 3
                    ELSE 4
                END,
                generated_at DESC
            LIMIT 1
            """

            result = await conn.fetchrow(query, customer_id, days_back)

            if result:
                result_dict = dict(result)
                summary_type = result_dict['generation_type']
                summary_date = result_dict['generated_at']
                is_todays_automated = (summary_type == 'automated' and
                                     summary_date.date() == datetime.now(timezone.utc).date())

                if is_todays_automated:
                    logger.info(f"Found today's pre-generated summary for customer {customer_id}")
                else:
                    logger.info(f"Found cached summary for customer {customer_id} (type: {summary_type}, date: {summary_date.date()})")

            return dict(result) if result else None

        except Exception as e:
            logger.error(f"Error getting cached summary for customer {customer_id}: {e}")
            return None

    def _is_cache_valid(self, cached_summary: Dict) -> bool:
        """Check if cached summary is still valid (optimized for daily automated summaries)."""

        try:
            generated_at = cached_summary['generated_at']
            generation_type = cached_summary.get('generation_type', 'manual')

            # Handle both datetime objects and strings
            if isinstance(generated_at, str):
                generated_at = datetime.fromisoformat(generated_at.replace('Z', '+00:00'))
            if generated_at.tzinfo is None:
                generated_at = generated_at.replace(tzinfo=timezone.utc)

            # OPTIMIZATION: Today's automated summaries are always valid (until tomorrow)
            if generation_type == 'automated' and generated_at.date() == datetime.now(timezone.utc).date():
                logger.info(f"Today's automated summary is valid for customer")
                return True

            # For other summaries, use standard expiry logic
            expiry_time = generated_at + timedelta(hours=self.cache_expiry_hours)
            current_time = datetime.now(timezone.utc)
            is_valid = current_time < expiry_time

            if not is_valid:
                logger.info(f"Cached summary expired: generated {generated_at}, expires {expiry_time}")
            else:
                logger.info(f"Cached summary is valid: generated {generated_at}, type {generation_type}")

            return is_valid

        except Exception as e:
            logger.error(f"Error checking cache validity: {e}")
            return False

    async def _convert_cached_to_response(self, cached_summary: Dict, customer_id: int, conn: asyncpg.Connection, locale: str = "en"):
        """Convert cached summary data to InteractionSummaryResponse format.

        When locale starts with 'zh' and a Chinese translation exists, returns the
        translated version. Falls back to English if no translation is available.
        """

        try:
            summary_data = cached_summary['summary_data']
            if isinstance(summary_data, str):
                summary_data = json.loads(summary_data)

            # Serve zh-CN translation when available and locale matches
            if locale.startswith('zh'):
                summary_data_zh = cached_summary.get('summary_data_zh')
                if summary_data_zh:
                    if isinstance(summary_data_zh, str):
                        summary_data_zh = json.loads(summary_data_zh)
                    summary_data = summary_data_zh
                    logger.debug(f"Serving zh-CN translation for customer {customer_id}")

            # Get customer name from database
            customer_name = await self._get_customer_name(customer_id, conn)

            # Import here to avoid circular import
            from routers.interaction_router import InteractionSummaryResponse

            return InteractionSummaryResponse(
                status="success",
                summary_data=summary_data,
                customer_id=customer_id,
                customer_name=customer_name,
                interactions_analyzed=cached_summary['interactions_analyzed'],
                period_analyzed=f"{cached_summary['period_analyzed_days']} days",
                generated_at=cached_summary['generated_at'].isoformat() if hasattr(cached_summary['generated_at'], 'isoformat') else str(cached_summary['generated_at']),
            )

        except Exception as e:
            logger.error(f"Error converting cached summary to response: {e}")
            raise Exception(f"Failed to convert cached summary: {e}")

    async def _get_customer_name(self, customer_id: int, conn: asyncpg.Connection) -> str:
        """Get customer name from database."""

        try:
            result = await conn.fetchrow("SELECT name FROM clients WHERE client_id = $1", customer_id)
            return result['name'] if result else f"Customer {customer_id}"

        except Exception as e:
            logger.error(f"Error getting customer name for {customer_id}: {e}")
            return f"Customer {customer_id}"

    async def _generate_realtime_summary(self, customer_id: int, authenticated_user: dict, days_back: int):
        """Generate real-time summary using existing logic."""

        # Import here to avoid circular import
        from routers.interaction_router import _generate_interaction_summary_logic, InteractionSummaryRequest

        request = InteractionSummaryRequest(days_back=days_back)
        return await _generate_interaction_summary_logic(str(customer_id), request, authenticated_user)

    async def _generate_realtime_summary_with_cleanup(self, customer_id: int, authenticated_user: dict, days_back: int):
        """Generate real-time summary with customer-specific cleanup for manual triggers."""

        # Import here to avoid circular import
        from services.interaction_summary_scheduler import summary_scheduler

        # Use the scheduler's selective cleanup method for individual customers
        result = await summary_scheduler.generate_single_customer_summary(
            customer_id,
            authenticated_user,
            days_back,
            clear_old=True  # Clear only this customer's old summaries
        )

        if result["status"] == "success":
            return result["summary_response"]
        else:
            raise Exception(f"Failed to generate summary: {result['message']}")

    async def _store_manual_summary(self, customer_id: int, summary_response, conn: asyncpg.Connection):
        """Store manually generated summary in cache with enhanced cleanup."""

        try:
            # Get the latest interaction date for this customer
            result = await conn.fetchrow("""
                SELECT MAX(created_at) as last_interaction_date
                FROM interaction_details
                WHERE customer_id = $1
            """, customer_id)

            last_interaction_date = result['last_interaction_date'] if result else None

            # Extract days from period_analyzed
            try:
                period_days = int(summary_response.period_analyzed.split()[0])
            except:
                period_days = 30

            # Extract agent and model information from response
            agent_used = getattr(summary_response, 'agent_used', None)
            ai_model_used = getattr(summary_response, 'ai_model_used', None)

            # Generate zh-CN translation
            from services.insight_translation_service import translate_summary_data, _get_source_hash
            summary_data_zh = None
            source_hash = _get_source_hash(summary_response.summary_data)
            try:
                summary_data_zh = translate_summary_data(summary_response.summary_data)
                if summary_data_zh:
                    logger.info(f"zh-CN translation generated for manual summary, customer {customer_id}")
            except Exception as zh_err:
                logger.warning(f"zh-CN translation failed for manual summary, customer {customer_id}: {zh_err}")

            # Insert summary record with enhanced tracking
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
                status,
                last_interaction_date,
                data_cutoff_date
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
            )
            """,
                customer_id,
                summary_response.summary_data,
                summary_data_zh if summary_data_zh else None,
                datetime.now(timezone.utc) if summary_data_zh else None,
                source_hash if summary_data_zh else None,
                'manual_fallback',
                'manual',
                period_days,
                summary_response.interactions_analyzed,
                agent_used,
                ai_model_used,
                'success',
                last_interaction_date,
                datetime.now(timezone.utc)
            )

            logger.info(f"Stored manual summary for customer {customer_id}")

            # ENHANCED CLEANUP: After successful summary storage, clean up all previous summaries for this customer
            try:
                from services.interaction_summary_scheduler import summary_scheduler
                cleanup_count = await summary_scheduler._clear_customer_all_previous_summaries(customer_id, conn)
                logger.debug(f"Post-generation cleanup completed for customer {customer_id}: {cleanup_count} old summaries removed")
            except Exception as cleanup_error:
                # Log cleanup errors but don't fail the entire operation
                logger.warning(f"Post-generation cleanup failed for customer {customer_id}: {cleanup_error}")

        except Exception as e:
            logger.error(f"Error storing manual summary for customer {customer_id}: {e}")

    async def get_cache_stats(self, conn: asyncpg.Connection) -> Dict[str, Any]:
        """Get comprehensive cache statistics for monitoring (optimized for daily refresh).

        Args:
            conn: asyncpg connection for database access
        """

        try:
            # Get comprehensive cache statistics
            row = await conn.fetchrow("""
            WITH customer_counts AS (
                SELECT COUNT(*) as total_customers
                FROM clients
            ),
            summary_stats AS (
                SELECT
                    COUNT(*) as total_summaries,
                    COUNT(CASE WHEN status = 'success' THEN 1 END) as successful_summaries,
                    COUNT(CASE WHEN status = 'error' THEN 1 END) as error_summaries,
                    COUNT(CASE WHEN generation_type = 'automated' THEN 1 END) as automated_summaries,
                    COUNT(CASE WHEN generation_type = 'manual' THEN 1 END) as manual_summaries,
                    COUNT(CASE WHEN generated_at >= CURRENT_DATE THEN 1 END) as todays_summaries,
                    COUNT(CASE WHEN generation_type = 'automated' AND DATE(generated_at) = CURRENT_DATE THEN 1 END) as todays_automated_summaries,
                    AVG(processing_time_ms) as avg_processing_time_ms,
                    MAX(generated_at) as last_generation_time
                FROM interaction_summaries
            )
            SELECT
                cc.total_customers,
                ss.*,
                CASE
                    WHEN cc.total_customers > 0 THEN
                        ROUND((ss.todays_automated_summaries::DECIMAL / cc.total_customers * 100), 2)
                    ELSE 0
                END as cache_coverage_percentage
            FROM customer_counts cc, summary_stats ss
            """)

            result = dict(row) if row else {}

            # Add cache readiness indicator
            if result:
                coverage = result.get('cache_coverage_percentage', 0)
                result['cache_status'] = (
                    'fully_populated' if coverage >= 95 else
                    'mostly_populated' if coverage >= 80 else
                    'partially_populated' if coverage >= 50 else
                    'needs_refresh'
                )

            return result

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}

    async def clear_cache(self, conn: asyncpg.Connection, customer_id: Optional[int] = None, older_than_days: Optional[int] = None) -> int:
        """Clear cached summaries.

        Args:
            conn: asyncpg connection for database access
            customer_id: Optional customer ID to clear cache for specific customer
            older_than_days: Optional number of days to clear cache older than
        """

        try:
            if customer_id:
                # Clear cache for specific customer
                result = await conn.execute("DELETE FROM interaction_summaries WHERE customer_id = $1", customer_id)
            elif older_than_days:
                # Clear cache older than specified days
                result = await conn.execute("""
                DELETE FROM interaction_summaries
                WHERE generated_at < NOW() - MAKE_INTERVAL(days => $1)
                """, older_than_days)
            else:
                # Clear all cache
                result = await conn.execute("DELETE FROM interaction_summaries")

            # asyncpg execute returns a status string like 'DELETE 5'
            deleted_count = int(result.split()[-1]) if result else 0

            logger.info(f"Cleared {deleted_count} cached summaries")
            return deleted_count

        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return 0

# Global service instance
cached_summary_service = CachedSummaryService()
