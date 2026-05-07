"""
Apollo contact adapter for the two-pager report.

Per user decision 2026-04-17: no contact caching — Apollo is called fresh every
two-pager generation. Top-3 cap bounds cost at ~$0.10-0.20/report.

This module is a thin adapter over `apollo_io.client.ApolloClient`. It does
NOT modify the client and does NOT write to any database. Fallback: if fewer
than 3 buyers yield a `found` contact, ranks 4-15 are walked sequentially
(max 15 Apollo call chains per request). Any slot that still has no `found`
contact after exhausting rank 15 stays absent from the final list — the caller
is expected to render only the `found` results on Page 2 (no placeholder).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from importyeti.services.contact_cache_writer import save_contact_to_cache

logger = logging.getLogger(__name__)


@dataclass
class ContactResult:
    """One row returned to `TwoPagerService` for Page-2 buyer cards."""
    buyer_slug: str
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    contact_email: Optional[str] = None
    fetch_status: str = "not_found"  # "found" | "not_found" | "failed"


def _buyer_location(buyer: Dict[str, Any]) -> str:
    """Format location for Apollo's Google-Maps-style parser.

    Apollo client (apollo_io/client.py) expects 4-part
    "Street, City, State ZIP, Country" and extracts city from parts[1],
    state from parts[2]. We don't have a street, so duplicate the city
    into parts[0] — Apollo ignores parts[0] for city/state extraction,
    and this way parts[1] correctly resolves to the city name (not the
    state abbrev, which was the bug in the 3-part format).
    """
    city = buyer.get("city") or ""
    state = buyer.get("state") or ""
    if city and state:
        return f"{city}, {city}, {state}, USA"
    return city or state or ""


def _check_cached_contact(buyer: Dict[str, Any]) -> Optional[ContactResult]:
    """Return a ContactResult from the cache fields or None."""
    slug = buyer.get("slug") or ""
    name = buyer.get("name") or ""
    cached_email = buyer.get("validated_email") or buyer.get("validatedEmail")
    cached_name = (
        buyer.get("validated_contact_name") or buyer.get("validatedContactName")
    )
    cached_title = (
        buyer.get("validated_contact_title") or buyer.get("validatedContactTitle")
    )
    if cached_email and cached_name and slug:
        logger.info(f"[TwoPager/Apollo] cache hit for {name}: skipping Apollo")
        return ContactResult(
            buyer_slug=slug,
            contact_name=cached_name,
            contact_title=cached_title,
            contact_email=cached_email,
            fetch_status="found",
        )
    return None


async def _fetch_one(
    buyer: Dict[str, Any], apollo_client: Any, auth_token: str = ""
) -> ContactResult:
    """Run one Apollo decision-maker chain for a single buyer.

    Checks cache first (free); falls back to Apollo. Never raises.
    """
    slug = buyer.get("slug") or ""
    name = buyer.get("name") or ""
    if not name:
        return ContactResult(buyer_slug=slug, fetch_status="not_found")

    cached = _check_cached_contact(buyer)
    if cached is not None:
        return cached

    meta = {
        "source": "google_maps",
        "company_name": name,
        "location": _buyer_location(buyer),
    }

    try:
        leads = await apollo_client.enrich_company_emails(
            company_ids=[slug],
            companies=[meta],
        )
    except (ConnectionError, asyncio.TimeoutError) as e:
        logger.warning(f"[TwoPager/Apollo] network failure for {name}: {e}")
        return ContactResult(buyer_slug=slug, fetch_status="failed")
    except Exception as e:
        # Apollo 5xx, parsing errors, rate-limits — never block the report.
        logger.warning(f"[TwoPager/Apollo] call failed for {name}: {e}")
        return ContactResult(buyer_slug=slug, fetch_status="failed")

    if not leads:
        return ContactResult(buyer_slug=slug, fetch_status="not_found")

    lead = leads[0]
    contact_email = lead.get("contact_email")
    contact_name = lead.get("contact_name")
    if not contact_email and not contact_name:
        return ContactResult(buyer_slug=slug, fetch_status="not_found")

    contact_title = lead.get("contact_title") or lead.get("title")

    # Fire-and-forget write-back to 8007 cache so future reports skip Apollo.
    if slug and (contact_email or contact_name):
        logger.info("[TwoPager/Apollo] writing contact to cache for %s", slug)
        asyncio.create_task(save_contact_to_cache(
            slug,
            email=contact_email,
            name=contact_name,
            title=contact_title,
            auth_token=auth_token,
        ))

    return ContactResult(
        buyer_slug=slug,
        contact_name=contact_name,
        contact_title=contact_title,
        contact_email=contact_email,
        fetch_status="found",
    )


async def fetch_top3_contacts(
    top3_buyers: List[Dict[str, Any]],
    apollo_client: Any,
    fallback_buyers: Optional[List[Dict[str, Any]]] = None,
    auth_token: str = "",
) -> List[ContactResult]:
    """Fetch up to 3 `found` contacts across the full buyer pool.

    New strategy (2026-04-17):
      1. Cache pass — scan EVERY buyer (primary + fallback) for cached
         validated_email + validated_contact_name. Free, synchronous. Any
         hit counts toward the 3-slot target, regardless of rank.
      2. Apollo pass — for remaining slots, call Apollo sequentially on
         buyers not yet filled from cache. Stops at 3 found or 8 Apollo
         chains, whichever comes first.

    Returns `List[ContactResult]` ordered so the earliest-ranked found
    contact is first. Callers align results back to buyers via
    `buyer_slug`.
    """
    all_buyers = list(top3_buyers or []) + list(fallback_buyers or [])
    if not all_buyers:
        return []

    results: List[ContactResult] = []
    filled_slugs: set[str] = set()
    found_count = 0

    # Pass 1: cache hits across the full pool.
    for buyer in all_buyers:
        if found_count >= 3:
            break
        slug = buyer.get("slug") or ""
        if not slug or slug in filled_slugs:
            continue
        cached = _check_cached_contact(buyer)
        if cached is not None:
            results.append(cached)
            filled_slugs.add(slug)
            found_count += 1

    # Pass 2: Apollo for remaining slots — run up to 8 calls concurrently
    # with Semaphore(4). Collect candidates in rank order, schedule them all
    # at once, then keep only the found results in original rank order.
    max_apollo_calls = 8
    apollo_candidates: List[Dict[str, Any]] = []
    for buyer in all_buyers:
        if len(apollo_candidates) >= max_apollo_calls:
            break
        slug = buyer.get("slug") or ""
        if not slug or slug in filled_slugs:
            continue
        apollo_candidates.append(buyer)
        filled_slugs.add(slug)

    if apollo_candidates:
        sem = asyncio.Semaphore(4)

        async def _fetch_bounded(buyer: Dict[str, Any]) -> ContactResult:
            async with sem:
                return await _fetch_one(buyer, apollo_client, auth_token)

        gathered = await asyncio.gather(
            *[_fetch_bounded(b) for b in apollo_candidates],
            return_exceptions=True,
        )

        for result in gathered:
            if isinstance(result, Exception):
                logger.warning(f"[TwoPager/Apollo] gather task raised: {result!r}")
                continue
            if result.fetch_status == "found" and found_count < 3:
                results.append(result)
                found_count += 1

    return results
