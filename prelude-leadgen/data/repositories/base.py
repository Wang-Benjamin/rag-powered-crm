"""
Base repository and SQL utilities for Lead Generation Service (asyncpg).

All methods are async and take an asyncpg connection as parameter.
Uses $1, $2, ... positional placeholders (asyncpg).
"""

import json
import logging
import uuid as _uuid_mod
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any, Tuple, Union
from dataclasses import dataclass

from config.constants import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    get_message
)

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """Standardized query result container."""
    data: Any
    total_count: Optional[int] = None
    page: Optional[int] = None
    page_size: Optional[int] = None
    success: bool = True
    message: str = ""
    error: Optional[str] = None


class SQLBuilder:
    """Utility class for building dynamic SQL queries with $N placeholders."""

    @staticmethod
    def build_where_clause(
        conditions: Dict[str, Any],
        operator: str = "AND",
        start_idx: int = 1
    ) -> Tuple[str, list, int]:
        """
        Build a WHERE clause from conditions dictionary.

        Args:
            conditions: Dictionary of field_name: value pairs
            operator: SQL operator to join conditions (AND/OR)
            start_idx: Starting parameter index ($N)

        Returns:
            Tuple of (where_clause, params_list, next_idx)
        """
        if not conditions:
            return "", [], start_idx

        where_parts = []
        params = []
        idx = start_idx

        for field, value in conditions.items():
            if value is None:
                continue

            if "__" in field:
                field_name, op = field.split("__", 1)
                if op == "ilike":
                    where_parts.append(f"{field_name} ILIKE ${idx}")
                    params.append(f"%{value}%")
                    idx += 1
                elif op == "like":
                    where_parts.append(f"{field_name} LIKE ${idx}")
                    params.append(f"%{value}%")
                    idx += 1
                elif op == "gte":
                    where_parts.append(f"{field_name} >= ${idx}")
                    params.append(value)
                    idx += 1
                elif op == "lte":
                    where_parts.append(f"{field_name} <= ${idx}")
                    params.append(value)
                    idx += 1
                elif op == "gt":
                    where_parts.append(f"{field_name} > ${idx}")
                    params.append(value)
                    idx += 1
                elif op == "lt":
                    where_parts.append(f"{field_name} < ${idx}")
                    params.append(value)
                    idx += 1
                elif op == "ne":
                    where_parts.append(f"{field_name} != ${idx}")
                    params.append(value)
                    idx += 1
                elif op == "in":
                    if isinstance(value, (list, tuple)) and value:
                        where_parts.append(f"{field_name} = ANY(${idx})")
                        params.append(value)
                        idx += 1
                elif op == "is_null":
                    if value:
                        where_parts.append(f"{field_name} IS NULL")
                    else:
                        where_parts.append(f"{field_name} IS NOT NULL")
            else:
                where_parts.append(f"{field} = ${idx}")
                params.append(value)
                idx += 1

        if where_parts:
            where_clause = f" WHERE {f' {operator} '.join(where_parts)}"
            return where_clause, params, idx

        return "", [], idx

    @staticmethod
    def build_order_clause(
        order_by: Optional[Union[str, List[str]]],
        default_order: str = "created_at DESC"
    ) -> str:
        if not order_by:
            return f" ORDER BY {default_order}"
        if isinstance(order_by, str):
            return f" ORDER BY {order_by}"
        if isinstance(order_by, list):
            return f" ORDER BY {', '.join(order_by)}"
        return f" ORDER BY {default_order}"

    @staticmethod
    def build_limit_offset(
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        start_idx: int = 1
    ) -> Tuple[str, list, int]:
        """
        Build LIMIT and OFFSET clause.

        Returns:
            Tuple of (limit_clause, params_list, next_idx)
        """
        if page_size is None:
            page_size = DEFAULT_PAGE_SIZE
        else:
            page_size = min(max(1, page_size), MAX_PAGE_SIZE)

        if page is None or page < 1:
            page = 1

        offset = (page - 1) * page_size

        limit_clause = f" LIMIT ${start_idx} OFFSET ${start_idx + 1}"
        return limit_clause, [page_size, offset], start_idx + 2


