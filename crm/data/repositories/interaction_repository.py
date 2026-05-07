"""Interaction repository for CRM - handles interaction database operations."""

import logging
import asyncpg
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone

from data.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class InteractionRepository(BaseRepository):
    """Repository for interaction database operations."""

    def __init__(self):
        super().__init__('interaction_details')

    async def find_by_customer_and_employee(self, conn: asyncpg.Connection, customer_id: int, employee_id: int) -> List[Dict[str, Any]]:
        """
        Get interactions for a specific customer and employee.

        Args:
            conn: asyncpg database connection
            customer_id: Customer ID
            employee_id: Employee ID

        Returns:
            List of interaction dictionaries
        """
        query = """
            SELECT
                i.interaction_id,
                i.customer_id,
                i.type,
                i.content,
                i.created_at,
                i.updated_at,
                i.gmail_message_id,
                i.theme,
                i.source,
                e.name as employee_name,
                e.role as employee_role,
                e.department as employee_department
            FROM interaction_details i
            LEFT JOIN employee_info e ON i.employee_id = e.employee_id
            WHERE i.customer_id = $1 AND i.employee_id = $2 AND i.type != 'quote_request'
            ORDER BY i.created_at DESC
        """
        return await self._execute_query(conn, query, customer_id, employee_id)

    async def find_by_customer(self, conn: asyncpg.Connection, customer_id: int) -> List[Dict[str, Any]]:
        """
        Get all interactions for a specific customer.

        Args:
            conn: asyncpg database connection
            customer_id: Customer ID

        Returns:
            List of interaction dictionaries
        """
        query = """
            SELECT
                i.interaction_id,
                i.customer_id,
                i.type,
                i.content,
                i.created_at,
                i.updated_at,
                i.gmail_message_id,
                i.theme,
                i.source,
                e.name as employee_name,
                e.role as employee_role,
                e.department as employee_department
            FROM interaction_details i
            LEFT JOIN employee_info e ON i.employee_id = e.employee_id
            WHERE i.customer_id = $1 AND i.type != 'quote_request'
            ORDER BY i.created_at DESC
        """
        return await self._execute_query(conn, query, customer_id)

    async def get_recent_interactions(self, conn: asyncpg.Connection, customer_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get recent interactions for a customer within specified days.

        Args:
            conn: asyncpg database connection
            customer_id: Customer ID
            days: Number of days to look back (default: 30)

        Returns:
            List of recent interaction dictionaries
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        query = """
            SELECT
                i.interaction_id,
                i.customer_id,
                i.type,
                i.content,
                i.created_at,
                i.updated_at,
                e.name as employee_name,
                e.role as employee_role
            FROM interaction_details i
            LEFT JOIN employee_info e ON i.employee_id = e.employee_id
            WHERE i.customer_id = $1 AND i.created_at >= $2 AND i.type != 'quote_request'
            ORDER BY i.created_at DESC
        """
        return await self._execute_query(conn, query, customer_id, cutoff_date)

    async def count_by_customer(self, conn: asyncpg.Connection, customer_id: int) -> int:
        """
        Count total interactions for a customer.

        Args:
            conn: asyncpg database connection
            customer_id: Customer ID

        Returns:
            Total interaction count
        """
        query = """
            SELECT COUNT(*) as count
            FROM interaction_details
            WHERE customer_id = $1
        """
        result = await self._execute_query_one(conn, query, customer_id)
        return result['count'] if result else 0

    async def get_interaction_summary_options(self, conn: asyncpg.Connection, customer_id: int) -> Dict[str, Any]:
        """
        Get interaction summary options for a customer.

        Args:
            conn: asyncpg database connection
            customer_id: Customer ID

        Returns:
            Dictionary with interaction summary data
        """
        # Get email count and last email date from crm_emails table
        email_query = """
            SELECT
                COUNT(*) as email_count,
                MAX(created_at) as last_email_date
            FROM crm_emails
            WHERE customer_id = $1
        """
        email_result = await self._execute_query_one(conn, email_query, customer_id)
        email_count = email_result.get('email_count', 0) if email_result else 0
        last_email_date = email_result.get('last_email_date') if email_result else None

        # Get other interaction counts from interaction_details table
        query = """
            SELECT
                COUNT(*) as total_interactions,
                MAX(created_at) as last_interaction_date,
                COUNT(CASE WHEN type = 'call' THEN 1 END) as call_count,
                COUNT(CASE WHEN type = 'meeting' THEN 1 END) as meeting_count,
                COUNT(CASE WHEN type = 'note' THEN 1 END) as note_count
            FROM interaction_details
            WHERE customer_id = $1
        """
        result = await self._execute_query_one(conn, query, customer_id)

        # Add email count and compute actual last interaction date across both tables
        if result:
            result['email_count'] = email_count
            result['total_interactions'] = result.get('total_interactions', 0) + email_count

            # Determine the most recent interaction date from both tables
            interaction_date = result.get('last_interaction_date')
            if last_email_date and interaction_date:
                # Both exist, use the most recent
                result['last_interaction_date'] = max(last_email_date, interaction_date)
            elif last_email_date:
                # Only email date exists
                result['last_interaction_date'] = last_email_date
            # else: keep the interaction_date from interaction_details (or None if no interactions)

        return result

    async def get_comprehensive_customer_data(self, conn: asyncpg.Connection, customer_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Get comprehensive customer interaction data including emails and notes.

        Args:
            conn: asyncpg database connection
            customer_id: Customer ID
            days: Number of days to look back (default: 30)

        Returns:
            Dictionary with comprehensive customer data
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        # Get emails from crm_emails table
        email_query = """
            SELECT
                ce.email_id as interaction_id,
                ce.body as content,
                ce.created_at,
                e.name as employee_name
            FROM crm_emails ce
            LEFT JOIN employee_info e ON ce.employee_id = e.employee_id
            WHERE ce.customer_id = $1
              AND ce.created_at >= $2
            ORDER BY ce.created_at DESC
        """
        emails = await self._execute_query(conn, email_query, customer_id, cutoff_date)

        # Get notes
        note_query = """
            SELECT
                i.interaction_id,
                i.content,
                i.created_at,
                e.name as employee_name
            FROM interaction_details i
            LEFT JOIN employee_info e ON i.employee_id = e.employee_id
            WHERE i.customer_id = $1
              AND i.type = 'note'
              AND i.created_at >= $2
            ORDER BY i.created_at DESC
        """
        notes = await self._execute_query(conn, note_query, customer_id, cutoff_date)

        return {
            'emails': emails,
            'notes': notes,
            'total_emails': len(emails),
            'total_notes': len(notes)
        }

    async def create_interaction(self, conn: asyncpg.Connection, interaction_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create a new interaction.

        Args:
            conn: asyncpg database connection
            interaction_data: Dictionary with interaction data

        Returns:
            Created interaction dictionary or None
        """
        query = """
            INSERT INTO interaction_details (
                customer_id, employee_id, type, content, created_at, updated_at,
                gmail_message_id, theme, source
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9
            )
            RETURNING *
        """
        return await self._execute_write(
            conn, query,
            interaction_data.get('customer_id'),
            interaction_data.get('employee_id'),
            interaction_data.get('type'),
            interaction_data.get('content'),
            interaction_data.get('created_at'),
            interaction_data.get('updated_at'),
            interaction_data.get('gmail_message_id'),
            interaction_data.get('theme'),
            interaction_data.get('source')
        )
