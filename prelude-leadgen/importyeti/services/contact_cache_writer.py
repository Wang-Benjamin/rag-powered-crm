"""Shared helper for writing Apollo-validated contacts to bol_companies.

Used by: two-pager (contact_adapter), CSV onboarding (lead_enrichment), and
future flows. Wraps internal_bol_client.update_enrichment with the
validated_email / validated_contact_name / validated_contact_title fields.

Fire-and-forget safe — returns bool, never raises.
"""

import logging
from typing import Optional

from importyeti.clients import internal_bol_client

logger = logging.getLogger(__name__)


async def save_contact_to_cache(
    slug: str,
    *,
    email: Optional[str],
    name: Optional[str],
    title: Optional[str],
    auth_token: str = "",
) -> bool:
    """Persist an Apollo contact to bol_companies.validated_* columns.

    Only writes when `email` is present — name-only / title-only outcomes
    are not cached so the next run re-attempts Apollo/Lemlist instead of
    serving a stale negative.

    Returns True on success, False on any failure or skipped write (caller
    should treat as advisory — never block on this).
    """
    if not email or not slug:
        return False
    payload: dict = {"validated_email": email}
    if name:
        payload["validated_contact_name"] = name
    if title:
        payload["validated_contact_title"] = title
    logger.info(
        "[ContactCache] writing contact to cache for %s (email=%s, name=%s, title=%s)",
        slug, bool(email), bool(name), bool(title),
    )
    return await internal_bol_client.update_enrichment(slug, payload, auth_token=auth_token)
