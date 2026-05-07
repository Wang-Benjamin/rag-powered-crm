"""
Tenant Discovery Activity (asyncpg)
==========================

Temporal activity to discover all tenant databases from the central management database.
Uses TenantPoolManager's analytics pool to query prelude_user_analytics.
"""

import logging
from typing import List, Dict, Any
from temporalio import activity

from service_core.pool import TenantPoolManager

logger = logging.getLogger(__name__)

# Temporal activities run in a separate process/event loop.
# They need their own pool manager instance.
_pool_manager = None


async def _get_pool_manager() -> TenantPoolManager:
    global _pool_manager
    if _pool_manager is None:
        _pool_manager = TenantPoolManager()
    return _pool_manager


@activity.defn(name="discover_all_tenants")
async def discover_all_tenants() -> List[Dict[str, Any]]:
    """
    Query the user_profiles table to discover all unique tenant databases.

    Returns a list of tenant database information, with one representative
    user email per database for routing purposes.

    Returns:
        List of dictionaries with structure:
        [
            {
                'db_name': 'prelude_techcorp',
                'user_email': 'admin@techcorp.com',
                'user_count': 15,
                'company': 'TechCorp Inc.',
            },
            ...
        ]
    """
    try:
        logger.info("[Temporal Activity] Discovering tenant databases from user_profiles table...")

        pm = await _get_pool_manager()
        pool = await pm.get_analytics_pool()

        rows = await pool.fetch(
            """
            SELECT
                db_name,
                COALESCE(
                    MAX(CASE WHEN email = 'prelude@preludeos.com' THEN email END),
                    MIN(email)
                ) as user_email,
                COUNT(*) as user_count,
                MIN(company) as company,
                MIN(role) as sample_role
            FROM user_profiles
            WHERE db_name IS NOT NULL
              AND db_name != ''
              AND db_name != 'default_db'
            GROUP BY db_name
            ORDER BY db_name
            """
        )

        tenant_databases = [dict(row) for row in rows]

        logger.info(f"[Temporal Activity] Found {len(tenant_databases)} tenant databases:")
        for tenant in tenant_databases:
            logger.info(
                f"   {tenant['db_name']}: {tenant['user_count']} users, "
                f"Company: {tenant['company']}"
            )

        return tenant_databases

    except Exception as e:
        logger.error(f"[Temporal Activity] Error discovering tenant databases: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise  # Re-raise to allow Temporal to retry
