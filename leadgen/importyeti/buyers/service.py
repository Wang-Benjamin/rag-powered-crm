"""
BoL Search Service — CSV-only pipeline

Buyer search always serves from the internal cache (populated via CSV ingestion).
Deep enrich is available on-click via /importyeti/enrich/{slug}.
"""

import asyncio
import logging

from typing import Optional, List, Dict, Any

from importyeti.clients.api_client import ImportYetiClient
from importyeti.clients import internal_bol_client
from importyeti.domain.scoring import (
    compute_full_score,
    _signal_1_reorder_window, _signal_2_supplier_diversification,
    _signal_3_competitive_displacement, _signal_4_volume_fit,
    _signal_5_recency_activity, _signal_6_hs_relevance,
    _signal_7_shipment_scale, _signal_8_switching_velocity,
    _signal_9_buyer_growth, _signal_10_supply_chain_vulnerability,
    _signal_11_order_consistency,
)
from importyeti.domain.transformers import (
    normalize_supplier_breakdown,
    build_company_data,
    build_query_data,
    compute_china_concentration,
    compute_avg_order_cycle_days,
    compute_supplier_company_yoy,
    compute_growth_12m,
    compute_supplier_hhi,
    compute_order_regularity_cv,
    compute_china_concentration_12m,
    derive_most_recent_shipment,
)
from importyeti.contracts.subscription import (
    release_onboarding_buyer_ready_slots,
    reserve_onboarding_buyer_ready_slots,
    ONBOARDING_AUTO_ENRICH_CAP, ONBOARDING_BUYER_RESULT_LIMIT,
    update_onboarding_progress,
)
from importyeti.contracts.bol_contract import select_onboarding_deep_enrich_slugs
from utils.background_tasks import fire_tracked
from service_core.db import get_pool_manager

logger = logging.getLogger(__name__)


def _best_score(c: Dict[str, Any]) -> float:
    return (c.get("enriched_score") or c.get("enrichedScore")
            or c.get("quick_score") or c.get("quickScore") or 0)


def _derive_hs_metrics_from_bols(
    recent_bols: Optional[List[Dict[str, Any]]],
) -> Dict[str, Dict[str, Any]]:
    """Aggregate per-HS weight/teu/shipment counts from recent_bols.

    Each BoL in recent_bols carries `HS_Code`, `Weight_in_KG`, `TEU`. Groups
    by HS code and sums. Returns {} for missing/empty input so callers can
    safely spread this into their enrichment payload. Drops HS codes
    shorter than 6 digits — the repo layer would log-and-drop them anyway.
    """
    if not recent_bols:
        return {}
    agg: Dict[str, Dict[str, float]] = {}
    for bol in recent_bols:
        hs = (bol.get("HS_Code") or bol.get("hs_code") or "").strip()
        if not hs or len(hs) < 6:
            continue
        try:
            w = float(bol.get("Weight_in_KG") or bol.get("weight_in_kg") or 0)
        except (TypeError, ValueError):
            w = 0.0
        try:
            t = float(bol.get("TEU") or bol.get("teu") or 0)
        except (TypeError, ValueError):
            t = 0.0
        bucket = agg.setdefault(hs, {"matching_shipments": 0, "weight_kg": 0.0, "teu": 0.0})
        bucket["matching_shipments"] = int(bucket["matching_shipments"]) + 1
        bucket["weight_kg"] = float(bucket["weight_kg"]) + w
        bucket["teu"] = float(bucket["teu"]) + t
    # Convert to plain dicts with int/float types the backend expects.
    return {
        hs: {
            "matching_shipments": int(v["matching_shipments"]),
            "weight_kg": round(float(v["weight_kg"]), 2),
            "teu": round(float(v["teu"]), 2),
        }
        for hs, v in agg.items()
    }

SINGLEFLIGHT_WAIT_ATTEMPTS = 3
SINGLEFLIGHT_WAIT_SECONDS = 0.2


