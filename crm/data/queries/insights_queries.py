"""
Centralized SQL queries for CRM insights generation system.

This module contains all database query logic for customer activity analysis,
agent input data preparation, and insight generation support.
"""

import logging
import asyncpg
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


async def analyze_customer_activity(conn: asyncpg.Connection, customer_id: int) -> Dict[str, Any]:
    """
    Analyze customer activity patterns across all communication channels
    (interactions, emails, notes, deals) to determine agent selection.

    Args:
        conn: asyncpg database connection
        customer_id: Customer ID to analyze

    Returns:
        Dict containing customer analysis results including total engagement score
    """
    try:
        fourteen_days_ago = datetime.now(timezone.utc) - timedelta(days=14)

        # Query interaction_details (calls/meetings)
        interaction_data = await conn.fetchrow("""
            SELECT COUNT(*) as total,
                   MAX(created_at) as last_date,
                   COUNT(CASE WHEN created_at >= $1 THEN 1 END) as last_14_days
            FROM interaction_details
            WHERE customer_id = $2
        """, fourteen_days_ago, customer_id) or {}

        # Query crm_emails
        email_data = await conn.fetchrow("""
            SELECT COUNT(*) as total,
                   MAX(created_at) as last_date,
                   COUNT(CASE WHEN created_at >= $1 THEN 1 END) as last_14_days
            FROM crm_emails
            WHERE customer_id = $2
        """, fourteen_days_ago, customer_id) or {}

        # Query employee_client_notes
        note_data = await conn.fetchrow("""
            SELECT COUNT(*) as total,
                   MAX(created_at) as last_date,
                   COUNT(CASE WHEN created_at >= $1 THEN 1 END) as last_14_days
            FROM employee_client_notes
            WHERE client_id = $2
        """, fourteen_days_ago, customer_id) or {}

        # Query deals
        deals_data = {"deal_count": 0, "active_deal_count": 0}
        try:
            deals_result = await conn.fetchrow("""
                SELECT COUNT(*) as deal_count,
                       COUNT(CASE WHEN room_status NOT IN ('closed-won', 'closed-lost') THEN 1 END) as active_deal_count,
                       MAX(created_at) as last_deal_date,
                       MIN(created_at) as first_deal_date
                FROM deals
                WHERE client_id = $1
            """, customer_id)
            if deals_result:
                deals_data = dict(deals_result)
        except Exception as e:
            logger.debug(f"Deals table not accessible for customer {customer_id}: {e}")

        # Extract counts
        interaction_count = interaction_data.get('total', 0) or 0
        email_count = email_data.get('total', 0) or 0
        note_count = note_data.get('total', 0) or 0
        deal_count = deals_data.get('deal_count', 0) or 0
        active_deal_count = deals_data.get('active_deal_count', 0) or 0

        recent_interactions = interaction_data.get('last_14_days', 0) or 0
        recent_emails = email_data.get('last_14_days', 0) or 0
        recent_notes = note_data.get('last_14_days', 0) or 0

        # Total engagement across all channels
        total_engagement = interaction_count + email_count + note_count
        recent_engagement = recent_interactions + recent_emails + recent_notes

        # Most recent activity across all channels
        last_dates = [
            d for d in [
                interaction_data.get('last_date'),
                email_data.get('last_date'),
                note_data.get('last_date'),
            ] if d is not None
        ]
        last_activity = max(last_dates) if last_dates else None

        days_since_activity = None
        if last_activity:
            if isinstance(last_activity, str):
                last_activity = datetime.fromisoformat(last_activity.replace('Z', '+00:00'))
            days_since_activity = (datetime.now(timezone.utc) - last_activity).days

        analysis = {
            "interaction_count": interaction_count,
            "email_count": email_count,
            "note_count": note_count,
            "total_engagement": total_engagement,
            "recent_interactions": recent_interactions,
            "recent_emails": recent_emails,
            "recent_notes": recent_notes,
            "recent_engagement": recent_engagement,
            "deal_count": deal_count,
            "active_deal_count": active_deal_count,
            "has_active_deals": active_deal_count > 0,
            "last_activity_date": last_activity,
            "days_since_activity": days_since_activity,
        }

        logger.info(f"Customer {customer_id} analysis: engagement={total_engagement} "
                     f"(interactions={interaction_count}, emails={email_count}, notes={note_count}), "
                     f"recent_14d={recent_engagement}, deals={deal_count} (active={active_deal_count})")
        return analysis

    except Exception as e:
        logger.error(f"Failed to analyze customer activity for {customer_id}: {e}")
        return {
            "interaction_count": 0,
            "email_count": 0,
            "note_count": 0,
            "total_engagement": 0,
            "recent_interactions": 0,
            "recent_emails": 0,
            "recent_notes": 0,
            "recent_engagement": 0,
            "deal_count": 0,
            "active_deal_count": 0,
            "has_active_deals": False,
            "last_activity_date": None,
            "days_since_activity": None,
        }


