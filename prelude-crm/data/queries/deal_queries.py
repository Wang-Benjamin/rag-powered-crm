"""
Database queries for deal stage progression system.
Leverages existing infrastructure from crm_data_router.py and insights_sql_query.py
"""

import logging
import asyncpg
from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone

from services.cache_service import clear_cache
from data.queries.insights_queries import get_comprehensive_customer_data

logger = logging.getLogger(__name__)


async def get_active_deals_for_room_analysis(conn: asyncpg.Connection) -> List[Dict[str, Any]]:
    """
    Fetch all active deals (excluding closed-won and closed-lost).

    Args:
        conn: asyncpg database connection

    Returns:
        List of deal dictionaries with client and employee information
    """
    try:
        rows = await conn.fetch("""
            SELECT
                d.deal_id,
                d.deal_name,
                d.description,
                d.room_status,
                d.value_usd,
                d.employee_id,
                d.client_id,
                d.expected_close_date,
                d.last_contact_date,
                d.created_at,
                d.updated_at,
                c.name as client_name,
                (SELECT email FROM personnel WHERE client_id = c.client_id AND is_primary = true LIMIT 1) as client_email,
                e.name as employee_name,
                e.email as employee_email
            FROM deals d
            LEFT JOIN clients c ON d.client_id = c.client_id
            LEFT JOIN employee_info e ON d.employee_id = e.employee_id
            WHERE d.room_status NOT IN ('closed-won', 'closed-lost')
            ORDER BY d.updated_at DESC
        """)

        logger.info(f"Found {len(rows)} active deals for stage analysis")
        return [dict(row) for row in rows]

    except Exception as e:
        logger.error(f"Error fetching active deals: {e}")
        raise


async def get_deal_communications_comprehensive(
    conn: asyncpg.Connection,
    client_id: int,
    days_lookback: int = 30
) -> Dict[str, Any]:
    """
    Fetch comprehensive customer data including emails and notes.
    Leverages existing get_comprehensive_customer_data function.

    Args:
        conn: asyncpg database connection
        client_id: Client ID to fetch data for
        days_lookback: Number of days to look back (for filtering)

    Returns:
        Dictionary with filtered emails and notes
    """
    try:
        # Use existing comprehensive data function
        comprehensive_data = await get_comprehensive_customer_data(conn, client_id)

        if not comprehensive_data:
            logger.warning(f"No comprehensive data found for client {client_id}")
            return {"emails": [], "notes": []}

        # Fetch emails from crm_emails table (emails are NOT in interaction_details)
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_lookback)
        emails = []
        try:
            email_rows = await conn.fetch("""
                SELECT email_id, customer_id, from_email, to_email, subject, body,
                       direction, created_at, updated_at
                FROM crm_emails
                WHERE customer_id = $1 AND created_at >= $2
                ORDER BY created_at DESC
            """, client_id, cutoff_date)
            emails = [dict(row) for row in email_rows]
        except Exception as e:
            logger.warning(f"Error fetching emails from crm_emails for client {client_id}: {e}")

        # Extract and filter notes
        all_notes = comprehensive_data.get('employee_client_notes', [])

        # Filter notes within lookback period
        notes = []
        for note in all_notes:
            created_at = note.get('created_at')
            if not created_at:
                continue

            # Handle both datetime objects and strings
            try:
                if isinstance(created_at, datetime):
                    note_date = created_at
                elif isinstance(created_at, str):
                    note_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                else:
                    continue
                if note_date.tzinfo is None:
                    note_date = note_date.replace(tzinfo=timezone.utc)

                if note_date >= cutoff_date:
                    notes.append(note)
            except Exception as e:
                logger.warning(f"Error parsing date for note: {e}")
                continue

        logger.info(f"Filtered communications for client {client_id}: {len(emails)} emails, {len(notes)} notes (last {days_lookback} days)")

        return {
            "emails": emails,
            "notes": notes,
            "all_data": comprehensive_data  # Include full data for context
        }

    except Exception as e:
        logger.error(f"Error fetching deal communications for client {client_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {"emails": [], "notes": []}


async def update_deal_room_status(
    conn: asyncpg.Connection,
    deal_id: int,
    new_stage: str,
    reasoning: str = None,
    updated_by: str = "automated_stage_progression",
    update_type: str = "automatic"
) -> bool:
    """
    Update deal room_status.

    Args:
        conn: asyncpg database connection
        deal_id: Deal ID to update
        new_stage: New room_status value
        reasoning: Explanation for the change (optional, for logging)
        updated_by: Who/what triggered the update (for logging)
        update_type: Type of update (for logging)

    Returns:
        True if successful, False otherwise
    """
    try:
        async with conn.transaction():
            # Get current room_status for logging
            result = await conn.fetchrow("SELECT room_status FROM deals WHERE deal_id = $1", deal_id)

            if not result:
                logger.error(f"Deal {deal_id} not found")
                return False

            old_status = result['room_status']

            # Update deal room_status
            await conn.execute("""
                UPDATE deals
                SET room_status = $1,
                    updated_at = CURRENT_TIMESTAMP,
                    last_contact_date = CURRENT_TIMESTAMP
                WHERE deal_id = $2
            """, new_stage, deal_id)

        # Clear relevant caches
        clear_cache("get_all_deals")
        clear_cache(f"get_deal_by_id:{deal_id}")

        logger.info(f"Updated deal {deal_id} room_status: {old_status} -> {new_stage} | Type: {update_type} | Reason: {reasoning[:100] if reasoning else 'N/A'}... | By: {updated_by}")
        return True

    except Exception as e:
        logger.error(f"Error updating deal {deal_id} room_status: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


async def update_deal_timestamp(
    conn: asyncpg.Connection,
    deal_id: int,
    reasoning: str = None,
    updated_by: str = "automated_stage_progression",
    update_type: str = "automatic"
) -> bool:
    """
    Update deal timestamp without changing the room_status (for periodic refresh tracking).

    Args:
        conn: asyncpg database connection
        deal_id: Deal ID to update
        reasoning: Explanation for the refresh (optional, for logging)
        updated_by: Who/what triggered the update (for logging)
        update_type: Type of update (for logging)

    Returns:
        True if successful, False otherwise
    """
    try:
        async with conn.transaction():
            # Get current room_status for logging
            result = await conn.fetchrow("SELECT room_status FROM deals WHERE deal_id = $1", deal_id)

            if not result:
                logger.error(f"Deal {deal_id} not found")
                return False

            current_status = result['room_status']

            # Update timestamps only, keeping room_status unchanged
            await conn.execute("""
                UPDATE deals
                SET updated_at = CURRENT_TIMESTAMP,
                    last_contact_date = CURRENT_TIMESTAMP
                WHERE deal_id = $1
            """, deal_id)

        # Clear relevant caches
        clear_cache("get_all_deals")
        clear_cache(f"get_deal_by_id:{deal_id}")

        logger.info(f"Refreshed deal {deal_id} timestamp: room_status unchanged ({current_status}) | Type: {update_type} | Reason: {reasoning[:100] if reasoning else 'N/A'}... | By: {updated_by}")
        return True

    except Exception as e:
        logger.error(f"Error updating deal {deal_id} timestamp: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
