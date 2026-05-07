"""Enrichment helpers for buyer reports (two-pager)."""

from __future__ import annotations

import asyncio
from typing import Dict, List

from importyeti.domain.transformers import (
    compute_supplier_company_yoy,
    normalize_supplier_breakdown,
)


async def deep_enrich_buyers(*, client, companies: List[Dict], auth_token: str, logger) -> Dict[str, Dict]:
    results = {}
    semaphore = asyncio.Semaphore(5)

    async def _enrich_one(comp: Dict):
        async with semaphore:
            slug = comp["slug"]
            try:
                response = await client.get_company_detail(slug)
                raw = response.data or {}
                suppliers_table = raw.get("suppliers_table")
                # Normalise the raw `suppliers_table` into the supplier_breakdown
                # shape that downstream scoring + two-pager helpers expect
                # (transformers.py:14-40 — keys like `weight_kg`, `shipments`,
                # `teu`). The raw shape uses `total_weight`, `total_shipments_company`,
                # `total_teus` — compute paths like `_china_concentration` read
                # `weight_kg` and would silently return 0 on raw rows.
                if isinstance(suppliers_table, list):
                    supplier_breakdown = normalize_supplier_breakdown(suppliers_table)
                else:
                    supplier_breakdown = None
                supplier_count = (
                    len(suppliers_table) if isinstance(suppliers_table, list) else None
                )
                time_series = raw.get("time_series")
                trend_yoy = None
                if time_series and isinstance(time_series, dict):
                    yoy = compute_supplier_company_yoy(time_series)
                    if yoy is not None:
                        trend_yoy = round(yoy * 100, 1)
                results[slug] = {
                    "supplier_count": supplier_count,
                    "trend_yoy": trend_yoy,
                    "supplier_breakdown": supplier_breakdown,
                    "time_series": time_series if isinstance(time_series, dict) else None,
                    "most_recent_shipment": raw.get("most_recent_shipment"),
                    "company_total_shipments": raw.get("company_total_shipments"),
                }

                if auth_token:
                    # Delegate the cache write to BolSearchService.enrich_company so the
                    # row gets a proper detail_enriched payload — including enriched_score
                    # and scoring_signals — built from the same `raw` we just fetched.
                    # Avoids the historical leak where this writer set detail_enriched
                    # without a score (the 134-row anomaly in prelude_lead_db).
                    try:
                        from importyeti.buyers.service import BolSearchService
                        await BolSearchService().enrich_company(
                            slug, auth_token, prefetched_detail=raw,
                        )
                    except Exception as cache_err:
                        logger.warning(f"[TwoPager] Buyer enrich write failed for {slug}: {cache_err}")
            except Exception as e:
                logger.warning(f"[TwoPager] Deep enrich failed for {slug}: {e}")

    gathered = await asyncio.gather(*[_enrich_one(c) for c in companies], return_exceptions=True)
    for comp, result in zip(companies, gathered):
        if isinstance(result, Exception):
            logger.warning(f"[TwoPager] enrich task raised for {comp.get('slug')}: {result!r}")
    return results