class BolSearchService:

    def __init__(self):
        self.client = ImportYetiClient()

    async def enrich_company(
        self,
        slug: str,
        auth_token: str,
        *,
        prefetched_detail: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Lazy deep-enrich a single company on click.
        Called from POST /importyeti/enrich/{slug}.

        Flow:
        1. Fetch cached company from internal DB
        2. If already detail_enriched, return cached (0 credits)
        3. Use prefetched_detail if caller already paid for /company/{company},
           otherwise call it ourselves (1 credit)
        4. Compute full score + signals
        5. Save enrichment to cache
        6. Return enriched company data
        """
        cached = await internal_bol_client.get_company(slug, auth_token=auth_token)
        if not cached:
            raise ValueError(f"Company not found in cache: {slug}")

        if cached.get("enrichment_status") == "detail_enriched":
            logger.info(f"[{slug}] Already detail_enriched, returning cached")
            return cached

        if prefetched_detail is not None:
            detail = prefetched_detail
        else:
            detail_response = await self.client.get_company_detail(slug)
            detail = detail_response.data if detail_response.data else {}

        if not detail:
            logger.warning(f"[{slug}] Company detail returned empty")
            return cached

        # Extract and normalize deep enrichment fields
        raw_suppliers = detail.get("suppliers_table") or []
        supplier_breakdown = normalize_supplier_breakdown(raw_suppliers)

        time_series = detail.get("time_series") or {}

        # Compute deep-enrichment scoring fields from time_series
        china_concentration = compute_china_concentration(time_series)
        avg_cycle = compute_avg_order_cycle_days(time_series)
        yoy = compute_supplier_company_yoy(time_series)
        growth = compute_growth_12m(time_series)
        hhi = compute_supplier_hhi(supplier_breakdown)
        cv = compute_order_regularity_cv(time_series)
        cn_12m = compute_china_concentration_12m(time_series)

        most_recent = cached.get("most_recent_shipment") or derive_most_recent_shipment(time_series)

        enrichment_data = {
            "most_recent_shipment": most_recent,
            "supplier_breakdown": supplier_breakdown,
            "time_series": time_series,
            "recent_bols": detail.get("recent_bols"),
            "also_known_names": detail.get("also_known_names"),
            "phone_number": detail.get("phone_number"),
            "website": detail.get("website"),
            # Per-HS aggregates derived from recent_bols. Persisted via
            # merge_hs_metrics_buyer on the internal-leads-db side — see
            # repositories/bol_company_repository.py update_enrichment().
            # Without this, detail_enriched rows end up with hs_metrics='{}'
            # and the frontend two-pager renders "—" for 年进口量.
            "hs_metrics": _derive_hs_metrics_from_bols(detail.get("recent_bols")),
        }

        # Merge into cached data for scoring
        merged = {**cached, **enrichment_data}

        # Prefer cached total_suppliers over len(supplier_breakdown), which is
        # capped at ~49 by ImportYeti's suppliers_table pagination.
        total_suppliers = cached.get("total_suppliers") or (len(supplier_breakdown) if supplier_breakdown else None)

        company_data = build_company_data(
            most_recent_shipment=merged.get("most_recent_shipment"),
            total_suppliers=total_suppliers,
            company_total_shipments=cached.get("company_total_shipments"),
            supplier_breakdown=supplier_breakdown,
            avg_order_cycle_days=avg_cycle,
            matching_shipments=cached.get("matching_shipments"),
            weight_kg=cached.get("weight_kg"),
            teu=cached.get("teu"),
            derived_growth_12m_pct=growth,
            derived_supplier_hhi=hhi,
            derived_order_regularity_cv=cv,
        )
        query_data = build_query_data(
            china_concentration=cn_12m if cn_12m is not None else china_concentration,
            cn_dominated_hs_code=cached.get("cn_dominated_hs_code", False),
            supplier_company_yoy=yoy,
        )

        # Compute full score (all 5 signals)
        full_score = compute_full_score(company_data, query_data)

        # Pre-compute scoring signals and camelCase conversions for pipeline reuse
        scoring_signals = {
            "reorderWindow": {"points": round(_signal_1_reorder_window(company_data), 1), "max": 20},
            "supplierDiversification": {"points": round(_signal_2_supplier_diversification(company_data, query_data), 1), "max": 15},
            "competitiveDisplacement": {"points": round(_signal_3_competitive_displacement(company_data, query_data), 1), "max": 10},
            "volumeFit": {"points": round(_signal_4_volume_fit(company_data), 1), "max": 12},
            "recencyActivity": {"points": round(_signal_5_recency_activity(company_data, query_data), 1), "max": 13},
            "hsRelevance": {"points": round(_signal_6_hs_relevance(company_data), 1), "max": 10},
            "shipmentScale": {"points": round(_signal_7_shipment_scale(company_data), 1), "max": 5},
            "switchingVelocity": {"points": round(_signal_8_switching_velocity(company_data), 1), "max": 3},
            "buyerGrowth": {"points": round(_signal_9_buyer_growth(company_data), 1), "max": 5},
            "supplyChainVulnerability": {"points": round(_signal_10_supply_chain_vulnerability(company_data), 1), "max": 4},
            "orderConsistency": {"points": round(_signal_11_order_consistency(company_data), 1), "max": 3},
        }

        enrichment_data["scoring_signals"] = scoring_signals
        enrichment_data["derived_china_concentration"] = china_concentration
        enrichment_data["derived_growth_12m_pct"] = growth
        enrichment_data["derived_china_concentration_12m"] = cn_12m

        # Save to cache — enriched_score goes on bol_companies directly
        enrichment_data["enrichment_status"] = "detail_enriched"
        enrichment_data["enriched_score"] = full_score
        write_ok = await internal_bol_client.update_enrichment(
            slug, enrichment_data, auth_token=auth_token,
        )
        if not write_ok:
            # Cache write failed — do NOT log a credit for a call whose result
            # did not persist. Raise so the caller surfaces the failure
            # (otherwise we'd return merged "detail_enriched" data for a row
            # whose cache row never advanced past pending, and the user would
            # be charged for a write that never landed).
            logger.error(
                "[%s] enrich_company: internal cache write failed; "
                "not logging the /company API credit.",
                slug,
            )
            raise RuntimeError(
                f"enrich_company: cache write failed for {slug} — refusing to "
                f"log API credit or surface detail_enriched payload"
            )

        # Log the API call (1 credit) — only after the cache write succeeded
        fire_tracked("log_api_call", lambda: internal_bol_client.log_api_call(
            endpoint=f"/company/{slug}",
            status_code=200,
            credits_used=1.0,
            result_count=1,
            auth_token=auth_token,
        ), retries=1)

        # Return full enriched company (include all fields written to cache)
        merged["enriched_score"] = full_score
        merged["enrichment_status"] = "detail_enriched"
        merged["scoring_signals"] = scoring_signals
        merged["derived_china_concentration"] = china_concentration
        merged["derived_growth_12m_pct"] = growth
        merged["derived_china_concentration_12m"] = cn_12m
        return merged

    async def search_companies(
        self,
        hs_codes: Optional[List[str]] = None,
        products: Optional[List[str]] = None,
        max_results: int = 500,
        supplier_country: str = "china",
        user_email: Optional[str] = None,
        auth_token: str = "",
        db_name: Optional[str] = None,
        cache_only: bool = False,
        requested_results: Optional[int] = None,
        is_onboarding: bool = False,
    ) -> Dict[str, Any]:
        # Normalize HS codes: strip dots so '9405.40' and '940540' are the same key
        if hs_codes:
            hs_codes = [code.replace(".", "") for code in hs_codes]

        # Poll-mode: caller wants to wait briefly for an in-flight cache warm
        if cache_only:
            return await self._serve_from_cache_with_poll(
                hs_codes=hs_codes,
                products=products,
                max_results=max_results,
                auth_token=auth_token,
                poll_attempts=SINGLEFLIGHT_WAIT_ATTEMPTS,
                poll_interval=SINGLEFLIGHT_WAIT_SECONDS,
            )

        result = await self._serve_from_cache(
            hs_codes=hs_codes,
            products=products,
            max_results=max_results,
            auth_token=auth_token,
        )
        merged = result["companies"]

        # Onboarding: trigger competitor fetch (Prelude pays)
        if is_onboarding and db_name and user_email:
            from importyeti.competitors.service import BolCompetitorService
            _competitor_dedupe = f"competitor_fetch:{','.join(sorted(hs_codes or []))}:{user_email}"
            fire_tracked("competitor_fetch", lambda: BolCompetitorService().fetch_competitors_background(
                hs_codes=hs_codes,
                db_name=db_name,
                user_email=user_email,
                auth_token=auth_token,
            ), retries=2, retry_delay=5.0, context={"hs_codes": hs_codes, "user_email": user_email},
            dedupe_key=_competitor_dedupe)

        # Auto deep-enrich top 10% when the visible window has unenriched companies
        _visible_limit = requested_results or max_results
        visible = merged[:_visible_limit]
        has_unenriched = any(
            (c.get("enrichment_status") or c.get("enrichmentStatus")) != "detail_enriched"
            for c in visible
        )
        _enrich_dedupe = f"auto_deep_enrich:{','.join(sorted(hs_codes or []))}:{user_email}"
        if user_email and db_name and is_onboarding and has_unenriched:
            fire_tracked("auto_deep_enrich", lambda: self.auto_deep_enrich_top_percent(
                hs_codes=hs_codes,
                auth_token=auth_token,
                user_email=user_email,
                db_name=db_name,
                is_onboarding=True,
                result_count=requested_results or max_results,
                cached_companies=visible,
            ), retries=2, retry_delay=3.0, context={"hs_codes": hs_codes, "user_email": user_email},
            dedupe_key=_enrich_dedupe)
        elif user_email and db_name and has_unenriched:
            fire_tracked("auto_deep_enrich", lambda: self.auto_deep_enrich_top_percent(
                hs_codes=hs_codes,
                auth_token=auth_token,
                user_email=user_email,
                db_name=db_name,
                is_onboarding=False,
                result_count=requested_results or max_results,
                cached_companies=visible,
            ), retries=2, retry_delay=3.0, context={"hs_codes": hs_codes, "user_email": user_email},
            dedupe_key=_enrich_dedupe)

        return result

    async def auto_deep_enrich_top_percent(
        self,
        hs_codes: List[str],
        auth_token: str,
        percent: float = 0.10,
        user_email: Optional[str] = None,
        db_name: Optional[str] = None,
        is_onboarding: bool = False,
        result_count: Optional[int] = None,
        cached_companies: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        Auto deep-enrich top N% of results.

        Onboarding: hardcoded cap (ONBOARDING_AUTO_ENRICH_CAP=10). Prelude pays.
        Ongoing: 10% of result_count (what the user asked for), not total cache.
        Skips already detail_enriched companies.

        When `cached_companies` is provided, skips the search_cache re-read.
        """
        if not user_email or not db_name:
            logger.info("[AutoEnrich] Skipped — missing user_email or db_name")
            return

        pm = get_pool_manager()

        # Use in-memory data when available, otherwise re-read from cache
        if cached_companies is not None:
            cached = cached_companies
        else:
            fetch_limit = result_count or 500
            cached = await internal_bol_client.search_cache(
                hs_codes=hs_codes, max_results=fetch_limit, auth_token=auth_token, slim=True,
            )
        if not cached:
            logger.info("[AutoEnrich] No cached results to deep-enrich")
            return

        # Compute how many to enrich — onboarding is capped globally across the
        # merged search cohort, ongoing uses the current result window.
        if is_onboarding:
            selected_slugs = select_onboarding_deep_enrich_slugs(
                cached,
                ONBOARDING_AUTO_ENRICH_CAP,
            )
            to_enrich = [
                company
                for company in cached
                if (company.get("importyeti_slug") or company.get("importyetiSlug")) in selected_slugs
            ]
        else:
            base_for_top_n = result_count if result_count and result_count > 0 else len(cached)
            top_n = min(50, max(1, int(base_for_top_n * percent)))
            to_enrich = [
                c for c in cached[:top_n]
                if (c.get("enrichment_status") or c.get("enrichmentStatus")) != "detail_enriched"
            ]

        if not to_enrich:
            logger.info("[AutoEnrich] Nothing to enrich from the current cache cohort")
            return

        if is_onboarding:
            reserved_units = 0
            try:
                async with pm.acquire(db_name) as conn:
                    reserved_units = await reserve_onboarding_buyer_ready_slots(conn, len(to_enrich))
                    await update_onboarding_progress(
                        conn,
                        buyers_target=result_count or ONBOARDING_BUYER_RESULT_LIMIT,
                    )
            except Exception as e:
                logger.warning(f"[AutoEnrich] Failed to reserve onboarding slots: {e}")
                return

            if reserved_units <= 0:
                logger.info("[AutoEnrich] Skipped — no reserved onboarding capacity available")
                return

            to_enrich = to_enrich[:reserved_units]

        logger.info(f"[AutoEnrich] Deep-enriching {len(to_enrich)} of {len(cached)} (onboarding={is_onboarding})")

        enriched = 0
        semaphore = asyncio.Semaphore(3)

        async def _enrich_one(slug: str):
            nonlocal enriched
            async with semaphore:
                try:
                    await self.enrich_company(slug, auth_token)
                    enriched += 1
                except Exception as e:
                    logger.warning(f"[AutoEnrich] Failed for {slug}: {e}")

        slugs = [
            c.get("importyeti_slug") or c.get("importyetiSlug")
            for c in to_enrich if (c.get("importyeti_slug") or c.get("importyetiSlug"))
        ]
        await asyncio.gather(*[_enrich_one(s) for s in slugs], return_exceptions=True)
        logger.info(f"[AutoEnrich] Complete: {enriched}/{len(slugs)} deep-enriched")

        if is_onboarding and reserved_units > enriched:
            try:
                async with pm.acquire(db_name) as conn:
                    await release_onboarding_buyer_ready_slots(conn, reserved_units - enriched)
            except Exception as e:
                logger.warning(f"[AutoEnrich] Failed to release unused onboarding slots: {e}")

    async def _serve_from_cache(self, hs_codes, max_results, auth_token, products=None):
        cached = await internal_bol_client.search_cache(
            hs_codes=hs_codes, products=products,
            max_results=max_results, auth_token=auth_token, slim=True,
        )
        companies = cached or []
        companies = self._merge_and_dedupe(companies)

        return {
            "companies": companies[:max_results],
            "source": "internal_db",
            "api_credits_used": 0,
            "total_cached": len(companies),
        }

    async def _serve_from_cache_with_poll(
        self,
        hs_codes,
        max_results,
        auth_token,
        *,
        poll_attempts: int,
        poll_interval: float,
        products=None,
    ):
        for attempt in range(poll_attempts):
            cached = await internal_bol_client.search_cache(
                hs_codes=hs_codes, products=products,
                max_results=max_results, auth_token=auth_token, slim=True,
            )
            if cached:
                companies = self._merge_and_dedupe(cached)
                return {
                    "companies": companies[:max_results],
                    "source": "warming_cache",
                    "api_credits_used": 0,
                    "total_cached": len(companies),
                    "in_progress": False,
                }
            if attempt < poll_attempts - 1:
                # After migration 009a the cache-state tables are gone — cache
                # warming is no longer polled via a separate endpoint. Just
                # sleep between attempts and re-query the cache directly.
                await asyncio.sleep(poll_interval)

        result = await self._serve_from_cache(hs_codes, max_results, auth_token, products=products)
        result["source"] = "warming_cache"
        result["in_progress"] = True
        return result

    def _merge_and_dedupe(self, companies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        by_slug: Dict[str, Dict[str, Any]] = {}
        by_name: Dict[str, Dict[str, Any]] = {}  # for raw CSV rows without slugs
        for c in companies:
            slug = c.get("importyeti_slug") or c.get("importyetiSlug", "")
            if slug:
                existing = by_slug.get(slug)
                if not existing:
                    by_slug[slug] = c
                else:
                    # Keep the higher best-available score (enriched_score if present, else quick_score)
                    new_score = _best_score(c)
                    old_score = _best_score(existing)
                    if new_score > old_score:
                        by_slug[slug] = c
            else:
                # Raw CSV row — dedup by normalized name, keep highest volume
                name = c.get("company_name_normalized") or c.get("company_name", "")
                if not name:
                    continue
                existing = by_name.get(name)
                if not existing or (c.get("matching_shipments") or 0) > (existing.get("matching_shipments") or 0):
                    by_name[name] = c
        return list(by_slug.values()) + list(by_name.values())
