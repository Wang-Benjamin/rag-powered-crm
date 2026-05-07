"""Customer service for CRM - handles customer-related business logic"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

import asyncpg
from fastapi import HTTPException

from data.repositories.customer_repository import CustomerRepository
from data.repositories.employee_repository import EmployeeRepository

logger = logging.getLogger(__name__)

# Initialize repositories
customer_repo = CustomerRepository()
employee_repo = EmployeeRepository()


async def get_dashboard_stats(conn: asyncpg.Connection) -> Dict[str, Any]:
    """
    Get CRM dashboard statistics.

    Args:
        conn: asyncpg connection

    Returns:
        Dictionary with dashboard statistics

    Raises:
        HTTPException: If database error
    """
    try:
        stats = await customer_repo.get_dashboard_stats(conn)

        if not stats:
            # Return default stats if no data
            return {
                'total_customers': 0,
                'active_customers': 0,
                'at_risk_customers': 0,
                'total_deal_value': 0,
                'avg_health_score': 75,
                'new_customers_month': 0,
                'expansion_opportunities': 0
            }

        return stats

    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching dashboard statistics: {str(e)}")


async def get_all_customers(
    conn: asyncpg.Connection,
    user_email: str,
    search: Optional[str] = None,
    status: Optional[str] = None,
    page: Optional[int] = None,
    per_page: Optional[int] = None
):
    """
    Get all customers with optional filtering and pagination.

    Args:
        conn: asyncpg connection
        user_email: Authenticated user's email for access-role check
        search: Optional search term for name/email/contact
        status: Optional status filter
        page: Page number (1-based). If None, returns all.
        per_page: Items per page. If None, returns all.

    Returns:
        List of customer dictionaries, or (list, total) tuple when paginated

    Raises:
        HTTPException: If database error
    """
    try:
        # Check if user is admin or regular user
        access_role = await employee_repo.get_access_role(conn, user_email)

        # Build filters
        filters = {}
        if search:
            filters['search'] = search
        if status:
            filters['status'] = status

        # If admin, get all customers; if user, get only assigned customers
        if access_role == 'admin':
            result = await customer_repo.find_all_with_details(conn, filters, page=page, per_page=per_page)
        else:
            # Get employee ID for filtering
            employee_id = await employee_repo.find_id_by_email(conn, user_email)
            if not employee_id:
                logger.warning(f"Employee not found for email: {user_email}")
                if page is not None and per_page is not None:
                    return [], 0
                return []

            result = await customer_repo.find_by_employee(conn, employee_id, filters, page=page, per_page=per_page)

        if page is not None and per_page is not None:
            customers, total = result
            logger.info(f"Retrieved {len(customers)}/{total} customers (page {page}) for user {user_email}")
            return customers, total

        logger.info(f"Retrieved {len(result)} customers for user {user_email}")
        return result

    except Exception as e:
        logger.error(f"Error getting customers: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching customers: {str(e)}")


async def get_customer_by_id(conn: asyncpg.Connection, customer_id: int) -> Dict[str, Any]:
    """
    Get specific customer by ID with complete details.

    Args:
        conn: asyncpg connection
        customer_id: Customer ID

    Returns:
        Customer dictionary with full details

    Raises:
        HTTPException: If customer not found or database error
    """
    try:
        customer = await customer_repo.find_by_id(conn, customer_id)

        if not customer:
            raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")

        logger.info(f"Retrieved customer {customer_id}")
        return customer

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting customer {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching customer: {str(e)}")


async def create_customer(conn: asyncpg.Connection, customer_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new customer.

    Args:
        conn: asyncpg connection
        customer_data: Dictionary with customer data

    Returns:
        Created customer dictionary

    Raises:
        HTTPException: If creation fails
    """
    try:
        # This will be implemented with the repository method
        # For now, raise not implemented
        raise HTTPException(status_code=501, detail="Customer creation not yet implemented in service layer")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating customer: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating customer: {str(e)}")


