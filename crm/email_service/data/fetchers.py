"""Data fetchers for email generation (asyncpg)."""

import json
import logging
import os
from typing import Dict, List, Optional

import asyncpg
import httpx
from fastapi import HTTPException

from email_core.generation.trade_voice import TRADE_VOICE_PRESET, TRADE_EMAIL_SAMPLES

logger = logging.getLogger(__name__)


def safe_json_loads(json_str, default=None):
    """Safely parse JSON string."""
    if json_str is None:
        return default or {}
    try:
        if isinstance(json_str, str):
            return json.loads(json_str)
        return json_str
    except (json.JSONDecodeError, TypeError):
        return default or {}


# ===== BATCH PREFETCH FUNCTIONS (CORE IMPLEMENTATIONS) =====
# These functions fetch data for multiple customers in single queries.
# Individual fetchers call these with single-item lists.


async def batch_fetch_customers(
    customer_ids: List[int], conn: asyncpg.Connection
) -> Dict[int, dict]:
    """Batch fetch customer data for multiple customers in single query."""
    if not customer_ids:
        return {}

    try:
        rows = await conn.fetch(
            """
            SELECT
                ci.client_id,
                ci.name,
                p_primary.full_name as primary_contact,
                p_primary.email,
                ci.phone,
                ci.location,
                ci.website,
                ci.status
            FROM clients ci
            LEFT JOIN LATERAL (
                SELECT full_name, email FROM personnel
                WHERE client_id = ci.client_id
                ORDER BY is_primary DESC NULLS LAST
                LIMIT 1
            ) p_primary ON true
            WHERE ci.client_id = ANY($1)
            """,
            customer_ids,
        )

        result = {}
        for row in rows:
            result[row['client_id']] = {
                'client_id': row['client_id'],
                'company': row['name'] or "Unknown Company",
                'primary_contact': row['primary_contact'] or "Unknown Contact",
                'email': row['email'] or "",
                'phone': row['phone'] or "",
                'location': row['location'] or "",
                'website': row['website'] or "",
                'status': row['status'] or "active",
            }

        logger.info(f"Batch fetched {len(result)} customers")
        return result

    except Exception as e:
        logger.error(f"Error batch fetching customers: {e}")
        return {}


async def batch_fetch_insights(
    customer_ids: List[int], conn: asyncpg.Connection
) -> Dict[int, dict]:
    """Batch fetch insights for multiple customers in single query."""
    if not customer_ids:
        return {}

    try:
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (customer_id)
                customer_id,
                summary_data,
                generated_at,
                period_analyzed_days,
                interactions_analyzed,
                status
            FROM interaction_summaries
            WHERE customer_id = ANY($1)
              AND status = 'success'
            ORDER BY customer_id, generated_at DESC
            """,
            customer_ids,
        )

        result = {row['customer_id']: dict(row) for row in rows}

        logger.info(f"Batch fetched insights for {len(result)} customers")
        return result

    except Exception as e:
        logger.warning(f"Error batch fetching insights: {e}")
        return {}


async def batch_fetch_notes(
    customer_ids: List[int],
    employee_id: Optional[int],
    conn: asyncpg.Connection,
) -> Dict[int, List[dict]]:
    """Batch fetch notes for multiple customers in single query."""
    if not customer_ids:
        return {}

    try:
        if employee_id is not None:
            rows = await conn.fetch(
                """
                SELECT
                    client_id,
                    note_id,
                    title,
                    body,
                    created_at,
                    star
                FROM employee_client_notes
                WHERE client_id = ANY($1)
                  AND employee_id = $2
                ORDER BY client_id, created_at DESC
                """,
                customer_ids,
                employee_id,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT
                    client_id,
                    note_id,
                    title,
                    body,
                    created_at,
                    star
                FROM employee_client_notes
                WHERE client_id = ANY($1)
                ORDER BY client_id, created_at DESC
                """,
                customer_ids,
            )

        # Group by customer_id, limit 10 per customer
        result: Dict[int, List[dict]] = {}
        for row in rows:
            cid = row['client_id']
            if cid not in result:
                result[cid] = []
            if len(result[cid]) < 10:
                result[cid].append(dict(row))

        logger.info(f"Batch fetched notes for {len(result)} customers")
        return result

    except Exception as e:
        logger.warning(f"Error batch fetching notes: {e}")
        return {}


