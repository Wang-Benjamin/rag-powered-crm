"""
Tenant-aware asyncpg connection pool manager.

Maintains one asyncpg pool per tenant database with LRU eviction
to cap total connections across all tenants.
"""

import os
import asyncio
import logging
from urllib.parse import quote_plus
import time
from typing import Dict, Optional, Any, Tuple
from contextlib import asynccontextmanager

import json
import asyncpg

logger = logging.getLogger(__name__)


async def _init_connection(conn: asyncpg.Connection):
    """Initialize each new connection with JSONB codec so JSONB columns return Python objects."""
    await conn.set_type_codec(
        'jsonb', encoder=json.dumps, decoder=json.loads, schema='pg_catalog',
    )

DEFAULT_MAX_ACTIVE_POOLS = 200
DEFAULT_POOL_MIN_SIZE = 0
DEFAULT_POOL_MAX_SIZE = 2
DEFAULT_IDLE_LIFETIME = 300.0
DEFAULT_COMMAND_TIMEOUT = 60.0


class TenantPoolManager:
    """
    Manages per-tenant asyncpg connection pools with LRU eviction.

    Each tenant database gets its own asyncpg pool. When the number of
    active pools exceeds the cap, the least-recently-used pool is closed.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        max_active_pools: int = DEFAULT_MAX_ACTIVE_POOLS,
        pool_min_size: int = DEFAULT_POOL_MIN_SIZE,
        pool_max_size: int = DEFAULT_POOL_MAX_SIZE,
        max_inactive_connection_lifetime: float = DEFAULT_IDLE_LIFETIME,
        command_timeout: float = DEFAULT_COMMAND_TIMEOUT,
    ):
        self._host = host or os.getenv("SESSIONS_DB_HOST")
        self._port = port or int(os.getenv("SESSIONS_DB_PORT", "5432"))
        self._user = user or os.getenv("SESSIONS_DB_USER")
        self._password = password or os.getenv("SESSIONS_DB_PASSWORD")

        self._max_active_pools = max_active_pools
        self._pool_min_size = pool_min_size
        self._pool_max_size = pool_max_size
        self._max_inactive_conn_lifetime = max_inactive_connection_lifetime
        self._command_timeout = command_timeout

        # {db_name: (pool, last_access_time)}
        self._pools: Dict[str, Tuple[asyncpg.Pool, float]] = {}
        self._lock = asyncio.Lock()

        # Dedicated pool for prelude_user_analytics (fallback JWT lookups)
        self._analytics_pool: Optional[asyncpg.Pool] = None

    async def _create_pool(self, db_name: str) -> asyncpg.Pool:
        """Create an asyncpg pool for a specific tenant database."""
        dsn = f"postgresql://{quote_plus(self._user)}:{quote_plus(self._password)}@{self._host}:{self._port}/{db_name}"
        pool = await asyncpg.create_pool(
            dsn,
            min_size=self._pool_min_size,
            max_size=self._pool_max_size,
            max_inactive_connection_lifetime=self._max_inactive_conn_lifetime,
            command_timeout=self._command_timeout,
            init=_init_connection,
        )
        logger.info(f"Created pool for tenant DB: {db_name} (min={self._pool_min_size}, max={self._pool_max_size})")
        return pool

    async def _evict_lru(self):
        """Evict the least-recently-used pool if at capacity. Must be called under lock."""
        if len(self._pools) < self._max_active_pools:
            return

        oldest_db = min(self._pools, key=lambda k: self._pools[k][1])
        pool, last_access = self._pools.pop(oldest_db)
        idle_seconds = time.monotonic() - last_access
        try:
            await pool.close()
            logger.info(f"Evicted LRU pool: {oldest_db} (idle {idle_seconds:.0f}s)")
        except Exception as e:
            logger.warning(f"Error closing evicted pool {oldest_db}: {e}")

    async def get_pool(self, db_name: str) -> asyncpg.Pool:
        """Get or create a pool for the given tenant database."""
        async with self._lock:
            entry = self._pools.get(db_name)
            if entry is not None:
                pool, _ = entry
                self._pools[db_name] = (pool, time.monotonic())
                return pool

            await self._evict_lru()
            pool = await self._create_pool(db_name)
            self._pools[db_name] = (pool, time.monotonic())
            return pool

    @asynccontextmanager
    async def acquire(self, db_name: str):
        """
        Acquire a connection from the tenant's pool.

        Uses optimistic acquire with one retry on connection error.
        """
        pool = await self.get_pool(db_name)
        try:
            async with pool.acquire() as conn:
                yield conn
        except (asyncpg.InterfaceError, asyncpg.ConnectionDoesNotExistError, OSError) as e:
            logger.warning(f"Connection error for {db_name}, retrying: {e}")
            async with pool.acquire() as conn:
                yield conn

    async def get_analytics_pool(self) -> asyncpg.Pool:
        """Get the dedicated pool for prelude_user_analytics."""
        if self._analytics_pool is None or self._analytics_pool._closed:
            dsn = (
                f"postgresql://{quote_plus(self._user)}:{quote_plus(self._password)}"
                f"@{self._host}:{self._port}/prelude_user_analytics"
            )
            self._analytics_pool = await asyncpg.create_pool(
                dsn,
                min_size=1,
                max_size=3,
                max_inactive_connection_lifetime=self._max_inactive_conn_lifetime,
                command_timeout=self._command_timeout,
                init=_init_connection,
            )
            logger.info("Created analytics pool for prelude_user_analytics")
        return self._analytics_pool

    async def lookup_db_name(self, email: str) -> str:
        """Fallback: look up db_name from user_profiles for JWTs without db_name claim."""
        pool = await self.get_analytics_pool()
        try:
            row = await pool.fetchrow(
                "SELECT db_name FROM user_profiles WHERE email = $1 LIMIT 1",
                email,
            )
            if row and row["db_name"]:
                return row["db_name"]
        except Exception as e:
            logger.error(f"Failed to look up db_name for {email}: {e}")
            raise ValueError(f"Cannot resolve tenant database for {email}") from e
        raise ValueError(f"No user_profile found for {email}, cannot resolve tenant database")

    async def close_all(self):
        """Close all tenant pools and the analytics pool."""
        async with self._lock:
            for db_name, (pool, _) in self._pools.items():
                try:
                    await pool.close()
                except Exception as e:
                    logger.warning(f"Error closing pool {db_name}: {e}")
            self._pools.clear()
            logger.info("All tenant pools closed")

        if self._analytics_pool and not self._analytics_pool._closed:
            try:
                await self._analytics_pool.close()
                logger.info("Analytics pool closed")
            except Exception as e:
                logger.warning(f"Error closing analytics pool: {e}")
            self._analytics_pool = None

    def get_stats(self) -> Dict[str, Any]:
        """Return pool statistics for monitoring."""
        stats = {
            "active_pools": len(self._pools),
            "max_active_pools": self._max_active_pools,
            "pools": {},
        }
        for db_name, (pool, last_access) in self._pools.items():
            stats["pools"][db_name] = {
                "size": pool.get_size(),
                "free_size": pool.get_idle_size(),
                "min_size": pool.get_min_size(),
                "max_size": pool.get_max_size(),
                "idle_seconds": round(time.monotonic() - last_access, 1),
            }
        return stats

    async def health_check(self) -> bool:
        """Verify the manager can connect to the analytics database."""
        try:
            pool = await self.get_analytics_pool()
            val = await pool.fetchval("SELECT 1")
            return val == 1
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