async def get_comprehensive_customer_data(conn: asyncpg.Connection, customer_id: int) -> Dict[str, Any]:
    """
    Gather comprehensive customer data from all relevant tables for agent input.

    Args:
        conn: asyncpg database connection
        customer_id: Customer ID to gather data for

    Returns:
        Dict containing comprehensive customer data structure
    """
    try:
        logger.info(f"DB Query [Customer {customer_id}]: Starting comprehensive data retrieval")
        start_time = datetime.now(timezone.utc)

        # Get customer basic information from clients table
        client_info = await conn.fetchrow("""
            SELECT ci.client_id, ci.name, ci.phone,
                   ci.location, ci.preferred_language, ci.source, ci.notes,
                   ci.created_at, ci.updated_at,
                   (SELECT full_name FROM personnel WHERE client_id = ci.client_id AND is_primary = true LIMIT 1) as primary_contact,
                   (SELECT email FROM personnel WHERE client_id = ci.client_id AND is_primary = true LIMIT 1) as email
            FROM clients ci
            WHERE ci.client_id = $1
        """, customer_id)

        if not client_info:
            logger.warning(f"No client info found for customer {customer_id}")
            return {}

        # Get customer status and health fields from clients
        client_details = await conn.fetchrow("""
            SELECT COALESCE((SELECT SUM(value_usd) FROM deals WHERE client_id = $1), 0) as total_deal_value,
                   health_score, status
            FROM clients
            WHERE client_id = $1
        """, customer_id)

        # Get all interaction history from interaction_details table
        interactions = await conn.fetch("""
            SELECT interaction_id, customer_id, employee_id, type, content, created_at, updated_at,
                   gmail_message_id, synced_by_employee_id
            FROM interaction_details
            WHERE customer_id = $1
            ORDER BY updated_at DESC
        """, customer_id)

        logger.info(f"DB Query [Customer {customer_id}]: Found {len(interactions)} interactions")

        # Get deal information from deals table (if exists)
        deals = []
        try:
            deals_result = await conn.fetch("""
                SELECT deal_id, deal_name, client_id, value_usd, room_status,
                       description, employee_id, created_at, updated_at,
                       completion_time, last_contact_date, expected_close_date
                FROM deals
                WHERE client_id = $1
                ORDER BY created_at DESC
            """, customer_id)
            if deals_result:
                deals = [dict(deal) for deal in deals_result]
        except Exception as e:
            logger.warning(f"DB Query [Customer {customer_id}]: Deals query failed: {e}")

        # Get employee client notes from employee_client_notes table
        employee_client_notes = []
        try:
            # First check if the table exists
            table_exists_result = await conn.fetchrow("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'employee_client_notes'
                ) as table_exists
            """)
            table_exists = table_exists_result['table_exists'] if table_exists_result else False

            if table_exists:
                notes_result = await conn.fetch("""
                    SELECT note_id, employee_id, client_id, title, body,
                           created_at, updated_at, star
                    FROM employee_client_notes
                    WHERE client_id = $1
                    ORDER BY created_at DESC
                """, customer_id)

                if notes_result:
                    employee_client_notes = [dict(note) for note in notes_result]

            logger.info(f"DB Query [Customer {customer_id}]: Found {len(employee_client_notes)} employee client notes")

        except Exception as e:
            logger.error(f"DB Query [Customer {customer_id}]: Employee client notes query failed: {e}")

        # Calculate summary metrics
        total_interactions = len(interactions)

        # Prepare comprehensive data structure
        comprehensive_data = {
            "client_info": dict(client_info) if client_info else {},
            "client_details": dict(client_details) if client_details else {},
            "interaction_details": [dict(interaction) for interaction in interactions],
            "deals": deals,
            "employee_client_notes": employee_client_notes,
            "summary_metrics": {
                "total_interactions": total_interactions,
                "deal_count": len(deals),
                "notes_count": len(employee_client_notes)
            }
        }

        total_time = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.info(f"DB Query [Customer {customer_id}]: Comprehensive data gathered in {total_time:.2f}s: "
                   f"{total_interactions} interactions, {len(deals)} deals, "
                   f"{len(employee_client_notes)} notes")

        return comprehensive_data

    except Exception as e:
        logger.error(f"Failed to gather comprehensive customer data for {customer_id}: {e}")
        return {}


async def get_customer_basic_info(conn: asyncpg.Connection, customer_id: int) -> Optional[Dict[str, Any]]:
    """
    Get basic customer information for quick lookups.

    Args:
        conn: asyncpg database connection
        customer_id: Customer ID to look up

    Returns:
        Dict containing basic customer info or None if not found
    """
    try:
        result = await conn.fetchrow("""
            SELECT ci.client_id, ci.name,
                   p_primary.full_name as primary_contact,
                   p_primary.email,
                   ci.status, ci.health_score
            FROM clients ci
            LEFT JOIN LATERAL (
                SELECT full_name, email FROM personnel
                WHERE client_id = ci.client_id AND is_primary = true
                LIMIT 1
            ) p_primary ON true
            WHERE ci.client_id = $1
        """, customer_id)

        return dict(result) if result else None

    except Exception as e:
        logger.error(f"Failed to get basic customer info for {customer_id}: {e}")
        return None


async def get_recent_interactions_summary(conn: asyncpg.Connection, customer_id: int, days_back: int) -> Dict[str, Any]:
    """
    Get summary of recent interactions for a customer.

    Args:
        conn: asyncpg database connection
        customer_id: Customer ID
        days_back: Number of days to look back

    Returns:
        Dict containing interaction summary
    """
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

        summary = await conn.fetchrow("""
            SELECT COUNT(*) as interaction_count,
                   COUNT(DISTINCT type) as unique_types,
                   MAX(created_at) as last_interaction,
                   array_agg(DISTINCT type) as interaction_types
            FROM interaction_details
            WHERE customer_id = $1 AND created_at >= $2
        """, customer_id, cutoff_date)

        return dict(summary) if summary else {}

    except Exception as e:
        logger.error(f"Failed to get interaction summary for customer {customer_id}: {e}")
        return {}
