from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
import logging

from service_core.db import get_tenant_connection

# Import service modules
from services import contact_service
from services.cache_service import clear_cache

# Import contact helpers
from utils.contact_helpers import validate_contact

# Import models
from models.crm_models import Contact

logger = logging.getLogger(__name__)
router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════
# CONTACT MANAGEMENT ENDPOINTS (backed by personnel table)
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/customers/{customer_id}/contacts")
async def add_contact_endpoint(customer_id: int, contact_data: Contact, tenant: tuple = Depends(get_tenant_connection)) -> Dict[str, Any]:
    """Add a new personnel record linked to a customer"""
    conn, user = tenant
    logger.info(f"ADD contact request: customer_id={customer_id}, contact_name={contact_data.name}")

    # Prepare contact data
    new_contact_data = contact_data.dict()

    # Validate contact
    is_valid, error_msg = validate_contact(new_contact_data)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid contact data: {error_msg}")

    # Add contact via service (inserts into personnel table)
    result = await contact_service.add_contact(conn, customer_id, new_contact_data)

    # Clear cache
    clear_cache(f"get_customer_by_id:{customer_id}")
    clear_cache("get_all_customers")

    created = result.get('contact', {})
    logger.info(f"Contact added successfully: {created.get('personnel_id')}")
    return {"success": True, "contact": created}

@router.put("/customers/{customer_id}/contacts/{contact_id}")
async def update_contact_endpoint(customer_id: int, contact_id: str, contact_data: Contact, tenant: tuple = Depends(get_tenant_connection)) -> Dict[str, Any]:
    """Update an existing personnel record"""
    conn, user = tenant
    logger.info(f"UPDATE contact request: customer_id={customer_id}, contact_id={contact_id}")

    # Prepare updated contact data
    updated_contact_data = contact_data.dict()

    # Validate contact
    is_valid, error_msg = validate_contact(updated_contact_data)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid contact data: {error_msg}")

    # Update contact via service (updates personnel table)
    result = await contact_service.update_contact(conn, customer_id, contact_id, updated_contact_data)

    # Clear cache
    clear_cache(f"get_customer_by_id:{customer_id}")
    clear_cache("get_all_customers")

    logger.info(f"Contact updated successfully: {contact_id}")
    return {"success": True, "contact": result.get('contact')}

@router.delete("/customers/{customer_id}/contacts/{contact_id}")
async def delete_contact_endpoint(customer_id: int, contact_id: str, tenant: tuple = Depends(get_tenant_connection)) -> Dict[str, Any]:
    """Delete a personnel record (cannot delete primary contact if it's the only one)"""
    conn, user = tenant
    logger.info(f"DELETE contact request: customer_id={customer_id}, contact_id={contact_id}")

    # Get current contacts to validate
    contacts = await contact_service.get_contacts_for_customer(conn, customer_id)

    # Find contact to delete
    contact_to_delete = None
    for contact in contacts:
        if str(contact.get('personnel_id')) == contact_id:
            contact_to_delete = contact
            break

    if not contact_to_delete:
        raise HTTPException(status_code=404, detail="Contact not found")

    # Prevent deleting the only contact
    if len(contacts) == 1:
        raise HTTPException(status_code=400, detail="Cannot delete the only contact. Customer must have at least one contact.")

    # Prevent deleting primary contact if there are other contacts
    if contact_to_delete.get('is_primary'):
        raise HTTPException(status_code=400, detail="Cannot delete primary contact. Please set another contact as primary first.")

    # Delete contact via service (deletes from personnel table)
    result = await contact_service.delete_contact(conn, customer_id, contact_id)

    # Clear cache
    clear_cache(f"get_customer_by_id:{customer_id}")
    clear_cache("get_all_customers")

    logger.info(f"Contact deleted successfully: {contact_id}")
    return {"success": True, "message": "Contact deleted successfully"}

@router.put("/customers/{customer_id}/contacts/{contact_id}/set-primary")
async def set_primary_contact_endpoint(customer_id: int, contact_id: str, tenant: tuple = Depends(get_tenant_connection)) -> Dict[str, Any]:
    """Set a personnel record as the primary contact"""
    conn, user = tenant
    logger.info(f"SET PRIMARY contact request: customer_id={customer_id}, contact_id={contact_id}")

    # Set primary contact via service (updates personnel table)
    result = await contact_service.set_primary_contact(conn, customer_id, contact_id)

    # Clear cache
    clear_cache(f"get_customer_by_id:{customer_id}")
    clear_cache("get_all_customers")

    logger.info(f"Primary contact set successfully: {contact_id}")
    return {"success": True, "message": "Primary contact updated successfully"}