class BaseRepository(ABC):
    """
    Abstract base repository (asyncpg).

    All methods take an asyncpg connection as first parameter.
    """

    def __init__(self, table_name: str, primary_key: str = "id"):
        self.table_name = table_name
        self.primary_key = primary_key
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")

    @staticmethod
    def _row_to_dict(row) -> dict:
        """Convert asyncpg Record to dict, stringifying UUID values for Pydantic."""
        return {k: str(v) if isinstance(v, _uuid_mod.UUID) else v for k, v in dict(row).items()}

    async def create(self, conn, data: Dict[str, Any], user_id: str = "system") -> Optional[str]:
        """Create a new record."""
        try:
            data["created_at"] = datetime.now(timezone.utc)
            data["updated_at"] = datetime.now(timezone.utc)

            if self.primary_key not in data:
                data[self.primary_key] = str(_uuid_mod.uuid4())

            fields = list(data.keys())
            placeholders = [f"${i+1}" for i in range(len(fields))]
            values = list(data.values())

            query = f"""
                INSERT INTO {self.table_name} ({', '.join(fields)})
                VALUES ({', '.join(placeholders)})
                RETURNING {self.primary_key}
            """

            result = await conn.fetchrow(query, *values)

            if result:
                record_id = str(result[self.primary_key])
                self.logger.info(f"Created {self.table_name} record: {record_id}")
                return record_id

            return None

        except Exception as e:
            self.logger.error(f"Error creating {self.table_name} record: {e}")
            return None

    async def get_by_id(self, conn, record_id: str) -> Optional[Dict[str, Any]]:
        """Get a record by its ID."""
        try:
            query = f"SELECT * FROM {self.table_name} WHERE {self.primary_key} = $1"
            result = await conn.fetchrow(query, record_id)
            return self._row_to_dict(result) if result else None
        except Exception as e:
            self.logger.error(f"Error getting {self.table_name} record {record_id}: {e}")
            return None

    async def update(self, conn, record_id: str, data: Dict[str, Any], user_id: str = "system") -> bool:
        """Update a record."""
        try:
            if not data:
                return True

            data["updated_at"] = datetime.now(timezone.utc)

            set_parts = []
            params = []
            idx = 1

            for field, value in data.items():
                if isinstance(value, (dict, list)):
                    set_parts.append(f"{field} = ${idx}")
                    params.append(json.dumps(value))
                else:
                    set_parts.append(f"{field} = ${idx}")
                    params.append(value)
                idx += 1

            params.append(record_id)

            query = f"""
                UPDATE {self.table_name}
                SET {', '.join(set_parts)}
                WHERE {self.primary_key} = ${idx}
                RETURNING {self.primary_key}
            """

            result = await conn.fetchrow(query, *params)

            if result:
                self.logger.info(f"Updated {self.table_name} record: {record_id}")
                return True

            return False

        except Exception as e:
            self.logger.error(f"Error updating {self.table_name} record {record_id}: {e}")
            return False

    async def delete(self, conn, record_id: str, user_id: str = "system") -> bool:
        """Delete a record."""
        try:
            query = f"DELETE FROM {self.table_name} WHERE {self.primary_key} = $1"
            result = await conn.execute(query, record_id)
            deleted = result and not result.endswith(' 0')

            if deleted:
                self.logger.info(f"Deleted {self.table_name} record: {record_id}")
            return deleted

        except Exception as e:
            self.logger.error(f"Error deleting {self.table_name} record {record_id}: {e}")
            return False

    async def list_all(
        self,
        conn,
        conditions: Optional[Dict[str, Any]] = None,
        order_by: Optional[Union[str, List[str]]] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None
    ) -> QueryResult:
        """List records with optional filtering and pagination."""
        try:
            where_clause, where_params, next_idx = SQLBuilder.build_where_clause(conditions or {})
            order_clause = SQLBuilder.build_order_clause(order_by)
            limit_clause, limit_params, _ = SQLBuilder.build_limit_offset(page, page_size, next_idx)

            query = f"SELECT * FROM {self.table_name}{where_clause}{order_clause}{limit_clause}"
            params = where_params + limit_params

            results = await conn.fetch(query, *params)

            total_count = None
            if page is not None:
                count_query = f"SELECT COUNT(*) as count FROM {self.table_name}{where_clause}"
                count_result = await conn.fetchrow(count_query, *where_params)
                total_count = count_result["count"] if count_result else 0

            data = [self._row_to_dict(row) for row in results] if results else []

            return QueryResult(
                data=data,
                total_count=total_count,
                page=page,
                page_size=page_size or DEFAULT_PAGE_SIZE,
                success=True,
                message=get_message("success")
            )

        except Exception as e:
            self.logger.error(f"Error listing {self.table_name} records: {e}")
            return QueryResult(
                data=[], success=False, error=str(e),
                message=get_message("internal_error")
            )

    async def count(self, conn, conditions: Optional[Dict[str, Any]] = None) -> int:
        """Count records matching conditions."""
        try:
            where_clause, params, _ = SQLBuilder.build_where_clause(conditions or {})
            query = f"SELECT COUNT(*) as count FROM {self.table_name}{where_clause}"
            result = await conn.fetchrow(query, *params)
            return result["count"] if result else 0
        except Exception as e:
            self.logger.error(f"Error counting {self.table_name} records: {e}")
            return 0

    async def exists(self, conn, record_id: str) -> bool:
        """Check if a record exists."""
        try:
            query = f"SELECT 1 FROM {self.table_name} WHERE {self.primary_key} = $1"
            result = await conn.fetchrow(query, record_id)
            return result is not None
        except Exception as e:
            self.logger.error(f"Error checking existence of {self.table_name} record {record_id}: {e}")
            return False

    async def bulk_create(self, conn, records: List[Dict[str, Any]], user_id: str = "system") -> int:
        """Create multiple records in a single transaction."""
        if not records:
            return 0

        try:
            created_count = 0
            async with conn.transaction():
                for data in records:
                    data["created_at"] = datetime.now(timezone.utc)
                    data["updated_at"] = datetime.now(timezone.utc)

                    if self.primary_key not in data:
                        data[self.primary_key] = str(_uuid_mod.uuid4())

                    fields = list(data.keys())
                    placeholders = [f"${i+1}" for i in range(len(fields))]
                    values = list(data.values())

                    query = f"""
                        INSERT INTO {self.table_name} ({', '.join(fields)})
                        VALUES ({', '.join(placeholders)})
                    """
                    await conn.execute(query, *values)
                    created_count += 1

            self.logger.info(f"Bulk created {created_count} {self.table_name} records")
            return created_count

        except Exception as e:
            self.logger.error(f"Error bulk creating {self.table_name} records: {e}")
            return 0

    @abstractmethod
    async def search(self, conn, **kwargs) -> QueryResult:
        """Search method that subclasses must implement."""
        pass


class JSONFieldMixin:
    """Mixin for handling JSON fields in repositories."""

    @staticmethod
    def safe_json_parse(value: Any, default: Any = None) -> Any:
        if value is None:
            return default
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, ValueError):
                return default
        return default

    @staticmethod
    def prepare_json_field(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            try:
                json.loads(value)
                return value
            except (json.JSONDecodeError, ValueError):
                tag_list = [tag.strip() for tag in value.split(',') if tag.strip()]
                return json.dumps(tag_list)
        try:
            return json.dumps(value)
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to serialize value to JSON: {e}")
            return "[]"
