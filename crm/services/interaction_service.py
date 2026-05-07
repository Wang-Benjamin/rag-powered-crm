"""Interaction service for CRM - handles interaction-related business logic"""

import logging
import json
import asyncpg
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from fastapi import HTTPException

from data.repositories.interaction_repository import InteractionRepository

logger = logging.getLogger(__name__)

# Initialize repository
interaction_repo = InteractionRepository()


async def get_customer_interactions_by_employee(customer_id: str, employee_id: int, conn: asyncpg.Connection) -> List[Dict[str, Any]]:
    """
    Get interactions for a specific customer and employee from database.

    Args:
        customer_id: Customer ID
        employee_id: Employee ID
        conn: asyncpg connection for database access

    Returns:
        List of interaction dictionaries

    Raises:
        HTTPException: If invalid customer ID or database error
    """
    try:
        # Convert customer_id to int for database query
        try:
            customer_id_int = int(customer_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid customer ID format")

        interactions = await interaction_repo.find_by_customer_and_employee(customer_id_int, employee_id, conn)

        logger.info(f"Found {len(interactions)} interactions for customer {customer_id} and employee {employee_id}")
        return interactions

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching interactions for customer {customer_id} and employee {employee_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching interactions: {str(e)}")


async def get_customer_interactions_all(customer_id: str, conn: asyncpg.Connection) -> List[Dict[str, Any]]:
    """
    Get all interactions for a specific customer from database.

    Args:
        customer_id: Customer ID
        conn: asyncpg connection for database access

    Returns:
        List of interaction dictionaries

    Raises:
        HTTPException: If invalid customer ID or database error
    """
    try:
        # Convert customer_id to int for database query
        try:
            customer_id_int = int(customer_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid customer ID format")

        interactions = await interaction_repo.find_by_customer(customer_id_int, conn)

        logger.info(f"Found {len(interactions)} interactions for customer {customer_id}")
        return interactions

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching interactions for customer {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching interactions: {str(e)}")


async def get_recent_customer_interactions(customer_id: str, conn: asyncpg.Connection, days_back: int = 30) -> List[Dict[str, Any]]:
    """
    Get recent interactions for a specific customer from database within the specified time period.

    Args:
        customer_id: Customer ID
        conn: asyncpg connection for database access
        days_back: Number of days to look back (default 30)

    Returns:
        List of recent interaction dictionaries

    Raises:
        HTTPException: If invalid customer ID or database error
    """
    try:
        # Convert customer_id to int for database query
        try:
            customer_id_int = int(customer_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid customer ID format")

        interactions = await interaction_repo.get_recent_interactions(conn, customer_id_int, days_back)

        logger.info(f"Found {len(interactions)} total interactions for customer {customer_id} in last {days_back} days")
        return interactions

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching recent interactions for customer {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching interactions: {str(e)}")


async def get_interaction_summary_options(customer_id: str, conn: asyncpg.Connection, employee_id: int = None) -> Dict[str, Any]:
    """
    Get available options for interaction summary generation.

    Args:
        customer_id: Customer ID
        conn: asyncpg connection for database access
        employee_id: Optional employee ID filter

    Returns:
        Dictionary with interaction summary options
    """
    try:
        customer_id_int = int(customer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid customer ID format")

    # Get interaction summary data from repository
    try:
        summary_data = await interaction_repo.get_interaction_summary_options(customer_id_int, conn)

        if not summary_data:
            return {
                "customer_id": customer_id_int,
                "available_periods": {"last_30_days": 0},
                "recommended_period": 30
            }

        # Calculate period counts based on total interactions
        total = summary_data.get('total_interactions', 0)

        return {
            "customer_id": customer_id_int,
            "total_interactions": total,
            "email_count": summary_data.get('email_count', 0),
            "call_count": summary_data.get('call_count', 0),
            "meeting_count": summary_data.get('meeting_count', 0),
            "note_count": summary_data.get('note_count', 0),
            "last_interaction_date": summary_data.get('last_interaction_date'),
            "recommended_period": 30 if total > 0 else 90
        }

    except Exception as e:
        logger.error(f"Error getting interaction summary options: {e}")
        return {
            "customer_id": customer_id_int,
            "available_periods": {"last_30_days": 0},
            "recommended_period": 30
        }


async def get_comprehensive_customer_data(conn: asyncpg.Connection, employee_id: int = None) -> List[Dict[str, Any]]:
    """
    Get all customer data with interactions and detailed metrics, optionally filtered by employee.

    Note: This function uses complex joins and aggregations that go beyond simple repository operations.
    It will remain in the service layer for now.

    Args:
        conn: asyncpg connection for database access
        employee_id: Optional employee ID filter

    Returns:
        List of customer dictionaries with comprehensive data
    """
    try:
        # Build the interactions subquery based on employee filter
        if employee_id:
            interactions_subquery = """
                (SELECT json_agg(
                    json_build_object(
                        'type', interactions_ordered.type,
                        'content', interactions_ordered.content,
                        'created_at', interactions_ordered.created_at,
                        'employee_name', interactions_ordered.employee_name,
                        'employee_role', interactions_ordered.employee_role
                    )
                )
                FROM (
                    SELECT
                        i.type,
                        i.content,
                        i.created_at,
                        e.name as employee_name,
                        e.role as employee_role
                    FROM interaction_details i
                    LEFT JOIN employee_info e ON i.employee_id = e.employee_id
                    WHERE i.customer_id = ci.client_id AND i.employee_id = $1 AND i.type != 'quote_request'
                    ORDER BY i.created_at DESC
                    LIMIT 5
                ) interactions_ordered)
            """
        else:
            interactions_subquery = """
                (SELECT json_agg(
                    json_build_object(
                        'type', interactions_ordered.type,
                        'content', interactions_ordered.content,
                        'created_at', interactions_ordered.created_at,
                        'employee_name', interactions_ordered.employee_name,
                        'employee_role', interactions_ordered.employee_role
                    )
                )
                FROM (
                    SELECT
                        i.type,
                        i.content,
                        i.created_at,
                        e.name as employee_name,
                        e.role as employee_role
                    FROM interaction_details i
                    LEFT JOIN employee_info e ON i.employee_id = e.employee_id
                    WHERE i.customer_id = ci.client_id AND i.type != 'quote_request'
                    ORDER BY i.created_at DESC
                    LIMIT 5
                ) interactions_ordered)
            """

        # Get comprehensive customer data with interactions
        if employee_id:
            # Only get customers that have interactions with this specific employee
            # $1 is used in the subquery, $2 is used in the EXISTS clause
            query = f"""
            SELECT
                ci.client_id,
                ci.name as company,
                p_primary.full_name as primary_contact,
                p_primary.email,
                ci.phone,
                ci.location,
                ci.created_at as customer_since,
                COALESCE((SELECT SUM(value_usd) FROM deals WHERE client_id = ci.client_id), 0) as total_deal_value,
                ci.health_score,
                ci.status,
                -- Recent interactions
                COALESCE({interactions_subquery}, '[]'::json) as recent_interactions
            FROM clients ci
            LEFT JOIN LATERAL (
                SELECT full_name, email FROM personnel
                WHERE client_id = ci.client_id AND is_primary = true
                LIMIT 1
            ) p_primary ON true
            WHERE EXISTS (
                SELECT 1 FROM interaction_details ic
                WHERE ic.customer_id = ci.client_id
                AND ic.employee_id = $2
            )
            ORDER BY
                CASE WHEN ci.status = 'at-risk' THEN 1
                     WHEN ci.health_score < 60 THEN 2
                     ELSE 3 END,
                ci.health_score ASC NULLS LAST
            """
            rows = await conn.fetch(query, employee_id, employee_id)
        else:
            # Get all customers (original behavior)
            query = f"""
            SELECT
                ci.client_id,
                ci.name as company,
                p_primary.full_name as primary_contact,
                p_primary.email,
                ci.phone,
                ci.location,
                ci.status,
                ci.created_at as customer_since,
                COALESCE((SELECT SUM(value_usd) FROM deals WHERE client_id = ci.client_id), 0) as total_deal_value,
                ci.health_score,
                ci.status,
                -- Recent interactions
                COALESCE({interactions_subquery}, '[]'::json) as recent_interactions
            FROM clients ci
            LEFT JOIN LATERAL (
                SELECT full_name, email FROM personnel
                WHERE client_id = ci.client_id AND is_primary = true
                LIMIT 1
            ) p_primary ON true
            WHERE ci.status IN ('active', 'at-risk')  -- Focus on active customers
            ORDER BY
                CASE WHEN ci.status = 'at-risk' THEN 1
                     WHEN ci.health_score < 60 THEN 2
                     ELSE 3 END,
                ci.health_score ASC NULLS LAST
            """
            rows = await conn.fetch(query)

        customers_data = [dict(row) for row in rows]

        if employee_id:
            logger.info(f"Found {len(customers_data)} customers with interactions for employee {employee_id}")
        else:
            logger.info(f"Found {len(customers_data)} customers with all interactions")

        return customers_data

    except Exception as e:
        logger.error(f"Error getting comprehensive customer data: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching customer data: {str(e)}")
