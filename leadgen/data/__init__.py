"""
Data layer for Lead Generation Service (asyncpg).

Provides async database connection helpers and repository patterns.
"""

from .connection import (
    execute_query,
    get_tenant_conn,
    get_analytics_conn,
    lookup_db_name,
)

from .repositories import (
    BaseRepository,
    QueryResult,
    SQLBuilder,
    JSONFieldMixin,
    LeadRepository,
    PersonnelRepository,
)

__all__ = [
    # Connection helpers
    'execute_query',
    'get_tenant_conn',
    'get_analytics_conn',
    'lookup_db_name',

    # Repository patterns
    'BaseRepository',
    'QueryResult',
    'SQLBuilder',
    'JSONFieldMixin',

    # Feature repositories
    'LeadRepository',
    'PersonnelRepository',
]