async def batch_fetch_interactions(
    customer_ids: List[int],
    employee_id: Optional[int],
    conn: asyncpg.Connection,
) -> Dict[int, List[dict]]:
    """Batch fetch past interactions for multiple customers in single query."""
    if not customer_ids:
        return {}

    try:
        interactions_by_customer: Dict[int, List[dict]] = {cid: [] for cid in customer_ids}

        # 1. Fetch emails from crm_emails
        if employee_id is not None:
            email_rows = await conn.fetch(
                """
                SELECT
                    ce.email_id as interaction_id,
                    ce.customer_id,
                    'email' as type,
                    ce.body as content,
                    ce.direction,
                    ce.subject,
                    ce.created_at,
                    NULL::text as theme,
                    NULL::text as source,
                    e.name as employee_name,
                    e.role as employee_role,
                    ce.conversation_state
                FROM crm_emails ce
                LEFT JOIN employee_info e ON ce.employee_id = e.employee_id
                WHERE ce.customer_id = ANY($1) AND ce.employee_id = $2
                ORDER BY ce.customer_id, ce.created_at DESC
                """,
                customer_ids,
                employee_id,
            )
        else:
            email_rows = await conn.fetch(
                """
                SELECT
                    ce.email_id as interaction_id,
                    ce.customer_id,
                    'email' as type,
                    ce.body as content,
                    ce.direction,
                    ce.subject,
                    ce.created_at,
                    NULL::text as theme,
                    NULL::text as source,
                    e.name as employee_name,
                    e.role as employee_role,
                    ce.conversation_state
                FROM crm_emails ce
                LEFT JOIN employee_info e ON ce.employee_id = e.employee_id
                WHERE ce.customer_id = ANY($1)
                ORDER BY ce.customer_id, ce.created_at DESC
                """,
                customer_ids,
            )

        for row in email_rows:
            cid = row['customer_id']
            interactions_by_customer[cid].append(dict(row))

        # 2. Fetch non-email interactions from interaction_details
        if employee_id is not None:
            other_rows = await conn.fetch(
                """
                SELECT
                    i.interaction_id,
                    i.customer_id,
                    i.type,
                    i.content,
                    i.created_at,
                    i.theme,
                    i.source,
                    e.name as employee_name,
                    e.role as employee_role
                FROM interaction_details i
                LEFT JOIN employee_info e ON i.employee_id = e.employee_id
                WHERE i.customer_id = ANY($1) AND i.employee_id = $2
                  AND i.type != 'note' AND i.type != 'email'
                ORDER BY i.customer_id, i.created_at DESC
                """,
                customer_ids,
                employee_id,
            )
        else:
            other_rows = await conn.fetch(
                """
                SELECT
                    i.interaction_id,
                    i.customer_id,
                    i.type,
                    i.content,
                    i.created_at,
                    i.theme,
                    i.source,
                    e.name as employee_name,
                    e.role as employee_role
                FROM interaction_details i
                LEFT JOIN employee_info e ON i.employee_id = e.employee_id
                WHERE i.customer_id = ANY($1)
                  AND i.type != 'note' AND i.type != 'email'
                ORDER BY i.customer_id, i.created_at DESC
                """,
                customer_ids,
            )

        for row in other_rows:
            cid = row['customer_id']
            interactions_by_customer[cid].append(dict(row))

        # Sort and limit each customer's interactions
        result = {}
        for cid, interactions in interactions_by_customer.items():
            if interactions:
                interactions.sort(key=lambda x: x['created_at'], reverse=True)
                result[cid] = interactions[:20]

        logger.info(f"Batch fetched interactions for {len(result)} customers")
        return result

    except Exception as e:
        logger.warning(f"Error batch fetching interactions: {e}")
        return {}


