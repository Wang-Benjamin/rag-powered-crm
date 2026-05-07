"""
Contact helper functions for managing multiple contacts per customer.
Provides utilities for validation, synchronization, and data manipulation.
"""

import json
import uuid
import re
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


def generate_contact_id() -> str:
    """
    Generate UUID for contact.
    
    Returns:
        UUID string
    """
    return str(uuid.uuid4())


def sync_legacy_fields_from_contacts(contacts: List[Dict]) -> Dict[str, Optional[str]]:
    """
    Extract primary contact info for legacy fields.
    
    Args:
        contacts: List of contact dictionaries
        
    Returns:
        Dictionary with keys: primary_contact, email, phone
    """
    if not contacts:
        return {
            'primary_contact': None,
            'email': None,
            'phone': None
        }
    
    # Find primary contact
    primary = None
    for contact in contacts:
        if contact.get('is_primary'):
            primary = contact
            break
    
    # If no primary found, use first contact
    if not primary and contacts:
        primary = contacts[0]
    
    if not primary:
        return {
            'primary_contact': None,
            'email': None,
            'phone': None
        }
    
    return {
        'primary_contact': primary.get('name', ''),
        'email': primary.get('email', ''),
        'phone': primary.get('phone', '')
    }


def create_contact_from_legacy(
    primary_contact: Optional[str], 
    email: Optional[str], 
    phone: Optional[str]
) -> Dict:
    """
    Create contact object from legacy fields.
    
    Args:
        primary_contact: Contact name
        email: Contact email
        phone: Contact phone
        
    Returns:
        Contact dictionary
    """
    now = datetime.now(timezone.utc).isoformat()
    
    return {
        'id': generate_contact_id(),
        'name': primary_contact or '',
        'email': email or '',
        'phone': phone or '',
        'title': '',
        'is_primary': True,
        'notes': '',
        'created_at': now,
        'updated_at': now
    }


def validate_contact(contact: Dict) -> Tuple[bool, Optional[str]]:
    """
    Validate contact data.
    
    Args:
        contact: Contact dictionary
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Required fields
    if not contact.get('name') or not str(contact.get('name')).strip():
        return False, "Contact name is required"
    
    if not contact.get('email') or not str(contact.get('email')).strip():
        return False, "Contact email is required"
    
    # Email format validation
    email = str(contact['email']).strip()
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, email):
        return False, "Invalid email format"
    
    # Phone format validation (if provided) - lenient to allow various formats
    if contact.get('phone'):
        phone = str(contact['phone']).strip()
        # Allow: digits, spaces, hyphens, parentheses, dots, plus sign, and extension markers
        # Minimum 7 characters to support local numbers, max 30 for international with extensions
        if phone and not re.match(r'^[+]?[\d\s\-().ext#*]{7,30}$', phone, re.IGNORECASE):
            return False, "Invalid phone format"
    
    return True, None


def parse_contacts_json(contacts_json: Any) -> List[Dict]:
    """
    Safely parse contacts JSON field from database.
    
    Args:
        contacts_json: Raw contacts data from database (could be string, list, dict, or None)
        
    Returns:
        List of contact dictionaries
    """
    if contacts_json is None:
        return []
    
    # If already a list, return it
    if isinstance(contacts_json, list):
        return contacts_json
    
    # If it's a string, try to parse it
    if isinstance(contacts_json, str):
        try:
            parsed = json.loads(contacts_json)
            if isinstance(parsed, list):
                return parsed
            return []
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"Failed to parse contacts JSON: {contacts_json}")
            return []
    
    # If it's a dict (shouldn't happen but handle it)
    if isinstance(contacts_json, dict):
        return [contacts_json]
    
    return []


def ensure_primary_contact(contacts: List[Dict]) -> List[Dict]:
    """
    Ensure exactly one contact is marked as primary.
    If no primary exists, set first contact as primary.
    If multiple primaries exist, keep only the first one.
    
    Args:
        contacts: List of contact dictionaries
        
    Returns:
        Updated list of contacts with exactly one primary
    """
    if not contacts:
        return contacts
    
    # Find all primary contacts
    primary_indices = [i for i, c in enumerate(contacts) if c.get('is_primary')]
    
    if not primary_indices:
        # No primary found, set first as primary
        contacts[0]['is_primary'] = True
    elif len(primary_indices) > 1:
        # Multiple primaries, keep only the first one
        for i in primary_indices[1:]:
            contacts[i]['is_primary'] = False
    
    return contacts


def add_timestamps_to_contact(contact: Dict, is_new: bool = True) -> Dict:
    """
    Add or update timestamps on contact.
    
    Args:
        contact: Contact dictionary
        is_new: If True, sets created_at. Always updates updated_at.
        
    Returns:
        Contact with timestamps
    """
    now = datetime.now(timezone.utc).isoformat()
    
    if is_new:
        contact['created_at'] = now
    
    contact['updated_at'] = now
    
    return contact


def serialize_contacts_for_db(contacts: List[Dict]) -> str:
    """
    Serialize contacts list to JSON string for database storage.
    
    Args:
        contacts: List of contact dictionaries
        
    Returns:
        JSON string
    """
    try:
        return json.dumps(contacts)
    except (TypeError, ValueError) as e:
        logger.error(f"Failed to serialize contacts: {e}")
        return "[]"


def find_contact_by_id(contacts: List[Dict], contact_id: str) -> Tuple[Optional[Dict], int]:
    """
    Find contact by ID in contacts list.
    
    Args:
        contacts: List of contact dictionaries
        contact_id: Contact ID to find
        
    Returns:
        Tuple of (contact_dict, index) or (None, -1) if not found
    """
    for i, contact in enumerate(contacts):
        if contact.get('id') == contact_id:
            return contact, i
    
    return None, -1


def set_contact_as_primary(contacts: List[Dict], contact_id: str) -> List[Dict]:
    """
    Set specified contact as primary and unset all others.
    
    Args:
        contacts: List of contact dictionaries
        contact_id: ID of contact to set as primary
        
    Returns:
        Updated contacts list
    """
    for contact in contacts:
        contact['is_primary'] = (contact.get('id') == contact_id)
    
    return contacts

