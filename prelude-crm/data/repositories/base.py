"""Base repository pattern for CRM data access layer."""

import logging
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)


class BaseRepository:
    """
    Base repository with common database operations.
    Provides standard CRUD operations using asyncpg connections.
    """

    def __init__(self, table_name: str):
        """
        Initialize repository with table name.

        Args:
            table_name: Name of the database table this repository manages
        """
        self.table_name = table_name

    async def _execute_query(self, conn: asyncpg.Connection, query: str, *params) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return results as list of dictionaries.

        Args:
            conn: asyncpg connection
            query: SQL query to execute
            params: Query parameters

        Returns:
            List of result dictionaries
        """
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]

    async def _execute_query_one(self, conn: asyncpg.Connection, query: str, *params) -> Optional[Dict[str, Any]]:
        """
        Execute a SELECT query and return single result as dictionary.

        Args:
            conn: asyncpg connection
            query: SQL query to execute
            params: Query parameters

        Returns:
            Result dictionary or None
        """
        row = await conn.fetchrow(query, *params)
        return dict(row) if row else None

    async def _execute_write(self, conn: asyncpg.Connection, query: str, *params) -> Optional[Dict[str, Any]]:
        """
        Execute an INSERT/UPDATE/DELETE query with optional RETURNING clause.

        Args:
            conn: asyncpg connection
            query: SQL query to execute
            params: Query parameters

        Returns:
            Result dictionary from RETURNING clause or None
        """
        row = await conn.fetchrow(query, *params)
        return dict(row) if row else None

    async def _execute_query_paginated(
        self, conn: asyncpg.Connection, query: str, params: list = None,
        page: int = 1, per_page: int = 10
    ) -> tuple:
        """
        Execute a SELECT query with pagination using COUNT(*) OVER().

        Args:
            conn: asyncpg connection
            query: SQL query to execute
            params: Query parameters as a list
            page: Page number (1-based)
            per_page: Items per page

        Returns:
            (rows, total_count) tuple
        """
        offset = (page - 1) * per_page
        param_count = len(params) if params else 0
        paginated_query = f"""
            SELECT *, COUNT(*) OVER() AS _total_count
            FROM ({query}) _paginated_sub
            LIMIT ${param_count + 1} OFFSET ${param_count + 2}
        """
        combined_params = list(params or []) + [per_page, offset]

        rows = await conn.fetch(paginated_query, *combined_params)

        if rows:
            results = [dict(row) for row in rows]
            total = results[0].pop('_total_count', 0)
            for row in results[1:]:
                row.pop('_total_count', None)
            return results, total
        return [], 0

    async def find_by_id(self, conn: asyncpg.Connection, entity_id: int, id_column: str = 'id') -> Optional[Dict[str, Any]]:
        """
        Find an entity by ID.

        Args:
            conn: asyncpg connection
            entity_id: Entity ID to find
            id_column: Name of the ID column (default: 'id')

        Returns:
            Entity dictionary or None
        """
        query = f"SELECT * FROM {self.table_name} WHERE {id_column} = $1"
        return await self._execute_query_one(conn, query, entity_id)

    async def find_all(self, conn: asyncpg.Connection, limit: int = None, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Find all entities with optional pagination.

        Args:
            conn: asyncpg connection
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of entity dictionaries
        """
        query = f"SELECT * FROM {self.table_name}"
        if limit:
            query += f" LIMIT {limit} OFFSET {offset}"

        return await self._execute_query(conn, query)

    async def count(self, conn: asyncpg.Connection) -> int:
        """
        Count total entities.

        Args:
            conn: asyncpg connection

        Returns:
            Total count
        """
        query = f"SELECT COUNT(*) as count FROM {self.table_name}"
        result = await self._execute_query_one(conn, query)
        return result['count'] if result else 0