async def batch_build_email_generation_payloads(
    customer_ids: List[int],
    conn: asyncpg.Connection,
    employee_id: Optional[int],
    user_email: str = None,
) -> Dict[int, dict]:
    """
    Batch build email generation payloads for multiple customers.
    Uses batch queries to minimize database round-trips.

    Returns dict mapping customer_id -> payload
    """
    logger.info(f"Batch building payloads for {len(customer_ids)} customers")

    # Batch fetch all data types
    all_customers = await batch_fetch_customers(customer_ids, conn)
    all_insights = await batch_fetch_insights(customer_ids, conn)
    all_notes = await batch_fetch_notes(customer_ids, employee_id, conn)
    all_interactions = await batch_fetch_interactions(customer_ids, employee_id, conn)

    # Fetch shared data once (filter by user_email to get correct employee's style)
    from email_core.delivery.signature_formatter import fetch_employee_signature
    email_samples = await fetch_email_samples(conn, user_email)
    writing_style = await fetch_employee_writing_style(conn, user_email)
    audience_context = await fetch_audience_context(conn)
    signature_data = await fetch_employee_signature(user_email, conn)

    # Build payloads for each customer
    payloads = {}
    for cid in customer_ids:
        customer_data = all_customers.get(cid)
        if not customer_data:
            logger.warning(f"No customer data found for {cid}")
            continue

        payloads[cid] = {
            'customer_data': customer_data,
            'insights': all_insights.get(cid),
            'email_samples': email_samples,
            'notes': all_notes.get(cid, []),
            'past_interactions': all_interactions.get(cid, []),
            'writing_style': writing_style,
            'audience_context': audience_context,
            'signature_data': signature_data,
        }

    logger.info(f"Built {len(payloads)} payloads with batch prefetching")
    return payloads


# ===== INDIVIDUAL FETCHERS (WRAPPERS AROUND BATCH FUNCTIONS) =====


async def fetch_customer_data(customer_id: int, conn: asyncpg.Connection) -> dict:
    """Fetch customer data from the clients table."""
    result = await batch_fetch_customers([customer_id], conn)
    if customer_id not in result:
        raise HTTPException(status_code=404, detail="Customer not found")
    return result[customer_id]


async def fetch_customer_insights(
    customer_id: int, conn: asyncpg.Connection
) -> Optional[dict]:
    """Fetch AI-generated customer insights from interaction_summaries table."""
    result = await batch_fetch_insights([customer_id], conn)
    insight = result.get(customer_id)
    if insight:
        logger.info(
            f"Found insights for customer {customer_id}: "
            f"{insight.get('period_analyzed_days')} days, "
            f"{insight.get('interactions_analyzed')} interactions"
        )
    else:
        logger.info(f"No insights found for customer {customer_id}")
    return insight


async def fetch_notes(
    customer_id: int, employee_id: Optional[int], conn: asyncpg.Connection
) -> List[dict]:
    """Fetch employee notes from employee_client_notes table."""
    result = await batch_fetch_notes([customer_id], employee_id, conn)
    return result.get(customer_id, [])


async def fetch_past_interactions(
    customer_id: int, employee_id: Optional[int], conn: asyncpg.Connection
) -> List[dict]:
    """Fetch past interactions from crm_emails and interaction_details tables."""
    result = await batch_fetch_interactions([customer_id], employee_id, conn)
    return result.get(customer_id, [])


