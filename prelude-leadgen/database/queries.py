"""
Database queries for lead deduplication.

Functions to check existing leads and prevent duplicates during
Apollo preview searches.

All functions are async and take an asyncpg connection as first parameter.
Uses $1, $2, ... positional placeholders (asyncpg).
"""

import logging
from typing import Set

from data.connection import get_tenant_conn

logger = logging.getLogger(__name__)


def normalize_company_name(name: str, strip_location: bool = False) -> str:
    """
    Normalize company name for deduplication comparison.

    Uses aggressive normalization to match variations like:
    - "Commercial Machine Service" vs "COMMERCIAL MACHINE SERVICE, INC."
    - "Mc Kean Machinery" vs "MCKEAN MACHINERY"
    - "O'Brien Company" vs "OBrien Company"
    - "Towlift, Inc. Cleveland Facility" vs "Towlift, Inc." (when strip_location=True)

    Args:
        name: Raw company name
        strip_location: If True, removes location-specific suffixes like "Cleveland Facility"

    Returns:
        Normalized name (lowercase, no spaces, no punctuation, no suffixes)
    """
    if not name:
        return ""

    normalized = name.strip()

    # Strip location suffixes BEFORE other normalization (if enabled)
    # "Towlift, Inc. Cleveland Facility" -> "Towlift, Inc."
    if strip_location:
        location_suffixes = [
            'facility', 'facilities', 'location', 'branch', 'division',
            'office', 'center', 'centre', 'plant', 'warehouse', 'depot',
            'headquarters', 'hq', 'campus'
        ]

        # Split by spaces to check for patterns like "{City} {Suffix}"
        words = normalized.split()
        if len(words) >= 2:
            # Check if last word is a location suffix
            last_word = words[-1].lower()
            if last_word in location_suffixes:
                # Remove last 1-2 words (e.g., "Cleveland Facility")
                # Try removing last 2 words first (city + suffix)
                if len(words) >= 3:
                    normalized = ' '.join(words[:-2])
                else:
                    # Only suffix present, remove it
                    normalized = ' '.join(words[:-1])

    # Remove punctuation FIRST
    normalized = normalized.rstrip('.,')
    normalized = normalized.replace('.', '').replace(',', '').replace('-', '').replace("'", '')

    # Remove ALL spaces for aggressive matching
    # "Mc Kean Machinery" -> "McKeanMachinery"
    normalized = normalized.replace(' ', '')

    # Convert to lowercase BEFORE suffix removal
    normalized = normalized.lower()

    # Remove common suffixes (case-insensitive, no spaces)
    # "commercialmachineserviceinc" -> "commercialmachineservice"
    suffixes = [
        'inc', 'llc', 'ltd',
        'corporation', 'corp',
        'company', 'co',
        'incorporated'
    ]

    for suffix in suffixes:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)]

    # Remove trailing 's' for plural normalization
    # "services" -> "service"
    if len(normalized) > 4 and normalized.endswith('s') and not normalized.endswith('ss'):
        normalized = normalized[:-1]

    return normalized.strip()


def get_company_name_variants(name: str) -> list:
    """
    Get multiple normalized variants of a company name for progressive matching.

    Returns variants in order of preference:
    1. Exact normalized match (strict)
    2. Core name with location suffix stripped (relaxed)

    Args:
        name: Raw company name

    Returns:
        List of (variant_name, match_type) tuples in order of preference
        Example: [("towlift", "exact"), ("towlift", "core")]
    """
    if not name:
        return []

    variants = []

    # Variant 1: Exact normalized match (current behavior)
    exact = normalize_company_name(name, strip_location=False)
    variants.append((exact, "exact"))

    # Variant 2: Core name with location suffix stripped
    core = normalize_company_name(name, strip_location=True)
    # Only add if different from exact
    if core != exact:
        variants.append((core, "core"))

    return variants


