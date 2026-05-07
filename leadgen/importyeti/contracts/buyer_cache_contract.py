"""Shared buyer-cache writer used by BoL search and one-pager warming.

After migration 009a the cache_state table is gone — per-HS metrics live on
bol_companies.hs_metrics JSONB and cache-state metadata is no longer tracked.
This helper now only forwards the buyer rows and their search_result entries
to the server in batches.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from importyeti.clients import internal_bol_client


async def save_buyer_cache_batches(
    *,
    companies: List[Dict[str, Any]],
    search_results: List[Dict[str, Any]],
    auth_token: str,
    batch_size: int = 50,
) -> bool:
    """Write buyer rows + per-HS metrics in batches.

    The first batch runs serially; remaining batches fire in parallel.
    """
    saved_all_batches = True

    if companies:
        batches = []
        for i in range(0, len(companies), batch_size):
            batch_companies = companies[i:i + batch_size]
            slugs = {company["importyeti_slug"] for company in batch_companies}
            batch_results = [
                result for result in search_results
                if result.get("importyeti_slug") in slugs
            ]
            batches.append((batch_companies, batch_results))

        if batches:
            first_companies, first_results = batches[0]
            first_saved = await internal_bol_client.save_to_cache(
                companies=first_companies,
                search_results=first_results,
                auth_token=auth_token,
            )
            saved_all_batches = saved_all_batches and first_saved

        if len(batches) > 1:
            rest_results = await asyncio.gather(*(
                internal_bol_client.save_to_cache(
                    companies=bc,
                    search_results=br,
                    auth_token=auth_token,
                )
                for bc, br in batches[1:]
            ))
            saved_all_batches = saved_all_batches and all(rest_results)
    elif search_results:
        saved_all_batches = await internal_bol_client.save_to_cache(
            companies=[],
            search_results=search_results,
            auth_token=auth_token,
        )

    return saved_all_batches


async def write_buyer_cache_batch(
    *,
    companies: List[Dict[str, Any]],
    search_results: List[Dict[str, Any]],
    auth_token: str,
) -> bool:
    return await save_buyer_cache_batches(
        companies=companies,
        search_results=search_results,
        auth_token=auth_token,
        batch_size=max(len(companies), 1),
    )