async def build_email_generation_payload(
    customer_id: int,
    conn: asyncpg.Connection,
    employee_id: Optional[int],
    user_email: str = None,
) -> dict:
    """Orchestrate all data fetches for email generation."""
    logger.info(f"Building email generation payload for customer {customer_id}")
    payloads = await batch_build_email_generation_payloads(
        [customer_id], conn, employee_id, user_email=user_email
    )

    if customer_id not in payloads:
        raise HTTPException(status_code=404, detail="Customer not found")

    payload = payloads[customer_id]
    has_insights = "YES" if payload.get('insights') else "NO"
    has_style = "YES" if payload.get('writing_style') else "NO"
    logger.info(
        f"Payload built: {len(payload.get('notes', []))} notes, "
        f"{len(payload.get('past_interactions', []))} interactions, "
        f"{len(payload.get('email_samples', []))} samples, "
        f"insights: {has_insights}, Writing style: {has_style}"
    )

    return payload


# ===== SHARED USER-LEVEL FETCHERS =====


async def fetch_audience_context(conn: asyncpg.Connection) -> Optional[dict]:
    """Fetch company profile, factory details, HS codes, and certifications for email generation context."""
    try:
        row = await conn.fetchrow(
            "SELECT company_profile, factory_details, hs_codes FROM tenant_subscription LIMIT 1"
        )

        if not row:
            return None

        company_profile = row.get('company_profile') or {}
        factory_details = row.get('factory_details') or {}
        hs_codes = row.get('hs_codes') or []

        if isinstance(company_profile, str):
            company_profile = json.loads(company_profile)
        if isinstance(factory_details, str):
            factory_details = json.loads(factory_details)
        if isinstance(hs_codes, str):
            hs_codes = json.loads(hs_codes)

        if not company_profile and not factory_details and not hs_codes:
            return None

        context = {
            "company_name": company_profile.get("company_name_en", ""),
            "product_description": company_profile.get("product_description_en", company_profile.get("product_description", "")),
            "hs_codes": [c.get("code", "") + " — " + c.get("description", "") for c in hs_codes if c.get("confirmed")],
            "capacity": factory_details.get("capacity", ""),
            "lead_time_default": factory_details.get("lead_time", ""),
            "moq_default": str(factory_details.get("moq", "")) if factory_details.get("moq") else "",
            "year_established": str(factory_details.get("year_established", "")) if factory_details.get("year_established") else "",
            "employees": str(factory_details.get("employees", "")) if factory_details.get("employees") else "",
            "factory_area_sqm": str(factory_details.get("factory_area_sqm", "")) if factory_details.get("factory_area_sqm") else "",
        }

        try:
            cert_rows = await conn.fetch(
                "SELECT DISTINCT cert_type, issuing_body, expiry_date FROM factory_certifications "
                "WHERE status = 'active'"
            )
            if cert_rows:
                context["certifications"] = [
                    {"name": r["cert_type"], "issuer": r.get("issuing_body", ""), "expiry": str(r["expiry_date"]) if r.get("expiry_date") else ""}
                    for r in cert_rows
                ]
        except Exception:
            pass

        logger.info("Fetched company profile + factory context")
        return context

    except Exception as e:
        logger.warning(f"Failed to fetch audience context: {e}")
        return None


async def fetch_email_samples(conn: asyncpg.Connection, user_email: str = None) -> List[dict]:
    """Fetch email samples from employee_info.training_emails.
    Falls back to TRADE_EMAIL_SAMPLES when no training emails exist."""
    try:
        if user_email:
            row = await conn.fetchrow(
                "SELECT training_emails FROM employee_info WHERE email = $1", user_email
            )
        else:
            row = await conn.fetchrow(
                "SELECT training_emails FROM employee_info LIMIT 1"
            )

        if not row or not row.get('training_emails'):
            logger.info("No training emails found, using trade voice preset")
            return list(TRADE_EMAIL_SAMPLES)

        return row['training_emails']

    except Exception as e:
        logger.warning(f"Error fetching email samples: {e}")
        return list(TRADE_EMAIL_SAMPLES)