async def update_customer(conn: asyncpg.Connection, customer_id: int, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update a customer's information.

    Args:
        conn: asyncpg connection
        customer_id: Customer ID
        update_data: Dictionary with fields to update

    Returns:
        Updated customer dictionary

    Raises:
        HTTPException: If update fails or customer not found
    """
    try:
        # This will be implemented with the repository method
        # For now, raise not implemented
        raise HTTPException(status_code=501, detail="Customer update not yet implemented in service layer")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating customer {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating customer: {str(e)}")


async def delete_customer(conn: asyncpg.Connection, customer_id: int) -> Dict[str, str]:
    """
    Delete a customer and all related data.

    Args:
        conn: asyncpg connection
        customer_id: Customer ID

    Returns:
        Success message dictionary

    Raises:
        HTTPException: If deletion fails or customer not found
    """
    try:
        # This will be implemented with the repository method
        # For now, raise not implemented
        raise HTTPException(status_code=501, detail="Customer deletion not yet implemented in service layer")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting customer {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting customer: {str(e)}")


async def compute_customer_signal(conn: asyncpg.Connection, client_id: int) -> Optional[Dict[str, str]]:
    """
    Compute the highest-priority signal for a single customer.
    For bulk operations, use compute_signals_batch() instead.
    """
    result = await compute_signals_batch(conn, [client_id])
    return result.get(client_id)


async def compute_signals_batch(conn: asyncpg.Connection, client_ids: List[int]) -> Dict[int, Optional[Dict[str, str]]]:
    """
    Compute signals for multiple customers in a single SQL query.

    Signal priority (highest first):
    - Red (1): urgent email, quote requested, pricing question, replied today
    - Purple (2): deal room viewed, viewed multiple times, high-intent email
    - Orange (3): email opened recently
    - Green (4): buying-signal keywords (MOQ, lead time, samples)

    Returns:
        Dict mapping client_id to signal dict or None
    """
    if not client_ids:
        return {}

    try:
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        days_7 = now - timedelta(days=7)
        days_14 = now - timedelta(days=14)
        days_30 = now - timedelta(days=30)

        # Single query: compute the best signal per customer using DISTINCT ON
        rows = await conn.fetch("""
            WITH customer_ids AS (
                SELECT unnest($1::int[]) AS client_id
            ),
            -- RED signals from emails (intent=quote/pricing, or replied today)
            red_signals AS (
                SELECT DISTINCT ON (ce.customer_id)
                    ce.customer_id AS client_id,
                    1 AS priority,
                    CASE
                        WHEN ce.intent = 'interested' THEN 'Buyer interested'
                        WHEN ce.intent = 'objection' THEN 'Buyer objection'
                        WHEN ce.intent = 'question' THEN 'Buyer question'
                        WHEN ce.created_at >= $3 THEN 'Replied today'
                    END AS label
                FROM crm_emails ce
                WHERE ce.customer_id = ANY($1::int[])
                  AND ce.direction = 'received'
                  AND ce.created_at >= $2
                  AND (
                      ce.intent IN ('interested', 'objection', 'question')
                      OR ce.created_at >= $3
                  )
                ORDER BY ce.customer_id,
                    CASE
                        WHEN ce.intent = 'interested' THEN 1
                        WHEN ce.intent = 'objection' THEN 2
                        WHEN ce.intent = 'question' THEN 3
                        ELSE 4
                    END,
                    ce.created_at DESC
            ),
            -- PURPLE signals from deal room views
            purple_deal AS (
                SELECT DISTINCT ON (d.client_id)
                    d.client_id,
                    2 AS priority,
                    CASE WHEN d.view_count > 1 THEN 'Viewed multiple times'
                         ELSE 'Deal room viewed'
                    END AS label
                FROM deals d
                JOIN deal_room_views drv ON d.deal_id = drv.deal_id
                WHERE d.client_id = ANY($1::int[])
                  AND drv.started_at >= $5
                ORDER BY d.client_id, drv.started_at DESC
            ),
            -- PURPLE signals from high-intent emails
            purple_intent AS (
                SELECT DISTINCT ON (ce.customer_id)
                    ce.customer_id AS client_id,
                    2 AS priority,
                    'High intent'::text AS label
                FROM crm_emails ce
                WHERE ce.customer_id = ANY($1::int[])
                  AND ce.direction = 'received'
                  AND ce.intent IS NOT NULL
                  AND ce.created_at >= $4
                ORDER BY ce.customer_id, ce.created_at DESC
            ),
            -- ORANGE signals from email opens
            orange_signals AS (
                SELECT DISTINCT ON (ce.customer_id)
                    ce.customer_id AS client_id,
                    3 AS priority,
                    'Opened'::text AS label
                FROM crm_emails ce
                WHERE ce.customer_id = ANY($1::int[])
                  AND ce.opened_at IS NOT NULL
                  AND ce.opened_at >= $4
                ORDER BY ce.customer_id, ce.opened_at DESC
            ),
            -- GREEN signals from buying-signal keywords
            green_signals AS (
                SELECT DISTINCT ON (ce.customer_id)
                    ce.customer_id AS client_id,
                    4 AS priority,
                    CASE
                        WHEN LOWER(ce.body) LIKE '%%moq%%' OR LOWER(ce.body) LIKE '%%minimum order%%'
                            THEN 'Asking about MOQ'
                        WHEN LOWER(ce.body) LIKE '%%lead time%%' OR LOWER(ce.body) LIKE '%%delivery time%%'
                            THEN 'Asking about lead time'
                        ELSE 'Asking about samples'
                    END AS label
                FROM crm_emails ce
                WHERE ce.customer_id = ANY($1::int[])
                  AND ce.direction = 'received'
                  AND ce.created_at >= $5
                  AND (
                      LOWER(ce.body) LIKE '%%moq%%'
                      OR LOWER(ce.body) LIKE '%%minimum order%%'
                      OR LOWER(ce.body) LIKE '%%lead time%%'
                      OR LOWER(ce.body) LIKE '%%delivery time%%'
                      OR LOWER(ce.body) LIKE '%%sample%%'
                  )
                ORDER BY ce.customer_id, ce.created_at DESC
            ),
            -- Combine all signals and pick highest priority per customer
            all_signals AS (
                SELECT * FROM red_signals
                UNION ALL SELECT * FROM purple_deal
                UNION ALL SELECT * FROM purple_intent
                UNION ALL SELECT * FROM orange_signals
                UNION ALL SELECT * FROM green_signals
            )
            SELECT DISTINCT ON (client_id)
                client_id, priority, label
            FROM all_signals
            WHERE label IS NOT NULL
            ORDER BY client_id, priority ASC
        """, client_ids, days_7, today_start, days_14, days_30)

        priority_to_level = {1: "red", 2: "purple", 3: "green", 4: "green"}

        results: Dict[int, Optional[Dict[str, str]]] = {}
        for row in rows:
            level = priority_to_level.get(row['priority'])
            if level:
                results[row['client_id']] = {"level": level, "label": row['label']}

        # Fill in None for customers with no signal
        for cid in client_ids:
            if cid not in results:
                results[cid] = None

        return results

    except Exception as e:
        logger.warning(f"Error computing signals in batch: {e}")
        return {cid: None for cid in client_ids}
