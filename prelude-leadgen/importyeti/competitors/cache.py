"""Cache helpers for competitor onboarding and hydration."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List

from importyeti.clients import internal_bol_client


async def fetch_competitors_cached(
    *,
    hs_code: str,
    max_results: int,
    auth_token: str,
    logger,
) -> List[Dict[str, Any]]:
    """Fetch competitors from the 8007 cache for a single HS code.

    After migration 009a there is no separate cache_state table to consult —
    the cache is ops-populated via CSV ingest, so the staleness check is gone.
    """
    if max_results <= 0:
        return []

    cached = await internal_bol_client.search_competitor_cache(
        hs_codes=[hs_code],
        max_results=max_results,
        auth_token=auth_token,
    )
    return cached or []


async def hydrate_cached_competitors(
    *,
    conn,
    hs_code: str,
    competitors: List[Dict[str, Any]],
    known_slugs: set[str],
    competitor_limit: int,
    upsert_cached_competitor: Callable[..., Awaitable[None]],
) -> int:
    inserted = 0

    for competitor in competitors:
        slug = competitor.get("importyeti_slug") or competitor.get("supplier_slug") or competitor.get("slug")
        if not slug:
            continue

        if slug not in known_slugs and len(known_slugs) >= competitor_limit:
            break

        was_known = slug in known_slugs
        await upsert_cached_competitor(
            conn=conn,
            hs_code=hs_code,
            competitor=competitor,
            supplier_slug=slug,
        )
        known_slugs.add(slug)
        if not was_known:
            inserted += 1

    return inserted