async def fetch_employee_writing_style(conn: asyncpg.Connection, user_email: str = None) -> Optional[dict]:
    """Fetch employee writing style from database.
    Falls back to TRADE_VOICE_PRESET when no writing style exists."""
    try:
        if user_email:
            row = await conn.fetchrow(
                "SELECT writing_style FROM employee_info WHERE email = $1", user_email
            )
        else:
            row = await conn.fetchrow(
                "SELECT writing_style FROM employee_info LIMIT 1"
            )

        if not row or not row.get('writing_style'):
            logger.info("No writing style found, using trade voice preset")
            return dict(TRADE_VOICE_PRESET)

        writing_style = row['writing_style']
        if isinstance(writing_style, str):
            writing_style = json.loads(writing_style)

        logger.info("Fetched writing style")
        return writing_style

    except Exception as e:
        logger.warning(f"Failed to fetch writing style: {e}")
        return dict(TRADE_VOICE_PRESET)


async def update_employee_writing_style_after_send(
    conn: asyncpg.Connection, user_email: str, emails: List[dict]
) -> None:
    """Update employee writing style after emails sent."""
    try:
        from datetime import datetime, timezone

        if not emails:
            return

        row = await conn.fetchrow(
            """
            SELECT employee_id, writing_style
            FROM employee_info
            WHERE email = $1
            """,
            user_email,
        )

        if not row:
            logger.warning(f"No employee found for {user_email}")
            return

        employee_id = row['employee_id']
        existing_style = row['writing_style']

        if existing_style and isinstance(existing_style, str):
            existing_style = json.loads(existing_style)

        logger.info(f"Updating writing style for employee {employee_id} with {len(emails)} new emails")

        emails_for_analysis = emails.copy()

        if existing_style and existing_style.get('examples'):
            for example in existing_style['examples'][:3]:
                emails_for_analysis.append({
                    'subject': '(Previous email)',
                    'body': example,
                })
            logger.info(
                f"Including {min(3, len(existing_style['examples']))} examples from existing style"
            )

        from email_core.writing_style import analyze_writing_style
        from email_core.config import settings as email_settings

        style_data = await analyze_writing_style(emails_for_analysis)

        style_data['metadata'] = {
            'lastUpdated': datetime.now(timezone.utc).isoformat(),
            'emailsSampled': len(emails),
            'model': email_settings.writing_style_model,
        }

        await conn.execute(
            """
            UPDATE employee_info
            SET writing_style = $1
            WHERE employee_id = $2
            """,
            style_data,
            employee_id,
        )

        logger.info(f"Writing style updated for {user_email} with {len(emails)} email(s)")

    except Exception as e:
        logger.warning(f"Failed to update writing style for {user_email}: {e}")


# ===== ENRICHED INTERACTIONS (SPECIALIZED) =====


