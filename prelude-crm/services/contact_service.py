"""Contact service for CRM - handles contact-related business logic via personnel table"""

import logging
from typing import List, Dict, Any, Optional

import asyncpg
from fastapi import HTTPException

from data.repositories.contact_repository import ContactRepository

logger = logging.getLogger(__name__)

# Initialize repositories
contact_repo = ContactRepository()


async def get_contacts_for_customer(conn: asyncpg.Connection, customer_id: int) -> List[Dict[str, Any]]:
    """
    Get all personnel linked to a customer.

    Args:
        conn: asyncpg connection
        customer_id: Customer ID

    Returns:
        List of personnel dictionaries

    Raises:
        HTTPException: If database error
    """
    try:
        contacts = await contact_repo.get_contacts_for_customer(conn, customer_id)
        logger.info(f"Retrieved {len(contacts)} contacts for customer {customer_id}")
        return contacts

    except Exception as e:
        logger.error(f"Error getting contacts for customer {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching contacts: {str(e)}")


async def add_contact(conn: asyncpg.Connection, customer_id: int, contact_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add a new personnel record linked to a customer.

    Args:
        conn: asyncpg connection
        customer_id: Customer ID
        contact_data: Dictionary with contact data

    Returns:
        Success message with the created personnel record

    Raises:
        HTTPException: If addition fails
    """
    try:
        async with conn.transaction():
            # If this is set as primary, clear existing primaries first
            if contact_data.get('is_primary'):
                await contact_repo.clear_primary_for_customer(conn, customer_id)

            # Insert into personnel table
            created = await contact_repo.add_contact(conn, customer_id, contact_data)

            if not created:
                raise HTTPException(status_code=500, detail="Failed to add contact")

        logger.info(f"Added personnel to customer {customer_id}: {created['personnel_id']}")
        return {"message": "Contact added successfully", "contact": created}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding contact to customer {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error adding contact: {str(e)}")


async def update_contact(conn: asyncpg.Connection, customer_id: int, contact_id: str, contact_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update an existing personnel record.

    Args:
        conn: asyncpg connection
        customer_id: Customer ID
        contact_id: Personnel UUID (string)
        contact_data: Dictionary with updated contact data

    Returns:
        Success message with updated personnel record

    Raises:
        HTTPException: If update fails or contact not found
    """
    try:
        async with conn.transaction():
            # If setting as primary, clear other primaries first
            if contact_data.get('is_primary'):
                await contact_repo.clear_primary_for_customer(conn, customer_id)

            # Update the personnel record
            updated = await contact_repo.update_contact(conn, customer_id, contact_id, contact_data)

            if not updated:
                raise HTTPException(status_code=404, detail="Contact not found")

        logger.info(f"Updated personnel {contact_id} for customer {customer_id}")
        return {"message": "Contact updated successfully", "contact": updated}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating contact for customer {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating contact: {str(e)}")


async def delete_contact(conn: asyncpg.Connection, customer_id: int, contact_id: str) -> Dict[str, Any]:
    """
    Delete a personnel record.

    Args:
        conn: asyncpg connection
        customer_id: Customer ID
        contact_id: Personnel UUID (string)

    Returns:
        Success message

    Raises:
        HTTPException: If deletion fails or contact not found
    """
    try:
        success = await contact_repo.delete_contact(conn, customer_id, contact_id)

        if not success:
            raise HTTPException(status_code=404, detail="Contact not found")

        logger.info(f"Deleted personnel {contact_id} from customer {customer_id}")
        return {"message": "Contact deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting contact from customer {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting contact: {str(e)}")


async def set_primary_contact(conn: asyncpg.Connection, customer_id: int, contact_id: str) -> Dict[str, Any]:
    """
    Set a personnel record as the primary contact for a customer.

    Args:
        conn: asyncpg connection
        customer_id: Customer ID
        contact_id: Personnel UUID (string)

    Returns:
        Success message

    Raises:
        HTTPException: If operation fails or contact not found
    """
    try:
        success = await contact_repo.set_primary_contact(conn, customer_id, contact_id)

        if not success:
            raise HTTPException(status_code=404, detail="Contact not found")

        logger.info(f"Set personnel {contact_id} as primary for customer {customer_id}")
        return {"message": "Primary contact updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting primary contact for customer {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error setting primary contact: {str(e)}")
