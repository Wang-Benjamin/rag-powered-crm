"""
Internal Leads Sync Module

Silently copies all generated leads to prelude_internal_leads database for
internal analytics and tracking purposes. This is completely transparent to users.

Converted to asyncpg - uses get_tenant_conn from data.connection.
"""

import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from data.connection import get_tenant_conn

logger = logging.getLogger(__name__)

# Internal database name - centralized collection of all user leads
INTERNAL_LEADS_DB = "prelude_internal_leads"


async def copy_lead_to_internal_db(
    lead_data: Dict[str, Any],
    personnel_data: Optional[List[Dict[str, Any]]] = None,
    user_email: str = None,
    user_tenant_db: str = None
) -> bool:
    """
    Silently copy a lead and its personnel to the internal leads database.

    This function runs in the background after a lead is successfully saved
    to the user's tenant database. It's completely transparent to the user.

    Args:
        lead_data: Lead information (company, location, industry, etc.)
        personnel_data: List of personnel/contacts associated with the lead
        user_email: Email of the user who generated this lead
        user_tenant_db: The tenant database where the original lead was saved

    Returns:
        True if successful, False if failed (failures are logged but don't affect user)
    """
    try:
        # Allowed columns in internal DB leads table
        ALLOWED_LEAD_COLS = {
            'lead_id', 'company', 'location', 'industry', 'company_size', 'revenue',
            'employees_count', 'website',
            'status', 'score', 'source',
            'created_at', 'updated_at', 'source_user_email',
            'source_tenant_db', 'synced_at'
        }

        # Filter to only allowed columns and add metadata
        lead_data_copy = {k: v for k, v in lead_data.items() if k in ALLOWED_LEAD_COLS}
        lead_data_copy['source_user_email'] = user_email
        lead_data_copy['source_tenant_db'] = user_tenant_db
        lead_data_copy['synced_at'] = datetime.now(timezone.utc)

        # Connect to internal database
        async with get_tenant_conn(INTERNAL_LEADS_DB) as conn:
            # Build dynamic insert with $N placeholders
            lead_fields = list(lead_data_copy.keys())
            placeholders = [f"${i+1}" for i in range(len(lead_fields))]
            values = list(lead_data_copy.values())

            insert_lead_query = f"""
                INSERT INTO leads ({', '.join(lead_fields)})
                VALUES ({', '.join(placeholders)})
                ON CONFLICT (lead_id) DO UPDATE SET
                    updated_at = EXCLUDED.updated_at,
                    synced_at = EXCLUDED.synced_at
                RETURNING lead_id
            """

            result = await conn.fetchrow(insert_lead_query, *values)
            lead_id = result['lead_id'] if result else None

            # Insert personnel if provided
            if personnel_data and lead_id:
                for person in personnel_data:
                    person_copy = {}

                    # Transform field names to match internal DB schema:
                    # - first_name/last_name -> name
                    # - full_name -> name
                    # - position -> title
                    if 'first_name' in person or 'last_name' in person:
                        first = person.get('first_name', '') or ''
                        last = person.get('last_name', '') or ''
                        person_copy['name'] = f"{first} {last}".strip()
                    elif 'full_name' in person:
                        person_copy['name'] = person['full_name']

                    if 'position' in person:
                        person_copy['title'] = person['position']

                    # Copy only allowed fields from source
                    for key in ['email', 'phone', 'linkedin_url', 'department',
                                'seniority_level', 'is_decision_maker', 'notes',
                                'created_at', 'updated_at']:
                        if key in person:
                            person_copy[key] = person[key]

                    # Generate personnel_id if not present
                    person_copy['personnel_id'] = person.get('personnel_id') or str(uuid.uuid4())
                    person_copy['lead_id'] = lead_id
                    person_copy['source_user_email'] = user_email
                    person_copy['synced_at'] = datetime.now(timezone.utc)

                    person_fields = list(person_copy.keys())
                    person_placeholders = [f"${i+1}" for i in range(len(person_fields))]
                    person_values = list(person_copy.values())

                    insert_personnel_query = f"""
                        INSERT INTO personnel ({', '.join(person_fields)})
                        VALUES ({', '.join(person_placeholders)})
                        ON CONFLICT (personnel_id) DO UPDATE SET
                            updated_at = EXCLUDED.updated_at,
                            synced_at = EXCLUDED.synced_at
                    """

                    await conn.execute(insert_personnel_query, *person_values)

            logger.info(f"Internal sync: Lead {lead_id} copied to {INTERNAL_LEADS_DB} from user {user_email}")
            return True

    except Exception as e:
        # Log error but don't raise - internal sync failures shouldn't affect user experience
        logger.error(f"Internal sync failed: {e}")
        logger.error(f"Lead data: {lead_data.get('company', 'Unknown')} from user {user_email}")
        return False


async def bulk_copy_leads_to_internal_db(
    leads_data: List[Dict[str, Any]],
    user_email: str = None,
    user_tenant_db: str = None
) -> Dict[str, int]:
    """
    Bulk copy multiple leads to internal database.

    Args:
        leads_data: List of lead dictionaries (each may include 'personnel' key)
        user_email: Email of user who generated these leads
        user_tenant_db: Tenant database where leads were originally saved

    Returns:
        Dict with 'success' and 'failed' counts
    """
    success_count = 0
    failed_count = 0

    for lead in leads_data:
        # Extract personnel from lead data
        personnel = lead.pop('personnel', None)

        # Try to sync
        if await copy_lead_to_internal_db(lead, personnel, user_email, user_tenant_db):
            success_count += 1
        else:
            failed_count += 1

    logger.info(f"Internal bulk sync: {success_count} succeeded, {failed_count} failed for user {user_email}")

    return {
        'success': success_count,
        'failed': failed_count
    }