async def fetch_customer_interactions_enriched(
    customer_id: int,
    employee_id: Optional[int],
    conn: asyncpg.Connection,
) -> List[Dict]:
    """
    Fetch ALL interactions for a customer with full enrichment.

    This is a specialized function with additional columns for timeline display.
    Not consolidated with batch functions due to different output format.
    """
    try:
        all_interactions_data = []

        # 1. Fetch emails from crm_emails table
        if employee_id:
            email_rows = await conn.fetch(
                """
                SELECT
                    ce.email_id as interaction_id,
                    ce.customer_id,
                    'email' as type,
                    ce.body as content,
                    ce.created_at,
                    ce.updated_at,
                    ce.message_id as gmail_message_id,
                    ce.message_id as email_id,
                    ce.subject as theme,
                    NULL::text as source,
                    e.name as employee_name,
                    e.role as employee_role,
                    e.department as employee_department,
                    NULL::text as source_name,
                    'unknown' as source_type,
                    0 as attachments,
                    NULL::int as duration,
                    ce.direction as outcome,
                    ce.subject as subject,
                    ce.direction as direction,
                    ce.from_email as from_email,
                    ce.to_email as to_email,
                    ce.thread_id as thread_id
                FROM crm_emails ce
                LEFT JOIN employee_info e ON ce.employee_id = e.employee_id
                WHERE ce.customer_id = $1 AND ce.employee_id = $2
                ORDER BY ce.created_at DESC
                """,
                customer_id,
                employee_id,
            )
        else:
            email_rows = await conn.fetch(
                """
                SELECT
                    ce.email_id as interaction_id,
                    ce.customer_id,
                    'email' as type,
                    ce.body as content,
                    ce.created_at,
                    ce.updated_at,
                    ce.message_id as gmail_message_id,
                    ce.message_id as email_id,
                    ce.subject as theme,
                    NULL::text as source,
                    e.name as employee_name,
                    e.role as employee_role,
                    e.department as employee_department,
                    NULL::text as source_name,
                    'unknown' as source_type,
                    0 as attachments,
                    NULL::int as duration,
                    ce.direction as outcome,
                    ce.subject as subject,
                    ce.direction as direction,
                    ce.from_email as from_email,
                    ce.to_email as to_email,
                    ce.thread_id as thread_id
                FROM crm_emails ce
                LEFT JOIN employee_info e ON ce.employee_id = e.employee_id
                WHERE ce.customer_id = $1
                ORDER BY ce.created_at DESC
                """,
                customer_id,
            )

        all_interactions_data.extend([dict(row) for row in email_rows])

        # 2. Fetch non-email interactions from interaction_details table
        if employee_id:
            other_rows = await conn.fetch(
                """
                SELECT
                    i.interaction_id,
                    i.customer_id,
                    i.type,
                    i.content,
                    i.created_at,
                    i.updated_at,
                    i.gmail_message_id,
                    i.theme,
                    i.source,
                    e.name as employee_name,
                    e.role as employee_role,
                    e.department as employee_department,
                    CASE
                        WHEN i.source IS NOT NULL AND i.source ~ '^[0-9]+$' THEN
                            COALESCE(
                                (SELECT c.name FROM clients c WHERE c.client_id = CAST(i.source AS INTEGER)),
                                (SELECT emp.name FROM employee_info emp WHERE emp.employee_id = CAST(i.source AS INTEGER)),
                                i.source
                            )
                        ELSE i.source
                    END as source_name,
                    CASE
                        WHEN i.source IS NOT NULL AND i.source ~ '^[0-9]+$' THEN
                            CASE
                                WHEN EXISTS (SELECT 1 FROM clients c WHERE c.client_id = CAST(i.source AS INTEGER)) THEN 'customer'
                                WHEN EXISTS (SELECT 1 FROM employee_info emp WHERE emp.employee_id = CAST(i.source AS INTEGER)) THEN 'employee'
                                ELSE 'unknown'
                            END
                        ELSE 'unknown'
                    END as source_type,
                    0 as attachments,
                    CASE
                        WHEN i.type = 'call' THEN 30
                        WHEN i.type = 'meeting' THEN 60
                        ELSE NULL
                    END as duration,
                    CASE
                        WHEN i.type = 'call' THEN 'Connected'
                        WHEN i.type = 'meeting' THEN 'Completed'
                        ELSE NULL
                    END as outcome,
                    NULL::text as subject,
                    NULL::text as direction,
                    NULL::text as from_email,
                    NULL::text as to_email
                FROM interaction_details i
                LEFT JOIN employee_info e ON i.employee_id = e.employee_id
                WHERE i.customer_id = $1 AND i.employee_id = $2 AND i.type NOT IN ('email', 'quote_request')
                ORDER BY i.created_at DESC
                """,
                customer_id,
                employee_id,
            )
        else:
            other_rows = await conn.fetch(
                """
                SELECT
                    i.interaction_id,
                    i.customer_id,
                    i.type,
                    i.content,
                    i.created_at,
                    i.updated_at,
                    i.gmail_message_id,
                    i.theme,
                    i.source,
                    e.name as employee_name,
                    e.role as employee_role,
                    e.department as employee_department,
                    CASE
                        WHEN i.source IS NOT NULL AND i.source ~ '^[0-9]+$' THEN
                            COALESCE(
                                (SELECT c.name FROM clients c WHERE c.client_id = CAST(i.source AS INTEGER)),
                                (SELECT emp.name FROM employee_info emp WHERE emp.employee_id = CAST(i.source AS INTEGER)),
                                i.source
                            )
                        ELSE i.source
                    END as source_name,
                    CASE
                        WHEN i.source IS NOT NULL AND i.source ~ '^[0-9]+$' THEN
                            CASE
                                WHEN EXISTS (SELECT 1 FROM clients c WHERE c.client_id = CAST(i.source AS INTEGER)) THEN 'customer'
                                WHEN EXISTS (SELECT 1 FROM employee_info emp WHERE emp.employee_id = CAST(i.source AS INTEGER)) THEN 'employee'
                                ELSE 'unknown'
                            END
                        ELSE 'unknown'
                    END as source_type,
                    0 as attachments,
                    CASE
                        WHEN i.type = 'call' THEN 30
                        WHEN i.type = 'meeting' THEN 60
                        ELSE NULL
                    END as duration,
                    CASE
                        WHEN i.type = 'call' THEN 'Connected'
                        WHEN i.type = 'meeting' THEN 'Completed'
                        ELSE NULL
                    END as outcome,
                    NULL::text as subject,
                    NULL::text as direction,
                    NULL::text as from_email,
                    NULL::text as to_email
                FROM interaction_details i
                LEFT JOIN employee_info e ON i.employee_id = e.employee_id
                WHERE i.customer_id = $1 AND i.type NOT IN ('email', 'quote_request')
                ORDER BY i.created_at DESC
                """,
                customer_id,
            )

        all_interactions_data.extend([dict(row) for row in other_rows])

        all_interactions_data.sort(key=lambda x: x['created_at'], reverse=True)

        if employee_id:
            logger.info(
                f"Found {len(all_interactions_data)} enriched interactions "
                f"for customer {customer_id} and employee {employee_id}"
            )
        else:
            logger.info(
                f"Found {len(all_interactions_data)} enriched interactions "
                f"for customer {customer_id} (all employees)"
            )

        return all_interactions_data

    except Exception as e:
        logger.error(f"Error fetching enriched interactions for customer {customer_id}: {e}")
        raise


