"""
FastAPI dependencies for tenant-scoped database connections.

Combines auth (JWT) with the TenantPoolManager to provide
an asyncpg connection scoped to the authenticated user's database.

Uses contextvars to make the request-scoped connection available
anywhere in the call stack without explicit parameter passing.
"""

import logging
import re
from contextvars import ContextVar
from typing import AsyncGenerator, Tuple, Optional

import asyncpg
from fastapi import Depends, HTTPException

from service_core.auth import verify_auth_token
from service_core.pool import TenantPoolManager

logger = logging.getLogger(__name__)

import threading

# Thread-local pool manager — each thread (FastAPI main, Temporal worker) gets its own.
# This prevents the worker thread from overwriting the FastAPI pool manager.
_thread_local = threading.local()

# Request-scoped connection available anywhere in the call stack.
# Set by get_tenant_connection, read by get_current_conn().
_current_conn: ContextVar[Optional[asyncpg.Connection]] = ContextVar("_current_conn", default=None)
_current_user: ContextVar[Optional[dict]] = ContextVar("_current_user", default=None)


def init_pool_manager(manager: TenantPoolManager):
    """Set the pool manager for the current thread. Called at startup and by Temporal workers."""
    _thread_local.pool_manager = manager


def get_pool_manager() -> TenantPoolManager:
    """Get the pool manager for the current thread."""
    pm = getattr(_thread_local, 'pool_manager', None)
    if pm is None:
        raise RuntimeError("TenantPoolManager not initialized. Call init_pool_manager() in lifespan.")
    return pm


def get_current_conn() -> asyncpg.Connection:
    """
    Get the current request's tenant DB connection from context.

    Use this in cross-cutting infrastructure (OAuthTokenManager, etc.)
    that needs DB access without receiving conn as a parameter.
    Avoids pool deadlocks — reuses the connection already acquired for this request.
    """
    conn = _current_conn.get()
    if conn is None:
        raise RuntimeError("No tenant connection in context. Must be called within a request handled by get_tenant_connection.")
    return conn


def get_current_user() -> dict:
    """Get the current request's authenticated user claims from context."""
    user = _current_user.get()
    if user is None:
        raise RuntimeError("No user in context. Must be called within a request handled by get_tenant_connection.")
    return user


async def get_tenant_connection(
    user: dict = Depends(verify_auth_token),
) -> AsyncGenerator[Tuple[asyncpg.Connection, dict], None]:
    """
    FastAPI dependency that yields (conn, user_claims) for the
    authenticated user's tenant database.

    Also sets contextvars so cross-cutting services (OAuthTokenManager, etc.)
    can access the connection via get_current_conn() without prop-drilling.
    """
    pm = get_pool_manager()

    db_name = user.get("db_name")

    if not db_name:
        email = user.get("email", "")
        logger.warning(f"JWT missing db_name for {email}, falling back to DB lookup")
        db_name = await pm.lookup_db_name(email)

    # Validate db_name to prevent access to system databases
    if not re.match(r'^(postgres|prelude_[a-z0-9_]+)$', db_name):
        logger.warning(f"Rejected invalid db_name: {db_name}")
        raise HTTPException(status_code=403, detail="Access denied")

    async with pm.acquire(db_name) as conn:
        conn_token = _current_conn.set(conn)
        user_token = _current_user.set(user)
        try:
            yield conn, user
        finally:
            _current_conn.reset(conn_token)
            _current_user.reset(user_token)
