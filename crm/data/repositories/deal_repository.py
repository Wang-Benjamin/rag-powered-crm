"""Deal repository for CRM - handles deal database operations."""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

import asyncpg

from data.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class DealRepository(BaseRepository):
    """Repository for deal database operations."""

    def __init__(self):
        super().__init__('deals')

    async def find_by_id(self, conn: asyncpg.Connection, deal_id: int) -> Optional[Dict[str, Any]]:
        """
        Find deal by ID with full details.

        Args:
            conn: asyncpg connection
            deal_id: Deal ID

        Returns:
            Deal dictionary or None
        """
        query = """
            SELECT
                d.deal_id,
                d.client_id,
                d.deal_name,
                d.value_usd,
                d.room_status,
                d.expected_close_date,
                d.created_at,
                d.updated_at,
                d.employee_id,
                d.description,
                c.name as client_name,
                e.name as employee_name
            FROM deals d
            LEFT JOIN clients c ON d.client_id = c.client_id
            LEFT JOIN employee_info e ON d.employee_id = e.employee_id
            WHERE d.deal_id = $1
        """
        return await self._execute_query_one(conn, query, deal_id)

    async def find_by_customer(self, conn: asyncpg.Connection, customer_id: int) -> List[Dict[str, Any]]:
        """
        Find all deals for a customer.

        Args:
            conn: asyncpg connection
            customer_id: Customer ID

        Returns:
            List of deal dictionaries
        """
        query = """
            SELECT
                d.deal_id,
                d.client_id,
                d.deal_name,
                d.value_usd,
                d.room_status,
                d.expected_close_date,
                d.created_at,
                d.updated_at,
                d.employee_id,
                d.description,
                e.name as employee_name
            FROM deals d
            LEFT JOIN employee_info e ON d.employee_id = e.employee_id
            WHERE d.client_id = $1
            ORDER BY d.created_at DESC
        """
        return await self._execute_query(conn, query, customer_id)

    async def find_active_deals(self, conn: asyncpg.Connection, customer_id: int) -> List[Dict[str, Any]]:
        """
        Find active deals for a customer (not closed-won or closed-lost).

        Args:
            conn: asyncpg connection
            customer_id: Customer ID

        Returns:
            List of active deal dictionaries
        """
        query = """
            SELECT
                d.deal_id,
                d.client_id,
                d.deal_name,
                d.value_usd,
                d.room_status,
                d.expected_close_date,
                d.created_at,
                d.updated_at,
                d.employee_id,
                d.description
            FROM deals d
            WHERE d.client_id = $1
              AND d.room_status NOT IN ('closed-won', 'closed-lost')
            ORDER BY d.created_at DESC
        """
        return await self._execute_query(conn, query, customer_id)

    async def create_deal(self, conn: asyncpg.Connection, deal_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create a new deal.

        Args:
            conn: asyncpg connection
            deal_data: Dictionary with deal data

        Returns:
            Created deal dictionary or None
        """
        query = """
            INSERT INTO deals (
                client_id, deal_name, value_usd, room_status,
                expected_close_date, employee_id, description, created_at, updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9
            )
            RETURNING *
        """
        return await self._execute_write(
            conn, query,
            deal_data['client_id'],
            deal_data['deal_name'],
            deal_data.get('value_usd', 0.0),
            deal_data.get('room_status', 'draft'),
            deal_data['expected_close_date'],
            deal_data['employee_id'],
            deal_data.get('description'),
            deal_data['created_at'],
            deal_data['updated_at'],
        )

    async def update_deal(self, conn: asyncpg.Connection, deal_id: int, deal_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update an existing deal.

        Args:
            conn: asyncpg connection
            deal_id: Deal ID
            deal_data: Dictionary with deal data to update

        Returns:
            Updated deal dictionary or None
        """
        set_clauses = []
        params = []
        param_idx = 1

        for key, value in deal_data.items():
            if key != 'deal_id':
                set_clauses.append(f"{key} = ${param_idx}")
                params.append(value)
                param_idx += 1

        if not set_clauses:
            return None

        # Always update updated_at
        set_clauses.append(f"updated_at = ${param_idx}")
        params.append(datetime.now(timezone.utc))
        param_idx += 1

        # Add deal_id to params
        params.append(deal_id)

        query = f"""
            UPDATE deals
            SET {', '.join(set_clauses)}
            WHERE deal_id = ${param_idx}
            RETURNING *
        """

        return await self._execute_write(conn, query, *params)

    async def delete_deal(self, conn: asyncpg.Connection, deal_id: int) -> bool:
        """
        Delete a deal.

        Args:
            conn: asyncpg connection
            deal_id: Deal ID

        Returns:
            True if successful
        """
        query = "DELETE FROM deals WHERE deal_id = $1 RETURNING deal_id"
        result = await self._execute_write(conn, query, deal_id)
        return result is not None

    async def update_room_status(self, conn: asyncpg.Connection, deal_id: int, new_status: str) -> Optional[Dict[str, Any]]:
        """
        Update deal room_status.

        Args:
            conn: asyncpg connection
            deal_id: Deal ID
            new_status: New room_status value

        Returns:
            Updated deal dictionary or None
        """
        query = """
            UPDATE deals
            SET room_status = $1,
                updated_at = $2
            WHERE deal_id = $3
            RETURNING *
        """
        now = datetime.now(timezone.utc)
        return await self._execute_write(conn, query, new_status, now, deal_id)
