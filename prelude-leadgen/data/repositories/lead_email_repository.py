"""
Lead Email Repository for Lead Generation Service (asyncpg).

Handles database operations for lead email history, including:
- Fetching email history for leads
- Retrieving recent emails for analysis
- Email statistics and analytics

All methods are async and take an asyncpg connection as first parameter.
"""

import logging
from typing import List, Dict, Optional, Any

from data.repositories.base import BaseRepository, QueryResult

logger = logging.getLogger(__name__)


class LeadEmailRepository(BaseRepository):
    """Repository for lead email data operations."""

    def __init__(self):
        """Initialize lead email repository."""
        super().__init__(
            table_name="lead_emails",
            primary_key="email_id",
        )

    async def get_recent_emails(
        self,
        conn,
        lead_id: str,
        limit: int = 10,
        include_sent: bool = True,
        include_received: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get recent emails for a lead, ordered by timestamp descending.

        Args:
            conn: asyncpg connection
            lead_id: Lead ID to fetch emails for
            limit: Maximum number of emails to return (default: 10)
            include_sent: Include sent emails (direction='sent')
            include_received: Include received emails (direction='received')

        Returns:
            List of email dictionaries
        """
        try:
            # Build direction filter
            direction_conditions = []
            if include_sent:
                direction_conditions.append("'sent'")
            if include_received:
                direction_conditions.append("'received'")

            if not direction_conditions:
                logger.warning(f"No email directions specified for lead {lead_id}")
                return []

            direction_filter = f"AND direction IN ({', '.join(direction_conditions)})"

            query = f"""
                SELECT
                    email_id,
                    lead_id,
                    from_email,
                    to_email,
                    subject,
                    body,
                    direction,
                    employee_id,
                    email_timestamp,
                    created_at,
                    thread_id,
                    rfc_message_id,
                    in_reply_to
                FROM {self.table_name}
                WHERE lead_id = $1 {direction_filter}
                ORDER BY email_timestamp DESC
                LIMIT $2
            """

            results = await conn.fetch(query, lead_id, limit)

            if results:
                emails = [dict(row) for row in results]
                logger.info(f"Retrieved {len(emails)} recent emails for lead {lead_id}")
                return emails

            logger.info(f"No emails found for lead {lead_id}")
            return []

        except Exception as e:
            logger.error(f"Error getting recent emails for lead {lead_id}: {e}")
            return []

    async def get_email_count(self, conn, lead_id: str) -> Dict[str, int]:
        """
        Get email count statistics for a lead.

        Args:
            conn: asyncpg connection
            lead_id: Lead ID

        Returns:
            Dictionary with counts: total, sent, received
        """
        try:
            query = f"""
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN direction = 'sent' THEN 1 END) as sent,
                    COUNT(CASE WHEN direction = 'received' THEN 1 END) as received
                FROM {self.table_name}
                WHERE lead_id = $1
            """

            result = await conn.fetchrow(query, lead_id)

            if result:
                return {
                    "total": result["total"] or 0,
                    "sent": result["sent"] or 0,
                    "received": result["received"] or 0
                }

            return {"total": 0, "sent": 0, "received": 0}

        except Exception as e:
            logger.error(f"Error getting email count for lead {lead_id}: {e}")
            return {"total": 0, "sent": 0, "received": 0}

    async def search(self, conn, **kwargs) -> QueryResult:
        """
        Search method implementation (required by BaseRepository).
        Not used for this repository - use get_recent_emails instead.
        """
        raise NotImplementedError("Use get_recent_emails() for lead email queries")
