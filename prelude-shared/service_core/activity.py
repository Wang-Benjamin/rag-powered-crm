"""
Shared Activity Logger — logs business events and platform telemetry.

Two targets:
  - log()  → per-tenant activity_log table (business events)
  - track() → shared prelude_user_analytics.activity_log (telemetry)

conn=None falls back to get_current_conn() (contextvars) for tenant writes.
track() always acquires its own connection from the analytics pool.
All methods are fire-and-forget — they never raise.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from service_core.db import get_current_conn, get_current_user, get_pool_manager

logger = logging.getLogger(__name__)


class ActivityLogger:
    """Shared activity logger for per-tenant and analytics databases."""

    @staticmethod
    async def log(
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        details: dict | None = None,
        user_id: str | None = None,
        conn=None,
    ) -> None:
        """Log business activity to the per-tenant DB. Fire-and-forget, never raises."""
        try:
            c = conn or get_current_conn()

            if user_id is None:
                try:
                    user = get_current_user()
                    user_id = user.get("email", "unknown")
                except RuntimeError:
                    user_id = "unknown"

            now = datetime.now(timezone.utc)

            await c.execute(
                """
                INSERT INTO activity_log (user_id, action, resource_type, resource_id, details, created_at)
                VALUES ($1, $2, $3, $4::uuid, $5::jsonb, $6)
                """,
                user_id,
                action,
                resource_type,
                resource_id,
                details or {},
                now,
            )
            logger.debug("Activity logged: %s/%s for %s", action, resource_type, user_id)
        except Exception as e:
            logger.error("Failed to log activity (%s/%s): %s", action, resource_type, e)

    @staticmethod
    async def track(
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        details: dict | None = None,
        user_id: str | None = None,
    ) -> None:
        """Log platform telemetry to the analytics DB. Fire-and-forget, never raises.

        Gets its own connection from get_pool_manager().get_analytics_pool().
        """
        try:
            if user_id is None:
                try:
                    user = get_current_user()
                    user_id = user.get("email", "unknown")
                except RuntimeError:
                    user_id = "unknown"

            now = datetime.now(timezone.utc)

            pm = get_pool_manager()
            pool = await pm.get_analytics_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO activity_log (user_id, action, resource_type, resource_id, details, created_at)
                    VALUES ($1, $2, $3, $4::uuid, $5::jsonb, $6)
                    """,
                    user_id,
                    action,
                    resource_type,
                    resource_id,
                    details or {},
                    now,
                )
            logger.debug("Telemetry tracked: %s/%s for %s", action, resource_type, user_id)
        except Exception as e:
            logger.error("Failed to track telemetry (%s/%s): %s", action, resource_type, e)

    @staticmethod
    async def get_for_resource(
        resource_type: str,
        resource_id: str,
        limit: int = 50,
        conn=None,
    ) -> list[dict]:
        """Get activity timeline for a specific resource (tenant DB)."""
        try:
            c = conn or get_current_conn()
            rows = await c.fetch(
                """
                SELECT id, user_id, action, resource_type, resource_id, details, created_at
                FROM activity_log
                WHERE resource_type = $1 AND resource_id = $2::uuid
                ORDER BY created_at DESC
                LIMIT $3
                """,
                resource_type,
                resource_id,
                limit,
            )
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error("Failed to get activity for %s/%s: %s", resource_type, resource_id, e)
            return []

    @staticmethod
    async def get_for_user(
        user_id: str,
        limit: int = 50,
        conn=None,
    ) -> list[dict]:
        """Get recent activity for a user (tenant DB)."""
        try:
            c = conn or get_current_conn()
            rows = await c.fetch(
                """
                SELECT id, user_id, action, resource_type, resource_id, details, created_at
                FROM activity_log
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                user_id,
                limit,
            )
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error("Failed to get activity for user %s: %s", user_id, e)
            return []
