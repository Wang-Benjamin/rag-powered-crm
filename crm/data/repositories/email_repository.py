"""Email repository for centralized crm_emails table access"""

import logging
import asyncpg
from typing import Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class EmailRepository:
    """Repository for managing email data in crm_emails table"""

    async def insert_email(
        self,
        conn: asyncpg.Connection,
        from_email: str,
        to_email: str,
        subject: str,
        body: str,
        direction: str,
        customer_id: Optional[int] = None,
        deal_id: Optional[int] = None,
        employee_id: Optional[int] = None,
        message_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        in_reply_to: Optional[str] = None,
        rfc_message_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
        tracking_token: Optional[str] = None,
        tracking_token_expires_at: Optional[datetime] = None,
        intent: Optional[str] = None,
        draft_body: Optional[str] = None
    ) -> int:
        """
        Insert a new email record into crm_emails table.

        Args:
            conn: asyncpg database connection
            from_email: Sender email address
            to_email: Recipient email address
            subject: Email subject
            body: Email body
            direction: 'sent' or 'received'
            customer_id: Customer/client ID (optional)
            deal_id: Deal ID for deal isolation (optional)
            employee_id: Employee ID of sender (optional)
            message_id: Gmail/Outlook message ID for duplicate prevention (optional)
            thread_id: Gmail threadId or Outlook conversationId (optional)
            in_reply_to: RFC Message-ID this email replies to (optional)
            rfc_message_id: RFC 2822 Message-ID header value (optional)
            created_at: Email timestamp (defaults to now)

        Returns:
            email_id of inserted record

        Raises:
            Exception if insert fails
        """
        try:
            # Use provided timestamp or current time
            timestamp = created_at or datetime.now(timezone.utc)

            result = await conn.fetchrow("""
                INSERT INTO crm_emails (
                    from_email, to_email, subject, body, direction,
                    customer_id, deal_id, employee_id, message_id,
                    thread_id, in_reply_to, rfc_message_id, created_at, updated_at,
                    tracking_token, tracking_token_expires_at,
                    intent, draft_body
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
                ON CONFLICT (message_id) DO NOTHING
                RETURNING email_id
            """,
                from_email, to_email, subject, body, direction,
                customer_id, deal_id, employee_id, message_id,
                thread_id, in_reply_to, rfc_message_id, timestamp, timestamp,
                tracking_token, tracking_token_expires_at,
                intent, draft_body
            )

            if result:
                email_id = result['email_id']
                logger.info(f"Inserted email {email_id} (message_id: {message_id}, thread_id: {thread_id})")
                return email_id
            else:
                logger.warning(f"Email with message_id {message_id} already exists, skipped")
                return None

        except Exception as e:
            logger.error(f"Failed to insert email: {e}")
            raise

    async def get_emails_by_customer(
        self,
        conn: asyncpg.Connection,
        customer_id: int,
        limit: int = 20,
        employee_id: Optional[int] = None
    ) -> List[Dict]:
        """
        Get emails for a specific customer.

        Args:
            conn: asyncpg database connection
            customer_id: Customer/client ID
            limit: Maximum number of emails to return
            employee_id: Filter by specific employee (optional)

        Returns:
            List of email records as dictionaries
        """
        try:
            if employee_id is not None:
                rows = await conn.fetch("""
                    SELECT
                        e.email_id,
                        e.from_email,
                        e.to_email,
                        e.subject,
                        e.body,
                        e.direction,
                        e.customer_id,
                        e.deal_id,
                        e.employee_id,
                        e.message_id,
                        e.thread_id,
                        e.in_reply_to,
                        e.created_at,
                        e.updated_at,
                        ei.name as employee_name,
                        ei.role as employee_role
                    FROM crm_emails e
                    LEFT JOIN employee_info ei ON e.employee_id = ei.employee_id
                    WHERE e.customer_id = $1 AND e.employee_id = $2
                    ORDER BY e.created_at DESC
                    LIMIT $3
                """, customer_id, employee_id, limit)
            else:
                rows = await conn.fetch("""
                    SELECT
                        e.email_id,
                        e.from_email,
                        e.to_email,
                        e.subject,
                        e.body,
                        e.direction,
                        e.customer_id,
                        e.deal_id,
                        e.employee_id,
                        e.message_id,
                        e.thread_id,
                        e.in_reply_to,
                        e.created_at,
                        e.updated_at,
                        ei.name as employee_name,
                        ei.role as employee_role
                    FROM crm_emails e
                    LEFT JOIN employee_info ei ON e.employee_id = ei.employee_id
                    WHERE e.customer_id = $1
                    ORDER BY e.created_at DESC
                    LIMIT $2
                """, customer_id, limit)

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get emails for customer {customer_id}: {e}")
            return []

    async def get_emails_by_deal(
        self,
        conn: asyncpg.Connection,
        deal_id: int,
        limit: int = 20
    ) -> List[Dict]:
        """
        Get emails for a specific deal.

        Args:
            conn: asyncpg database connection
            deal_id: Deal ID
            limit: Maximum number of emails to return

        Returns:
            List of email records as dictionaries
        """
        try:
            rows = await conn.fetch("""
                SELECT
                    e.email_id,
                    e.from_email,
                    e.to_email,
                    e.subject,
                    e.body,
                    e.direction,
                    e.customer_id,
                    e.deal_id,
                    e.employee_id,
                    e.message_id,
                    e.thread_id,
                    e.in_reply_to,
                    e.created_at,
                    e.updated_at,
                    ei.name as employee_name,
                    ei.role as employee_role
                FROM crm_emails e
                LEFT JOIN employee_info ei ON e.employee_id = ei.employee_id
                WHERE e.deal_id = $1
                ORDER BY e.created_at DESC
                LIMIT $2
            """, deal_id, limit)

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get emails for deal {deal_id}: {e}")
            return []

    async def check_duplicate(self, conn: asyncpg.Connection, message_id: str) -> bool:
        """
        Check if email with given message_id already exists.

        Args:
            conn: asyncpg database connection
            message_id: Gmail/Outlook message ID

        Returns:
            True if email exists, False otherwise
        """
        try:
            result = await conn.fetchrow("""
                SELECT 1 FROM crm_emails WHERE message_id = $1
            """, message_id)

            return result is not None

        except Exception as e:
            logger.error(f"Failed to check duplicate for message_id {message_id}: {e}")
            return False

    async def get_all_threads(
        self,
        conn: asyncpg.Connection,
        customer_id: int,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get all email threads for a customer, grouped by thread_id.

        Args:
            conn: asyncpg database connection
            customer_id: Customer/client ID
            limit: Maximum number of threads to return

        Returns:
            List of thread summaries with latest email info
        """
        try:
            rows = await conn.fetch("""
                WITH thread_summary AS (
                    SELECT
                        thread_id,
                        customer_id,
                        MAX(created_at) as last_activity,
                        COUNT(*) as email_count,
                        SUM(CASE WHEN direction = 'sent' THEN 1 ELSE 0 END) as sent_count,
                        SUM(CASE WHEN direction = 'received' THEN 1 ELSE 0 END) as received_count
                    FROM crm_emails
                    WHERE customer_id = $1 AND thread_id IS NOT NULL
                    GROUP BY thread_id, customer_id
                ),
                latest_email AS (
                    SELECT DISTINCT ON (thread_id)
                        thread_id,
                        subject,
                        from_email,
                        to_email,
                        direction,
                        body,
                        rfc_message_id
                    FROM crm_emails
                    WHERE customer_id = $1 AND thread_id IS NOT NULL
                    ORDER BY thread_id, created_at DESC
                )
                SELECT
                    ts.thread_id,
                    ts.customer_id,
                    ts.last_activity,
                    ts.email_count,
                    ts.sent_count,
                    ts.received_count,
                    le.subject,
                    le.from_email,
                    le.to_email,
                    le.direction as last_direction,
                    LEFT(le.body, 200) as preview,
                    le.rfc_message_id as last_rfc_message_id
                FROM thread_summary ts
                JOIN latest_email le ON ts.thread_id = le.thread_id
                ORDER BY ts.last_activity DESC
                LIMIT $2
            """, customer_id, limit)

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get threads for customer {customer_id}: {e}")
            return []

    async def get_emails_by_thread(
        self,
        conn: asyncpg.Connection,
        thread_id: str,
        customer_id: int,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get all emails in a specific thread.

        Args:
            conn: asyncpg database connection
            thread_id: Gmail threadId or Outlook conversationId
            customer_id: Customer/client ID (for access control)
            limit: Maximum number of emails to return

        Returns:
            List of email records in the thread, ordered by date
        """
        try:
            rows = await conn.fetch("""
                SELECT
                    e.email_id,
                    e.from_email,
                    e.to_email,
                    e.subject,
                    e.body,
                    e.direction,
                    e.customer_id,
                    e.deal_id,
                    e.employee_id,
                    e.message_id,
                    e.thread_id,
                    e.in_reply_to,
                    e.rfc_message_id,
                    e.created_at,
                    e.updated_at,
                    ei.name as employee_name,
                    ei.role as employee_role
                FROM crm_emails e
                LEFT JOIN employee_info ei ON e.employee_id = ei.employee_id
                WHERE e.thread_id = $1 AND e.customer_id = $2
                ORDER BY e.created_at ASC
                LIMIT $3
            """, thread_id, customer_id, limit)

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get emails for thread {thread_id}: {e}")
            return []
