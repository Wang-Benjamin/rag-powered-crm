"""Customer repository for CRM - handles customer database operations."""

import logging
from typing import Optional, Dict, Any, List

import asyncpg

from data.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class CustomerRepository(BaseRepository):
    """Repository for customer database operations."""

    def __init__(self):
        super().__init__('clients')

    async def find_by_id(self, conn: asyncpg.Connection, customer_id: int) -> Optional[Dict[str, Any]]:
        """
        Find customer by ID with full details.

        Args:
            conn: asyncpg connection
            customer_id: Customer ID

        Returns:
            Customer dictionary with details or None
        """
        query = """
            SELECT
                ci.client_id,
                ci.name,
                ci.phone,
                ci.location,
                ci.website,
                ci.preferred_language,
                ci.source,
                ci.notes,
                ci.created_at,
                ci.updated_at,
                ci.status,
                COALESCE((SELECT SUM(value_usd) FROM deals WHERE client_id = ci.client_id), 0) as total_deal_value,
                ci.health_score,
                ci.stage,
                ci.signal,
                ci.trade_intel,
                ecl.employee_id as assigned_employee_id,
                ei.name as assigned_employee_name,
                (
                    SELECT MAX(ts) FROM (
                        SELECT MAX(id2.created_at) AS ts FROM interaction_details id2 WHERE id2.customer_id = ci.client_id
                        UNION ALL
                        SELECT MAX(ce.created_at) AS ts FROM crm_emails ce WHERE ce.customer_id = ci.client_id
                    ) sub
                ) AS last_activity
            FROM clients ci
            LEFT JOIN employee_client_links ecl ON ci.client_id = ecl.client_id
            LEFT JOIN employee_info ei ON ecl.employee_id = ei.employee_id
            WHERE ci.client_id = $1
        """
        return await self._execute_query_one(conn, query, customer_id)

    async def find_all_with_details(self, conn: asyncpg.Connection, filters: Dict[str, Any] = None,
                                    page: int = None, per_page: int = None):
        """
        Find all customers with details and optional filtering.

        Args:
            conn: asyncpg connection
            filters: Optional filters (search, status)
            page: Page number (1-based). If None, returns all rows.
            per_page: Items per page. If None, returns all rows.

        Returns:
            List of customer dictionaries, or (list, total) tuple when paginated
        """
        query = """
            SELECT
                ci.client_id,
                ci.name,
                ci.phone,
                ci.location,
                ci.website,
                ci.preferred_language,
                ci.source,
                ci.status,
                ci.notes,
                ci.created_at,
                ci.updated_at,
                COALESCE((SELECT SUM(value_usd) FROM deals WHERE client_id = ci.client_id), 0) as total_deal_value,
                ci.health_score,
                ci.stage,
                ci.signal,
                ecl.employee_id as assigned_employee_id,
                ei.name as assigned_employee_name,
                (
                    SELECT MAX(ts) FROM (
                        SELECT MAX(id2.created_at) AS ts FROM interaction_details id2 WHERE id2.customer_id = ci.client_id
                        UNION ALL
                        SELECT MAX(ce.created_at) AS ts FROM crm_emails ce WHERE ce.customer_id = ci.client_id
                    ) sub
                ) AS last_activity
            FROM clients ci
            LEFT JOIN LATERAL (
                SELECT employee_id
                FROM employee_client_links
                WHERE client_id = ci.client_id AND status = 'active'
                LIMIT 1
            ) ecl ON true
            LEFT JOIN employee_info ei ON ecl.employee_id = ei.employee_id
        """

        where_clauses = []
        params = []
        param_idx = 1

        if filters:
            if filters.get('search'):
                where_clauses.append(f"(ci.name ILIKE ${param_idx})")
                search_term = f"%{filters['search']}%"
                params.append(search_term)
                param_idx += 1

            if filters.get('status'):
                where_clauses.append(f"ci.status = ${param_idx}")
                params.append(filters['status'])
                param_idx += 1

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        query += " ORDER BY ci.created_at DESC"

        if page is not None and per_page is not None:
            return await self._execute_query_paginated(
                conn, query, params if params else None, page, per_page
            )

        return await self._execute_query(conn, query, *params)

    async def find_by_employee(self, conn: asyncpg.Connection, employee_id: int, filters: Dict[str, Any] = None,
                               page: int = None, per_page: int = None):
        """
        Find customers assigned to a specific employee.

        Args:
            conn: asyncpg connection
            employee_id: Employee ID
            filters: Optional filters (search, status)
            page: Page number (1-based). If None, returns all rows.
            per_page: Items per page. If None, returns all rows.

        Returns:
            List of customer dictionaries, or (list, total) tuple when paginated
        """
        query = """
            SELECT
                ci.client_id,
                ci.name,
                ci.phone,
                ci.location,
                ci.website,
                ci.preferred_language,
                ci.source,
                ci.status,
                ci.notes,
                ci.created_at,
                ci.updated_at,
                COALESCE((SELECT SUM(value_usd) FROM deals WHERE client_id = ci.client_id), 0) as total_deal_value,
                ci.health_score,
                ci.stage,
                ci.signal,
                ecl.employee_id as assigned_employee_id,
                ei.name as assigned_employee_name,
                (
                    SELECT MAX(ts) FROM (
                        SELECT MAX(id2.created_at) AS ts FROM interaction_details id2 WHERE id2.customer_id = ci.client_id
                        UNION ALL
                        SELECT MAX(ce.created_at) AS ts FROM crm_emails ce WHERE ce.customer_id = ci.client_id
                    ) sub
                ) AS last_activity
            FROM clients ci
            INNER JOIN employee_client_links ecl ON ci.client_id = ecl.client_id
            LEFT JOIN employee_info ei ON ecl.employee_id = ei.employee_id
            WHERE ecl.employee_id = $1 AND ecl.status = 'active'
        """

        params = [employee_id]
        param_idx = 2

        if filters:
            if filters.get('search'):
                query += f" AND (ci.name ILIKE ${param_idx})"
                search_term = f"%{filters['search']}%"
                params.append(search_term)
                param_idx += 1

            if filters.get('status'):
                query += f" AND ci.status = ${param_idx}"
                params.append(filters['status'])
                param_idx += 1

        query += " ORDER BY ci.created_at DESC"

        if page is not None and per_page is not None:
            return await self._execute_query_paginated(
                conn, query, params, page, per_page
            )

        return await self._execute_query(conn, query, *params)

    async def get_dashboard_stats(self, conn: asyncpg.Connection) -> Optional[Dict[str, Any]]:
        """
        Get dashboard statistics.

        Args:
            conn: asyncpg connection

        Returns:
            Dictionary with dashboard statistics
        """
        query = """
            SELECT
                COUNT(ci.client_id) as total_customers,
                COUNT(CASE WHEN ci.status = 'active' THEN 1 END) as active_customers,
                COUNT(CASE WHEN ci.status = 'at-risk' THEN 1 END) as at_risk_customers,
                COALESCE((SELECT SUM(value_usd) FROM deals), 0) as total_deal_value,
                COALESCE(AVG(ci.health_score), 75) as avg_health_score,
                COUNT(CASE WHEN ci.created_at >= DATE_TRUNC('month', CURRENT_DATE) THEN 1 END) as new_customers_month,
                0 as expansion_opportunities
            FROM clients ci
        """
        return await self._execute_query_one(conn, query)

    async def create_customer(self, conn: asyncpg.Connection, customer_data: Dict[str, Any]) -> Optional[int]:
        """
        Create a new customer.

        Args:
            conn: asyncpg connection
            customer_data: Dictionary with customer data

        Returns:
            Created customer ID or None
        """
        # This will be implemented in the next phase
        pass

    async def update_customer(self, conn: asyncpg.Connection, customer_id: int, customer_data: Dict[str, Any]) -> bool:
        """
        Update an existing customer.

        Args:
            conn: asyncpg connection
            customer_id: Customer ID
            customer_data: Dictionary with customer data to update

        Returns:
            True if successful
        """
        # This will be implemented in the next phase
        pass

    async def delete_customer(self, conn: asyncpg.Connection, customer_id: int) -> bool:
        """
        Delete a customer.

        Args:
            conn: asyncpg connection
            customer_id: Customer ID

        Returns:
            True if successful
        """
        # This will be implemented in the next phase
        pass
