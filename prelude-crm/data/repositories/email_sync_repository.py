"""Email sync repository for CRM - handles email synchronization database operations."""

import logging
import asyncpg
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from data.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class EmailSyncRepository(BaseRepository):
    """Repository for email sync database operations."""

    def __init__(self):
        super().__init__('email_sync_state')

    async def get_sync_state(self, conn: asyncpg.Connection, employee_id: int = None) -> Optional[Dict[str, Any]]:
        """
        Get email sync state for specific employee.

        Args:
            conn: asyncpg database connection
            employee_id: Optional employee ID filter

        Returns:
            Sync state dictionary or None
        """
        if employee_id:
            # First try to get existing sync state
            result = await conn.fetchrow("""
                SELECT last_sync_timestamp, last_history_id, emails_synced_count
                FROM email_sync_state
                WHERE employee_id = $1
            """, employee_id)

            if not result:
                # Create a new row with default values for this employee
                result = await conn.fetchrow("""
                    INSERT INTO email_sync_state (employee_id, last_sync_timestamp, last_history_id, emails_synced_count)
                    VALUES ($1, NULL, NULL, 0)
                    ON CONFLICT (employee_id) DO NOTHING
                    RETURNING last_sync_timestamp, last_history_id, emails_synced_count
                """, employee_id)

                # If RETURNING didn't work, fetch the newly created row
                if not result:
                    result = await conn.fetchrow("""
                        SELECT last_sync_timestamp, last_history_id, emails_synced_count
                        FROM email_sync_state
                        WHERE employee_id = $1
                    """, employee_id)
        else:
            # Fallback to get sync state with NULL employee_id
            result = await conn.fetchrow("""
                SELECT last_sync_timestamp, last_history_id, emails_synced_count
                FROM email_sync_state
                WHERE employee_id IS NULL
                LIMIT 1
            """)

        if result:
            return {
                'last_sync_timestamp': result['last_sync_timestamp'],
                'last_history_id': result['last_history_id'],
                'emails_synced_count': result['emails_synced_count'] or 0
            }
        return None

    async def update_sync_state(self, conn: asyncpg.Connection, history_id: str, emails_synced: int, employee_id: int = None) -> bool:
        """
        Update email sync state for specific employee.

        Args:
            conn: asyncpg database connection
            history_id: Gmail history ID
            emails_synced: Number of emails synced
            employee_id: Optional employee ID filter

        Returns:
            True if successful
        """
        try:
            async with conn.transaction():
                if employee_id is not None:
                    # Use INSERT ... ON CONFLICT UPDATE for per-employee sync state
                    await conn.execute("""
                        INSERT INTO email_sync_state (employee_id, last_sync_timestamp, last_history_id, emails_synced_count)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (employee_id)
                        DO UPDATE SET
                            last_sync_timestamp = EXCLUDED.last_sync_timestamp,
                            last_history_id = EXCLUDED.last_history_id,
                            emails_synced_count = email_sync_state.emails_synced_count + EXCLUDED.emails_synced_count
                    """, employee_id, datetime.now(timezone.utc), history_id, emails_synced)
                else:
                    # Fallback to update with NULL employee_id
                    await conn.execute("""
                        UPDATE email_sync_state
                        SET last_sync_timestamp = $1,
                            last_history_id = $2,
                            emails_synced_count = emails_synced_count + $3
                        WHERE employee_id IS NULL
                    """, datetime.now(timezone.utc), history_id, emails_synced)

            return True

        except Exception as e:
            logger.error(f"Error updating sync state: {e}")
            return False

    async def get_all_customer_emails(self, conn: asyncpg.Connection, employee_id: int = None) -> List[str]:
        """
        Get customer email addresses assigned to a specific employee.

        Args:
            conn: asyncpg database connection
            employee_id: Filter customers assigned to this employee (if None, returns all)

        Returns:
            List of customer email addresses
        """
        if employee_id is not None:
            # Get only customers assigned to this employee
            query = """
                SELECT DISTINCT p.email
                FROM personnel p
                INNER JOIN employee_client_links ecl ON p.client_id = ecl.client_id
                WHERE ecl.employee_id = $1
                AND p.email IS NOT NULL AND p.email != ''
            """
            results = await self._execute_query(conn, query, employee_id)
        else:
            # Fallback: get all customer-linked personnel emails
            query = """
                SELECT DISTINCT email
                FROM personnel
                WHERE client_id IS NOT NULL
                AND email IS NOT NULL AND email != ''
            """
            results = await self._execute_query(conn, query)
        return [row['email'] for row in results]

    async def get_all_employee_emails(self, conn: asyncpg.Connection) -> List[str]:
        """
        Get all employee email addresses.

        Args:
            conn: asyncpg database connection

        Returns:
            List of employee email addresses
        """
        query = """
            SELECT DISTINCT email
            FROM employee_info
            WHERE email IS NOT NULL AND email != ''
        """
        results = await self._execute_query(conn, query)
        return [row['email'] for row in results]

    async def find_customer_by_email(self, conn: asyncpg.Connection, email: str) -> Optional[Dict[str, Any]]:
        """
        Find customer by email address.

        Args:
            conn: asyncpg database connection
            email: Customer email to search for

        Returns:
            Customer dictionary or None
        """
        query = """
            SELECT client_id, name, email
            FROM clients
            WHERE LOWER(email) = LOWER($1)
            LIMIT 1
        """
        return await self._execute_query_one(conn, query, email)
