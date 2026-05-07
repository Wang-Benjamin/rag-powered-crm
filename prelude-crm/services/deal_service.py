"""Deal service for CRM - handles deal-related business logic"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

import asyncpg
from fastapi import HTTPException

from data.repositories.deal_repository import DealRepository
from data.repositories.customer_repository import CustomerRepository

logger = logging.getLogger(__name__)

# Initialize repositories
deal_repo = DealRepository()
customer_repo = CustomerRepository()


async def get_deals_for_customer(conn: asyncpg.Connection, customer_id: int) -> List[Dict[str, Any]]:
    """
    Get all deals for a customer.

    Args:
        conn: asyncpg connection
        customer_id: Customer ID

    Returns:
        List of deal dictionaries

    Raises:
        HTTPException: If database error
    """
    try:
        deals = await deal_repo.find_by_customer(conn, customer_id)
        logger.info(f"Retrieved {len(deals)} deals for customer {customer_id}")
        return deals

    except Exception as e:
        logger.error(f"Error getting deals for customer {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching deals: {str(e)}")


async def get_active_deals_for_customer(conn: asyncpg.Connection, customer_id: int) -> List[Dict[str, Any]]:
    """
    Get active deals for a customer (not closed-won or closed-lost).

    Args:
        conn: asyncpg connection
        customer_id: Customer ID

    Returns:
        List of active deal dictionaries

    Raises:
        HTTPException: If database error
    """
    try:
        deals = await deal_repo.find_active_deals(conn, customer_id)
        logger.info(f"Retrieved {len(deals)} active deals for customer {customer_id}")
        return deals

    except Exception as e:
        logger.error(f"Error getting active deals for customer {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching active deals: {str(e)}")


async def get_deal_by_id(conn: asyncpg.Connection, deal_id: int) -> Dict[str, Any]:
    """
    Get specific deal by ID.

    Args:
        conn: asyncpg connection
        deal_id: Deal ID

    Returns:
        Deal dictionary

    Raises:
        HTTPException: If deal not found or database error
    """
    try:
        deal = await deal_repo.find_by_id(conn, deal_id)

        if not deal:
            raise HTTPException(status_code=404, detail=f"Deal {deal_id} not found")

        logger.info(f"Retrieved deal {deal_id}")
        return deal

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting deal {deal_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching deal: {str(e)}")


async def create_deal(conn: asyncpg.Connection, deal_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new deal.

    Args:
        conn: asyncpg connection
        deal_data: Dictionary with deal data

    Returns:
        Created deal dictionary

    Raises:
        HTTPException: If creation fails
    """
    try:
        # Add timestamps
        deal_data['created_at'] = datetime.now(timezone.utc)
        deal_data['updated_at'] = datetime.now(timezone.utc)

        # Create deal
        deal = await deal_repo.create_deal(conn, deal_data)

        if not deal:
            raise HTTPException(status_code=500, detail="Failed to create deal")

        logger.info(f"Created deal {deal.get('deal_id')} for customer {deal_data.get('client_id')}")
        return deal

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating deal: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating deal: {str(e)}")


async def update_deal(conn: asyncpg.Connection, deal_id: int, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update an existing deal.

    Args:
        conn: asyncpg connection
        deal_id: Deal ID
        update_data: Dictionary with fields to update

    Returns:
        Updated deal dictionary

    Raises:
        HTTPException: If update fails or deal not found
    """
    try:
        # Update deal
        deal = await deal_repo.update_deal(conn, deal_id, update_data)

        if not deal:
            raise HTTPException(status_code=404, detail=f"Deal {deal_id} not found")

        logger.info(f"Updated deal {deal_id}")
        return deal

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating deal {deal_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating deal: {str(e)}")


async def update_room_status(conn: asyncpg.Connection, deal_id: int, new_status: str) -> Dict[str, Any]:
    """
    Update deal room_status.

    Args:
        conn: asyncpg connection
        deal_id: Deal ID
        new_status: New room_status value

    Returns:
        Updated deal dictionary

    Raises:
        HTTPException: If update fails or deal not found
    """
    try:
        # Validate room_status
        valid_statuses = ['draft', 'sent', 'viewed', 'quote_requested', 'closed-won', 'closed-lost']
        if new_status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid room_status: {new_status}")

        # Update room_status
        deal = await deal_repo.update_room_status(conn, deal_id, new_status)

        if not deal:
            raise HTTPException(status_code=404, detail=f"Deal {deal_id} not found")

        logger.info(f"Updated deal {deal_id} room_status to {new_status}")
        return deal

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating deal {deal_id} room_status: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating deal room_status: {str(e)}")


async def delete_deal(conn: asyncpg.Connection, deal_id: int) -> Dict[str, str]:
    """
    Delete a deal.

    Args:
        conn: asyncpg connection
        deal_id: Deal ID

    Returns:
        Success message dictionary

    Raises:
        HTTPException: If deletion fails or deal not found
    """
    try:
        success = await deal_repo.delete_deal(conn, deal_id)

        if not success:
            raise HTTPException(status_code=404, detail=f"Deal {deal_id} not found")

        logger.info(f"Deleted deal {deal_id}")
        return {"message": f"Deal {deal_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting deal {deal_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting deal: {str(e)}")