async def get_existing_company_names(conn, user_email: str = None) -> Set[str]:
    """
    Get set of company names already in the database.

    Used for deduplication during preview search - filters out ALL companies
    in the database to avoid duplicates across all users.

    Args:
        conn: asyncpg connection
        user_email: User identifier (not used - checks all companies)

    Returns:
        Set of normalized company names (lowercase, trimmed)
    """
    try:
        query = """
            SELECT DISTINCT company
            FROM leads
            WHERE company IS NOT NULL
            AND company != ''
        """

        rows = await conn.fetch(query)

        # Apply Python normalization function to each company name
        company_names = {normalize_company_name(row['company']) for row in rows if row['company']}

        logger.info(f"Found {len(company_names)} existing companies in database (all users): {list(company_names)[:10]}{'...' if len(company_names) > 10 else ''}")
        return company_names

    except Exception as e:
        logger.error(f"Error fetching existing company names: {e}")
        # Return empty set on error - won't block preview search
        return set()


async def get_enriched_company_names_for_user(conn, user_email: str) -> Set[str]:
    """
    Get set of company names from enrichment history for a specific user.

    Used for deduplication during preview search - filters out companies
    that the current user has already enriched.

    Args:
        conn: asyncpg connection
        user_email: Email of the current user

    Returns:
        Set of normalized company names (lowercase, trimmed) from enrichment history
    """
    try:
        # First get employee_id from email
        employee_id = await get_employee_id_by_email(conn, user_email)
        if not employee_id:
            logger.warning(f"No employee_id found for email {user_email}, skipping enrichment history check")
            return set()

        query = """
            SELECT DISTINCT company_name
            FROM enrichment_history
            WHERE employee_id = $1
            AND company_name IS NOT NULL
            AND company_name != ''
        """

        rows = await conn.fetch(query, employee_id)

        # Apply Python normalization function to each company name
        company_names = {normalize_company_name(row['company_name']) for row in rows if row['company_name']}

        logger.info(f"Found {len(company_names)} enriched companies for user {user_email}: {list(company_names)[:10]}{'...' if len(company_names) > 10 else ''}")
        return company_names

    except Exception as e:
        logger.error(f"Error fetching enriched company names for user: {e}")
        # Return empty set on error - won't block preview search
        return set()


def is_duplicate(company_name: str, existing_names: Set[str]) -> bool:
    """
    Check if a company name is a duplicate.

    Args:
        company_name: Company name to check
        existing_names: Set of existing normalized company names

    Returns:
        True if duplicate, False if unique
    """
    normalized = normalize_company_name(company_name)
    return normalized in existing_names


async def save_enrichment_history(conn, enrichment_data: dict, employee_id: int) -> bool:
    """
    Save enrichment history record to the database.

    Note: ON CONFLICT clause removed due to missing unique constraint.
    This will create a new record for each enrichment attempt.

    Args:
        conn: asyncpg connection
        enrichment_data: Dict containing enrichment details
        employee_id: ID of the employee who performed the enrichment

    Returns:
        True if successful, False otherwise
    """
    try:
        query = """
            INSERT INTO enrichment_history (
                employee_id, session_id, company_name, apollo_company_id,
                website, location, industry, company_size,
                contact_name, contact_title, contact_email, contact_phone,
                enrichment_source, enrichment_status, enrichment_cost_credits,
                final_score, search_intent_industry, search_intent_location,
                search_intent_keywords, workflow_id
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20
            )
        """

        await conn.execute(query,
            employee_id,
            enrichment_data.get('session_id'),
            enrichment_data.get('company_name'),
            enrichment_data.get('apollo_company_id'),
            enrichment_data.get('website'),
            enrichment_data.get('location'),
            enrichment_data.get('industry'),
            enrichment_data.get('company_size'),
            enrichment_data.get('contact_name'),
            enrichment_data.get('contact_title'),
            enrichment_data.get('contact_email'),
            enrichment_data.get('contact_phone'),
            enrichment_data.get('enrichment_source', 'apollo'),
            enrichment_data.get('enrichment_status', 'success'),
            enrichment_data.get('enrichment_cost_credits', 0),
            enrichment_data.get('final_score'),
            enrichment_data.get('search_intent_industry'),
            enrichment_data.get('search_intent_location'),
            enrichment_data.get('search_intent_keywords'),
            enrichment_data.get('workflow_id')
        )

        logger.info(f"Saved enrichment history for company: {enrichment_data.get('company_name')}")
        return True

    except Exception as e:
        logger.error(f"Error saving enrichment history: {e}")
        return False


