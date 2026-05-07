"""
Data fetchers for initial outreach email generation (BoL leads).

Fetches lead data from the leads table (with LEFT JOIN to personnel for email).
Shared user-level data (writing_style, audience_context, email_samples) is
imported from CRM's existing fetchers.
"""

import logging
from typing import Dict, List

from email_core.delivery.signature_formatter import fetch_employee_signature
from email_service.outreach.bol_intelligence import build_bol_intelligence
from email_service.data.fetchers import (
    fetch_email_samples,
    fetch_employee_writing_style,
    fetch_audience_context,
)

logger = logging.getLogger(__name__)


async def batch_fetch_leads(conn, lead_ids: List[str]) -> Dict[str, dict]:
    """Batch fetch lead data for multiple leads in single query."""
    if not lead_ids:
        return {}

    try:
        rows = await conn.fetch("""
            SELECT
                l.lead_id,
                l.company,
                p.full_name AS contact_name,
                p.email,
                p.phone,
                l.industry,
                l.location,
                l.website,
                l.company_size,
                l.revenue,
                l.status,
                l.created_at,
                l.updated_at,
                l.import_context,
                l.supplier_context
            FROM leads l
            LEFT JOIN LATERAL (
                SELECT email, phone, full_name FROM personnel
                WHERE lead_id = l.lead_id AND email IS NOT NULL
                ORDER BY is_primary DESC NULLS LAST, created_at DESC LIMIT 1
            ) p ON true
            WHERE l.lead_id = ANY($1::uuid[])
        """, lead_ids)

        result = {}
        for row in rows:
            lead_data = dict(row)
            lead_id = str(lead_data['lead_id'])
            lead_data['lead_id'] = lead_id

            result[lead_id] = {
                'lead_id': lead_id,
                'company': lead_data.get('company') or "Unknown Company",
                'name': lead_data.get('contact_name') or "Unknown Contact",
                'email': lead_data.get('email') or "",
                'phone': lead_data.get('phone') or "",
                'industry': lead_data.get('industry') or "Business",
                'location': lead_data.get('location') or "",
                'website': lead_data.get('website') or "",
                'company_size': lead_data.get('company_size') or "Unknown",
                'revenue': lead_data.get('revenue') or "Unknown",
                'status': lead_data.get('status') or "new",
                'import_context': lead_data.get('import_context'),
                'supplier_context': lead_data.get('supplier_context'),
            }

        logger.info(f"Batch fetched {len(result)} leads")
        return result

    except Exception as e:
        logger.error(f"Error batch fetching leads: {e}")
        return {}


async def batch_build_email_generation_payloads(
    conn,
    lead_ids: List[str],
    user_email: str
) -> Dict[str, dict]:
    """
    Batch build email generation payloads for multiple leads.
    Uses batch queries to minimize database round-trips.

    Returns dict mapping lead_id -> payload
    """
    logger.info(f"Batch building outreach payloads for {len(lead_ids)} leads")

    # Batch fetch lead data
    all_leads = await batch_fetch_leads(conn, lead_ids)

    # Fetch shared data once (from CRM's existing fetchers).
    # Sequential calls — `conn` is a single asyncpg Connection and cannot
    # multiplex; concurrent fetches on it would raise "another operation is
    # in progress".
    email_samples = await fetch_email_samples(conn, user_email)
    writing_style = await fetch_employee_writing_style(conn, user_email)
    audience_context = await fetch_audience_context(conn)
    signature_data = await fetch_employee_signature(user_email, conn)

    # Build payloads for each lead
    payloads = {}
    for lid in lead_ids:
        lead_data = all_leads.get(lid)
        if not lead_data:
            logger.warning(f"No lead data found for {lid}")
            continue

        # Build BoL buyer intelligence from import_context + supplier_context.
        # `score` is the per-lead readiness score (0–100) — surfaces as "Buyer fit".
        buyer_intelligence = build_bol_intelligence(
            lead_data.get('import_context'),
            lead_data.get('supplier_context'),
            score=lead_data.get('score'),
        )

        payloads[lid] = {
            'lead_data': lead_data,
            'email_history': [],  # No history for initial outreach
            'email_samples': email_samples,
            'writing_style': writing_style,
            'audience_context': audience_context,
            'buyer_intelligence': buyer_intelligence,
            'signature_data': signature_data,
        }

    logger.info(f"Built {len(payloads)} outreach payloads with batch prefetching")
    return payloads
