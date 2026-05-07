"""
Database connection management for Lead Generation Service (asyncpg).

Provides async query execution functions and context managers
using TenantPoolManager from service_core.
"""

import json
import logging
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from service_core.db import get_pool_manager

logger = logging.getLogger(__name__)


async def execute_query(
    conn,
    query: str,
    *params,
    fetch_one: bool = False,
    fetch_all: bool = False,
) -> Any:
    """
    Execute a query on an existing asyncpg connection.

    Args:
        conn: asyncpg connection
        query: SQL query with $1, $2 placeholders
        *params: positional parameters
        fetch_one: return single row
        fetch_all: return all rows

    Returns:
        Row(s) or status string from execute()
    """
    if fetch_one:
        return await conn.fetchrow(query, *params)
    elif fetch_all:
        return await conn.fetch(query, *params)
    else:
        return await conn.execute(query, *params)


@asynccontextmanager
async def get_tenant_conn(db_name: str):
    """
    Acquire a connection from the tenant pool for a specific database.
    Use this in background tasks / Temporal workers that don't have
    a request-scoped connection.
    """
    pm = get_pool_manager()
    async with pm.acquire(db_name) as conn:
        yield conn


@asynccontextmanager
async def get_analytics_conn():
    """Acquire a connection from the analytics pool."""
    pm = get_pool_manager()
    pool = await pm.get_analytics_pool()
    async with pool.acquire() as conn:
        yield conn


async def lookup_db_name(user_email: str) -> str:
    """Look up the tenant database name for a user email."""
    pm = get_pool_manager()
    return await pm.lookup_db_name(user_email)