# ===== TEMPLATE & CLIENT FETCHERS =====


async def fetch_template_from_settings(
    template_id: str, user_email: str, authorization: str = None
) -> dict:
    """Fetch a template from User Settings service by ID."""
    USER_SETTINGS_BASE_URL = os.getenv('USER_SETTINGS_URL', 'http://localhost:8005')
    async with httpx.AsyncClient() as http_client:
        response = await http_client.get(
            f"{USER_SETTINGS_BASE_URL}/api/settings/templates/{template_id}",
            params={"user_email": user_email},
            headers={"Authorization": authorization} if authorization else {},
        )
        response.raise_for_status()
        template = response.json()
        logger.info(f"Fetched template '{template.get('name')}' for generation")
        return template


async def fetch_clients_by_ids(
    client_ids: List[int], conn: asyncpg.Connection
) -> list:
    """Fetch client data from the clients table for mass email."""
    rows = await conn.fetch(
        """
        SELECT ci.client_id, ci.name, ci.phone,
               p.full_name as primary_contact,
               p.email
        FROM clients ci
        LEFT JOIN LATERAL (
            SELECT full_name, email FROM personnel
            WHERE client_id = ci.client_id
            ORDER BY is_primary DESC NULLS LAST, created_at ASC
            LIMIT 1
        ) p ON true
        WHERE ci.client_id = ANY($1)
        """,
        client_ids,
    )
    return [dict(row) for row in rows]
