"""Signature formatting utility for email generation (asyncpg).

Reads structured signature fields from employee_info.signature_fields JSONB
and renders as HTML. Hardcoded styles: 12px text, 50px logo height.

Post-processes generated emails to append user signatures.
"""

import html
import json
import logging
import re
from typing import Optional, Dict

import asyncpg

from email_core.config import settings

logger = logging.getLogger(__name__)


async def fetch_employee_signature(
    user_email: str, conn: asyncpg.Connection
) -> Optional[Dict]:
    """Fetch structured signature fields from employee_info.signature_fields JSONB.

    Returns:
        A dict matching the SignatureFields shape, or None if not set or unreadable.
    """
    try:
        row = await conn.fetchrow(
            """
            SELECT signature_fields
            FROM employee_info
            WHERE email = $1
            """,
            user_email,
        )
    except asyncpg.exceptions.UndefinedColumnError:
        # Defensive read for the rolling-deploy window after the schema migration.
        # Removed in a follow-up PR once the deploy stabilizes.
        # Pattern matches prelude-leadgen/importyeti/contracts/subscription.py:446-456.
        logger.warning(
            f"signature_fields column not present for {user_email}; rolling deploy in flight?"
        )
        return None
    except Exception as e:
        logger.error(f"Error fetching signature for {user_email}: {e}")
        return None

    if not row or not row['signature_fields']:
        logger.debug(f"No signature found for {user_email}")
        return None

    # asyncpg returns JSONB as either a dict or a string depending on how it was
    # written. Project convention (utils/json_helpers.parse_jsonb): normalize.
    raw = row['signature_fields']
    try:
        fields = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"signature.read.malformed_jsonb for {user_email}: {e}")
        return None
    if not isinstance(fields, dict):
        logger.error(
            f"signature.read.malformed_jsonb for {user_email}: type={type(fields).__name__}"
        )
        return None

    return fields


def format_signature_html(fields: Dict) -> str:
    """Render structured signature fields as HTML (12px text, 50px logo)."""
    parts = ['<div style="margin-top: 20px; font-size: 12px; line-height: 1.6;">']
    if fields.get('name'):
        parts.append(f'{html.escape(fields["name"])}<br/>')
    if fields.get('title'):
        parts.append(f'{html.escape(fields["title"])}<br/>')
    if fields.get('email'):
        e = html.escape(fields['email'])
        parts.append(
            f'<a href="mailto:{e}" '
            f'style="color:#2563eb;text-decoration:underline;">{e}</a><br/>'
        )
    if fields.get('phoneNumber'):
        parts.append(f'{html.escape(fields["phoneNumber"])}<br/>')
    if fields.get('location'):
        parts.append(f'{html.escape(fields["location"])}<br/>')
    if fields.get('link'):
        lnk = html.escape(fields['link'])
        parts.append(
            f'<a href="{lnk}" '
            f'style="color:#2563eb;text-decoration:underline;" '
            f'target="_blank">{lnk}</a>'
        )
    parts.append('</div>')

    if fields.get('logoUrl'):
        url = fields['logoUrl']
        if not (url.startswith('http://') or url.startswith('https://')):
            url = f"{settings.user_settings_url}{url}"
        parts.append(
            f'<img src="{html.escape(url)}" alt="Signature" '
            f'style="height:50px;margin-top:8px;display:block;" />'
        )

    return ''.join(parts)


async def attach_signature_to_email(
    result: Dict,
    user_email: str,
    conn: asyncpg.Connection = None,
    signature_data: Optional[Dict] = None,
) -> Dict:
    """Append the user's signature to a generated email.

    Call AFTER LLM generation, BEFORE returning to the frontend. Pass
    pre-fetched ``signature_data`` (from ``fetch_employee_signature``) to skip
    the DB query in batch generation.
    """
    try:
        if signature_data is None and conn is not None:
            signature_data = await fetch_employee_signature(user_email, conn)

        if not signature_data:
            logger.debug(f"No signature to append for {user_email}")
            return result

        body = result.get('email_data', {}).get('body', '')

        if not body:
            logger.warning("Email body is empty, cannot append signature")
            return result

        # Safety net: strip trailing sign-off if model generated one
        # (the signature block already represents the closing).
        body = re.sub(
            r'\n(Regards|Best regards|Thanks|Thank you|Cheers|Sincerely|Kind regards|Warm regards),?\s*$',
            '',
            body,
            flags=re.IGNORECASE,
        ).rstrip()

        signature_html = format_signature_html(signature_data)
        result['email_data']['body'] = f"{body}\n{signature_html}"

        logger.info(f"Signature appended for {user_email}")
        return result

    except Exception as e:
        logger.error(f"Failed to attach signature for {user_email}: {e}")
        return result
