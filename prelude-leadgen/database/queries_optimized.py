"""
Optimized database query functions for batch operations.

All functions are async and take an asyncpg connection as first parameter.
Uses $1, $2, ... positional placeholders (asyncpg).
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


async def save_enrichment_history_batch(conn, enrichments: List[Dict[str, Any]], employee_id: int) -> bool:
    """
    Batch insert enrichment history records.

    OPTIMIZED: Uses asyncpg executemany for fast batch inserts.

    Args:
        conn: asyncpg connection
        enrichments: List of enrichment data dicts
        employee_id: Employee ID to associate records with

    Returns:
        True if successful

    Example:
        enrichments = [
            {
                'company_name': 'Company A',
                'apollo_company_id': '123',
                'website': 'https://companya.com',
                ...
            },
            ...
        ]
        await save_enrichment_history_batch(conn, enrichments, employee_id=42)
    """
    if not enrichments:
        logger.debug("No enrichments to save")
        return True

    try:
        query = """
            INSERT INTO enrichment_history (
                session_id, company_name, apollo_company_id, website,
                location, industry, company_size,
                contact_name, contact_title, contact_email, contact_phone,
                enrichment_source, enrichment_status, enrichment_cost_credits,
                final_score, employee_id, created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, NOW())
        """

        # Build list of tuples for executemany
        rows = []
        for data in enrichments:
            rows.append((
                data.get('session_id'),
                data.get('company_name'),
                data.get('apollo_company_id'),
                data.get('website'),
                data.get('location'),
                data.get('industry'),
                data.get('company_size'),
                data.get('contact_name'),
                data.get('contact_title'),
                data.get('contact_email'),
                data.get('contact_phone'),
                data.get('enrichment_source', 'apollo'),
                data.get('enrichment_status', 'success'),
                data.get('enrichment_cost_credits', 1),
                data.get('final_score'),
                employee_id
            ))

        await conn.executemany(query, rows)
        logger.info(f"Batch inserted {len(enrichments)} enrichment history records")
        return True

    except Exception as e:
        logger.error(f"Error in batch insert enrichment history: {e}")
        return False


async def batch_check_companies_exist(conn, company_names: List[str]) -> Dict[str, bool]:
    """
    Check if multiple companies exist in database.

    OPTIMIZED: Single query instead of N queries (100x faster).

    Args:
        conn: asyncpg connection
        company_names: List of company names to check

    Returns:
        Dict mapping company name to exists boolean

    Example:
        result = await batch_check_companies_exist(conn, ["Company A", "Company B"])
        # {'Company A': True, 'Company B': False}
    """
    if not company_names:
        return {}

    try:
        query = """
            SELECT DISTINCT company
            FROM leads
            WHERE company = ANY($1)
        """

        rows = await conn.fetch(query, company_names)
        existing_companies = {row['company'] for row in rows}

        # Build result dict
        result = {name: name in existing_companies for name in company_names}
        return result

    except Exception as e:
        logger.error(f"Error in batch check companies: {e}")
        return {name: False for name in company_names}