async def get_employee_id_by_email(conn, email: str) -> int:
    """
    Get employee_id from employee_info table by email.

    Args:
        conn: asyncpg connection (to the user's tenant database)
        email: Employee email address

    Returns:
        Employee ID, or None if not found
    """
    try:
        query = """
            SELECT employee_id
            FROM employee_info
            WHERE email = $1
            LIMIT 1
        """

        row = await conn.fetchrow(query, email)

        if row:
            logger.info(f"Found employee_id {row['employee_id']} for {email}")
            return row['employee_id']
        else:
            logger.warning(f"No employee found with email: {email}")
            return None

    except Exception as e:
        logger.error(f"Error fetching employee_id by email: {e}")
        return None


async def get_enrichment_history_count(conn, employee_id: int) -> int:
    """
    Get total count of enrichment history records for a specific employee.

    Args:
        conn: asyncpg connection
        employee_id: ID of the employee

    Returns:
        Total count of records
    """
    try:
        query = """
            SELECT COUNT(*) as total
            FROM enrichment_history
            WHERE employee_id = $1
        """

        result = await conn.fetchrow(query, employee_id)
        return result['total'] if result else 0

    except Exception as e:
        logger.error(f"Error fetching enrichment history count: {e}")
        return 0


async def get_enrichment_history(conn, employee_id: int, limit: int = 20, offset: int = 0) -> list:
    """
    Get enrichment history for a specific employee with pagination.

    Args:
        conn: asyncpg connection
        employee_id: ID of the employee
        limit: Maximum number of records to return
        offset: Number of records to skip

    Returns:
        List of enrichment history records
    """
    try:
        query = """
            SELECT
                id, employee_id, session_id, company_name, apollo_company_id,
                website, location, industry, company_size,
                contact_name, contact_title, contact_email, contact_phone,
                enrichment_source, enrichment_status, enrichment_cost_credits,
                final_score, search_intent_industry, search_intent_location,
                search_intent_keywords, workflow_id, is_saved_to_leads,
                created_at, updated_at
            FROM enrichment_history
            WHERE employee_id = $1
            ORDER BY updated_at DESC
            LIMIT $2 OFFSET $3
        """

        rows = await conn.fetch(query, employee_id, limit, offset)

        results = []
        for row in rows:
            record = dict(row)
            # Convert datetime to string for JSON serialization
            if record.get('created_at'):
                record['created_at'] = record['created_at'].isoformat()
            if record.get('updated_at'):
                record['updated_at'] = record['updated_at'].isoformat()
            results.append(record)

        logger.info(f"Retrieved {len(results)} enrichment history records for employee {employee_id}")
        return results

    except Exception as e:
        logger.error(f"Error fetching enrichment history: {e}")
        return []


async def get_monthly_token_usage_by_leads(conn, user_email: str) -> int:
    """
    Get monthly token usage by counting enrichment history records with contact emails.

    Each enrichment_history record with a VALID contact_email created this month counts as 1 token.
    Excludes placeholder emails like email_not_unlocked@domain.com.

    Args:
        conn: asyncpg connection
        user_email: Email of the user

    Returns:
        Number of tokens used this month (count of enrichment records with valid emails)
    """
    try:
        # First get employee_id from email
        employee_id = await get_employee_id_by_email(conn, user_email)
        if not employee_id:
            logger.warning(f"No employee_id found for email {user_email}, returning 0 tokens")
            return 0

        query = """
            SELECT COUNT(*)
            FROM enrichment_history
            WHERE employee_id = $1
              AND contact_email IS NOT NULL
              AND contact_email != ''
              AND contact_email NOT LIKE '%not_unlocked%'
              AND contact_email NOT LIKE '%@domain.com'
              AND created_at >= date_trunc('month', CURRENT_DATE)
        """

        result = await conn.fetchrow(query, employee_id)

        token_count = result['count'] if result else 0
        logger.info(f"User {user_email} (employee_id={employee_id}) has used {token_count} tokens this month from enrichment history (excluding placeholders)")
        return token_count

    except Exception as e:
        logger.error(f"Error fetching monthly token usage: {e}")
        return 0
