"""
BoL Competitor Service — Phase 4

Competitor identification, overlap computation, threat scoring, lazy enrichment.
Split from bol_search_service.py — same ImportYetiClient, same internal_bol_client.
"""

import asyncio
import json
import logging
import uuid
from typing import Optional, List, Dict, Any

from importyeti.clients.api_client import ImportYetiClient
from importyeti.clients import internal_bol_client
from importyeti.clients.chinese_name_resolver import resolve_chinese_company_name
from importyeti.competitors.cache import (
    fetch_competitors_cached as _fetch_competitors_cached_helper,
    hydrate_cached_competitors as _hydrate_cached_competitors_helper,
)
from importyeti.competitors.common import (
    bucket_address as _bucket_address,
    bucket_name as _bucket_name,
    extract_city_from_address,
    json_or_none,
    list_or_empty,
    list_or_none,
    merge_hs_codes,
    normalize_trend_yoy,
)
from importyeti.competitors.overlap import (
    compute_competitor_overlap as _compute_competitor_overlap_helper,
    recompute_single_competitor_overlap as _recompute_single_competitor_overlap_helper,
)
from importyeti.competitors.repository import (
    current_hs_codes as _current_hs_codes_helper,
    get_hs_descriptions as _get_hs_descriptions_helper,
    get_visible_competitor_slugs as _get_visible_competitor_slugs_helper,
    upsert_cached_competitor as _upsert_cached_competitor_helper,
    upsert_competitor as _upsert_competitor_helper,
)
from importyeti.competitors.threat import (
    compute_threat_level as _compute_threat_level_helper,
    compute_threat_levels as _compute_threat_levels_helper,
)
from importyeti.contracts.competitor_onboarding import (
    COMPETITOR_CANDIDATE_BUFFER,
    build_competitor_completion_state,
    is_current_cohort_competitor,
    is_refresh_stale,
)
from importyeti.contracts.subscription import (
    ONBOARDING_COMPETITOR_FETCH,
    set_onboarding_status,
    update_onboarding_progress,
)
from service_core.db import get_pool_manager

logger = logging.getLogger(__name__)



class BolCompetitorService:

    def __init__(self):
        self.client = ImportYetiClient()

    async def _resolve_chinese_name(
        self, supplier_name: str, address: Optional[str] = None,
    ) -> Optional[str]:
        """Use Perplexity to web-search the official Chinese company name."""
        try:
            return await resolve_chinese_company_name(supplier_name, address)
        except Exception as e:
            logger.warning(f"[Competitors] Perplexity Chinese name lookup failed for {supplier_name}: {e}")
            return None

    async def fetch_competitors_background(
        self,
        hs_codes: List[str],
        db_name: str,
        user_email: str,
        auth_token: str,
    ):
        """
        Background task: fetch CN competitors for user's HS codes.
        Triggered during onboarding for BOTH tiers (Prelude pays).

        Uses /product/{product}/suppliers?countries=china (0.1/result).
        Seeds per-tenant bol_competitors from the fresh 8007 cache first,
        then falls back to live ImportYeti for any remaining slots.
        Then computes overlap, threat levels, and deep-enriches the onboarding-capped set.
        Updates onboarding status throughout.
        """
        try:
            pm = get_pool_manager()
        except RuntimeError:
            logger.warning("[Competitors] Pool manager not available for background task")
            return

        try:
            async with pm.acquire(db_name) as conn:
                await set_onboarding_status(conn, user_email, "competitors")
                await self._fetch_competitors_impl(hs_codes, conn, user_email, auth_token)
                ready_count, candidate_pool_exhausted = await self._deep_enrich_all_competitors(
                    conn,
                    auth_token,
                    user_email,
                )
                completion = build_competitor_completion_state(
                    ready_count=ready_count,
                    target=ONBOARDING_COMPETITOR_FETCH,
                    candidate_pool_exhausted=candidate_pool_exhausted,
                )
                await update_onboarding_progress(
                    conn,
                    competitors_target=ONBOARDING_COMPETITOR_FETCH,
                    competitors_ready=ready_count,
                    warning_code=completion.warning_code,
                    warning_meta=completion.warning_meta,
                )
                await set_onboarding_status(conn, user_email, completion.status)
        except Exception as e:
            logger.error(f"[Competitors] Background fetch failed: {e}", exc_info=True)
            try:
                async with pm.acquire(db_name) as conn:
                    await set_onboarding_status(conn, user_email, "failed")
            except Exception:
                pass

    async def _fetch_competitors_impl(
        self,
        hs_codes: List[str],
        conn,
        user_email: str,
        auth_token: str,
    ):
        """Core competitor fetch logic, called within a pooled connection."""
        try:
            # Get product descriptions from user's HS code profile
            hs_descriptions = await self._get_hs_descriptions(conn, user_email)
            current_hs_codes = set(hs_descriptions.keys()) or {code.replace(".", "") for code in hs_codes}

            existing_rows = await conn.fetch(
                "SELECT supplier_slug, hs_codes FROM bol_competitors"
            )
            known_slugs = {
                row["supplier_slug"]
                for row in existing_rows
                if row["supplier_slug"]
                and is_current_cohort_competitor(row.get("hs_codes"), current_hs_codes)
            }

            total_credits = 0.0
            api_cache_competitors_by_slug: Dict[str, Dict[str, Any]] = {}
            api_cache_search_results: List[Dict[str, Any]] = []
            candidate_target = ONBOARDING_COMPETITOR_FETCH + COMPETITOR_CANDIDATE_BUFFER

            total_codes = max(1, len(hs_codes))
            for index, hs_code in enumerate(hs_codes):
                remaining_slots = max(0, candidate_target - len(known_slugs))
                if remaining_slots <= 0:
                    logger.info(
                        "[Competitors] Candidate pool reached %s competitors; skipping remaining HS codes",
                        candidate_target,
                    )
                    break

                remaining_codes = max(1, total_codes - index)
                per_code_limit = max(1, (remaining_slots + remaining_codes - 1) // remaining_codes)

                # Use the HS code description or fall back to the code itself
                product_query = hs_descriptions.get(hs_code, hs_code)
                hydrated_from_cache = 0
                if auth_token:
                    cached_competitors = await self._fetch_competitors_cached(
                        hs_code=hs_code,
                        max_results=per_code_limit,
                        auth_token=auth_token,
                    )
                    if cached_competitors:
                        hydrated_from_cache = await self._hydrate_cached_competitors(
                            conn=conn,
                            hs_code=hs_code,
                            competitors=cached_competitors,
                            known_slugs=known_slugs,
                        )
                        logger.info(
                            "[Competitors] Hydrated %s competitors for %s from 8007 cache",
                            hydrated_from_cache,
                            hs_code,
                        )

                remaining_slots = max(0, candidate_target - len(known_slugs))
                remaining_for_code = max(0, per_code_limit - hydrated_from_cache)
                if remaining_slots <= 0 or remaining_for_code <= 0:
                    continue

                try:
                    response = await self.client.power_query_suppliers(
                        hs_code=f"{hs_code}*",
                        supplier_country="china",
                        page_size=min(remaining_slots, remaining_for_code),
                        start_date="01/01/2023",
                    )
                except Exception as e:
                    logger.warning(f"[Competitors] Failed to fetch for {hs_code}: {e}")
                    continue

                buckets = ((response.get("data") or {}).get("data")) or []
                credits = response.get("requestCost") or (len(buckets) * 0.1)
                total_credits += credits

                # Log API call
                asyncio.create_task(internal_bol_client.log_api_call(
                    endpoint="/powerquery/us-import/suppliers",
                    status_code=200,
                    credits_used=credits,
                    result_count=len(buckets),
                    hs_code=hs_code,
                    user_email=user_email,
                    auth_token=auth_token,
                ))

                hs_code_api_slugs = set()
                for bucket in buckets:
                    slug = self.client.extract_slug(bucket.get("supplier_link") or "")
                    if not slug:
                        continue

                    if slug not in known_slugs and len(known_slugs) >= candidate_target:
                        logger.info(
                            "[Competitors] Skipping new competitor %s because candidate cap %s is full",
                            slug,
                            candidate_target,
                        )
                        continue

                    supplier_name = _bucket_name(bucket.get("name_variations"))
                    address = _bucket_address(bucket.get("supplier_address"))
                    country_code = bucket.get("supplier_country_code") or "CN"
                    total_shipments = bucket.get("total_shipments")
                    matching_shipments = bucket.get("doc_count")

                    await self._upsert_competitor(
                        conn=conn,
                        supplier_slug=slug,
                        supplier_name=supplier_name,
                        address=address,
                        country_code=country_code,
                        hs_codes=[hs_code],
                        total_shipments=total_shipments,
                        matching_shipments=matching_shipments,
                        total_customers=None,
                        customer_companies=[],
                        specialization=None,
                        weight_kg=None,
                        product_descriptions=[],
                    )

                    known_slugs.add(slug)

                    city = self._extract_city_from_address(address)
                    existing = api_cache_competitors_by_slug.get(slug)
                    if not existing:
                        api_cache_competitors_by_slug[slug] = {
                            "importyeti_slug": slug,
                            "supplier_name": supplier_name,
                            "country": "China",
                            "country_code": country_code,
                            "address": address,
                            "city": city,
                            "hs_codes": [hs_code],
                            "total_shipments": total_shipments,
                            "product_descriptions": None,
                            "customer_companies": None,
                        }
                    else:
                        if hs_code not in existing["hs_codes"]:
                            existing["hs_codes"].append(hs_code)
                        if not existing.get("address") and address:
                            existing["address"] = address
                        if not existing.get("city") and city:
                            existing["city"] = city
                        if existing.get("total_shipments") is None and total_shipments is not None:
                            existing["total_shipments"] = total_shipments

                    api_cache_search_results.append({
                        "importyeti_slug": slug,
                        "hs_code": hs_code,
                        "matching_shipments": matching_shipments,
                        "weight_kg": None,
                        "specialization": None,
                        "total_customers": None,
                    })
                    hs_code_api_slugs.add(slug)

            if api_cache_competitors_by_slug and auth_token:
                try:
                    await internal_bol_client.save_competitors_to_cache(
                        competitors=list(api_cache_competitors_by_slug.values()),
                        search_results=api_cache_search_results,
                        auth_token=auth_token,
                    )
                except Exception as e:
                    logger.warning(f"[Competitors] Competitor cache write failed: {e}")

            logger.info(
                f"[Competitors] Fetched competitors for {len(hs_codes)} HS codes, "
                f"credits={total_credits:.1f} (Prelude pays — not charged to user)"
            )

            # Compute overlap with user's enriched buyers
            await self._compute_competitor_overlap(conn, user_email, auth_token, hs_descriptions)

        except Exception as e:
            logger.error(f"[Competitors] Competitor fetch failed: {e}", exc_info=True)
            raise  # Re-raise so outer handler sets status to "failed"

    async def _deep_enrich_all_competitors(
        self, conn, auth_token: str, user_email: str,
        enrich_cap: int | None = None,
    ) -> tuple[int, bool]:
        """
        Background deep-enrich the onboarding-capped competitor set via /supplier/{slug} (1 credit each).
        Prelude pays — no credit recording against user.
        Saves time_series, companies_table, also_known_names, recent_bols, carriers_per_country.
        Recomputes overlap and threat after enrichment.

        enrich_cap: optional override for how many competitors to deep-enrich.
                    Defaults to ONBOARDING_COMPETITOR_FETCH (30) if not set.
        """
        target_ready = enrich_cap if enrich_cap is not None else ONBOARDING_COMPETITOR_FETCH
        current_hs_codes = await self._current_hs_codes(conn)
        if current_hs_codes:
            ready_count = await conn.fetchval(
                "SELECT COUNT(*) FROM bol_competitors "
                "WHERE hs_codes && $1::varchar[] AND time_series IS NOT NULL",
                list(current_hs_codes),
            ) or 0
            remaining_target = max(0, target_ready - ready_count)
            candidate_limit = remaining_target + COMPETITOR_CANDIDATE_BUFFER
            rows = []
            if candidate_limit > 0:
                rows = await conn.fetch(
                    "SELECT supplier_slug, supplier_name, address, hs_codes FROM bol_competitors "
                    "WHERE hs_codes && $1::varchar[] AND time_series IS NULL "
                    "ORDER BY matching_shipments DESC NULLS LAST, last_updated_at DESC NULLS LAST "
                    f"LIMIT {candidate_limit}",
                    list(current_hs_codes),
                )
        else:
            ready_count = await conn.fetchval(
                "SELECT COUNT(*) FROM bol_competitors WHERE time_series IS NOT NULL"
            ) or 0
            remaining_target = max(0, target_ready - ready_count)
            candidate_limit = remaining_target + COMPETITOR_CANDIDATE_BUFFER
            rows = []
            if candidate_limit > 0:
                rows = await conn.fetch(
                    "SELECT supplier_slug, supplier_name, address, hs_codes FROM bol_competitors "
                    "WHERE time_series IS NULL "
                    "ORDER BY matching_shipments DESC NULLS LAST, last_updated_at DESC NULLS LAST "
                    f"LIMIT {candidate_limit}"
                )

        if ready_count >= target_ready:
            logger.info("[Competitors] Onboarding competitor target already satisfied")
            return ready_count, False

        if not rows:
            logger.info("[Competitors] No remaining competitors require deep enrichment")
            return ready_count, True

        logger.info(
            "[Competitors] Deep-enriching up to %s competitors from %s pending candidates "
            "(already ready=%s, Prelude pays)",
            target_ready,
            len(rows),
            ready_count,
        )
        enriched = 0

        async def _enrich_one(slug: str, name: str, address: Optional[str]):
            nonlocal enriched
            try:
                detail = await self.client.get_supplier_detail(slug)
                raw = detail.get("data", {}) if isinstance(detail.get("data"), dict) else detail

                time_series = raw.get("time_series")
                companies_table = raw.get("companies_table")
                also_known_names = raw.get("also_known_names")
                recent_bols = raw.get("recent_bols")
                carriers_per_country = raw.get("carriers_per_country")

                # Derive total_customers + top-5 customer_companies from
                # companies_table since power_query_suppliers doesn't return
                # those fields directly.
                derived_total_customers: Optional[int] = None
                derived_customer_companies: Optional[List[str]] = None
                if isinstance(companies_table, list) and companies_table:
                    derived_total_customers = len(companies_table)
                    derived_customer_companies = [
                        ((entry.get("company_name") or entry.get("name") or "").strip())
                        for entry in companies_table[:5]
                        if isinstance(entry, dict)
                        and (entry.get("company_name") or entry.get("name"))
                    ]

                # Compute trend_yoy
                trend_yoy = None
                if time_series and isinstance(time_series, dict):
                    from importyeti.domain.transformers import compute_supplier_company_yoy
                    yoy = compute_supplier_company_yoy(time_series)
                    if yoy is not None:
                        trend_yoy = round(yoy * 100, 1)
                elif time_series and isinstance(time_series, list) and len(time_series) >= 12:
                    recent_12 = sum(m.get("shipments", 0) for m in time_series[-12:])
                    prev_12 = sum(m.get("shipments", 0) for m in time_series[-24:-12]) if len(time_series) >= 24 else 0
                    if prev_12 > 0:
                        trend_yoy = round((recent_12 - prev_12) / prev_12 * 100, 1)

                # Derive product_descriptions and weight_kg from recent_bols
                derived_product_descriptions: Optional[List[str]] = None
                derived_weight_kg: Optional[float] = None
                if isinstance(recent_bols, list) and recent_bols:
                    descs = set()
                    total_weight = 0.0
                    for b in recent_bols:
                        desc = b.get("Product_Description") or b.get("product_description")
                        if desc and isinstance(desc, str):
                            descs.add(desc.strip())
                        w = b.get("Weight_in_KG") or b.get("weight_in_kg") or 0
                        try:
                            total_weight += float(w)
                        except (ValueError, TypeError):
                            pass
                    if descs:
                        derived_product_descriptions = sorted(descs)[:20]
                    if total_weight > 0:
                        derived_weight_kg = round(total_weight, 1)

                # Resolve Chinese company name via LLM
                supplier_name_cn = await self._resolve_chinese_name(name, address)

                await conn.execute(
                    """
                    UPDATE bol_competitors
                    SET time_series = $1::jsonb,
                        trend_yoy = $3,
                        companies_table = $4::jsonb,
                        also_known_names = $5,
                        recent_bols = $6::jsonb,
                        carriers_per_country = $7::jsonb,
                        supplier_name_cn = $8,
                        total_customers = COALESCE($9, total_customers),
                        customer_companies = COALESCE($10, customer_companies),
                        product_descriptions = COALESCE($11, product_descriptions),
                        weight_kg = COALESCE($12, weight_kg),
                        specialization = CASE
                            WHEN total_shipments > 0 THEN ROUND((matching_shipments::numeric / total_shipments) * 100, 1)
                            ELSE specialization
                        END,
                        last_updated_at = NOW()
                    WHERE supplier_slug = $2
                    """,
                    time_series if time_series else None,
                    slug,
                    trend_yoy,
                    companies_table if companies_table else None,
                    also_known_names,
                    recent_bols if recent_bols else None,
                    carriers_per_country if carriers_per_country else None,
                    supplier_name_cn,
                    derived_total_customers,
                    derived_customer_companies,
                    derived_product_descriptions,
                    derived_weight_kg,
                )

                if auth_token:
                    try:
                        await internal_bol_client.update_competitor_enrichment(slug, {
                            "time_series": time_series,
                            "trend_yoy": (trend_yoy / 100.0) if trend_yoy is not None else None,
                            "companies_table": companies_table,
                            "also_known_names": also_known_names,
                            "recent_bols": recent_bols,
                            "carriers_per_country": carriers_per_country,
                            "supplier_name_cn": supplier_name_cn,
                            "enrichment_status": "detail_enriched",
                        }, auth_token=auth_token)
                    except Exception as cache_err:
                        logger.warning(f"[Competitors] Competitor enrich write failed for {slug}: {cache_err}")

                # Log API call (Prelude-paid, tracking only)
                asyncio.create_task(internal_bol_client.log_api_call(
                    endpoint=f"/supplier/{slug}",
                    status_code=200,
                    credits_used=1.0,
                    result_count=1,
                    user_email=user_email,
                    auth_token=auth_token,
                ))
                enriched += 1
                return True
            except Exception as e:
                logger.warning(f"[Competitors] Deep-enrich failed for {slug}: {e}")
                return False

        remaining_to_enrich = target_ready - ready_count
        sem = asyncio.Semaphore(3)

        async def _guarded(row):
            # Double-check: once before waiting for semaphore (skip queueing),
            # once after acquiring (another worker may have hit the target).
            if enriched >= remaining_to_enrich:
                return
            async with sem:
                if enriched >= remaining_to_enrich:
                    return
                await _enrich_one(row["supplier_slug"], row["supplier_name"], row["address"])

        await asyncio.gather(*[_guarded(r) for r in rows], return_exceptions=True)
        total_ready = ready_count + enriched
        logger.info(
            "[Competitors] Deep-enrich complete: newly_enriched=%s pending_candidates=%s total_ready=%s",
            enriched,
            len(rows),
            total_ready,
        )

        # Recompute overlap + threat with fresh data
        if enriched > 0:
            try:
                hs_descriptions = await self._get_hs_descriptions(conn, user_email)
                await self._compute_competitor_overlap(conn, user_email, auth_token, hs_descriptions)
            except Exception as e:
                logger.warning(f"[Competitors] Post-enrich overlap recompute failed: {e}")
        return total_ready, total_ready < target_ready

    async def _fetch_competitors_cached(
        self,
        hs_code: str,
        max_results: int,
        auth_token: str,
    ) -> List[Dict[str, Any]]:
        return await _fetch_competitors_cached_helper(
            hs_code=hs_code,
            max_results=max_results,
            auth_token=auth_token,
            logger=logger,
        )

    async def _hydrate_cached_competitors(
        self,
        conn,
        hs_code: str,
        competitors: List[Dict[str, Any]],
        known_slugs: set[str],
    ) -> int:
        return await _hydrate_cached_competitors_helper(
            conn=conn,
            hs_code=hs_code,
            competitors=competitors,
            known_slugs=known_slugs,
            competitor_limit=ONBOARDING_COMPETITOR_FETCH,
            upsert_cached_competitor=self._upsert_cached_competitor,
        )

    async def _get_hs_descriptions(
        self, conn, user_email: str,
    ) -> Dict[str, str]:
        return await _get_hs_descriptions_helper(conn, logger)

    async def _current_hs_codes(self, conn) -> set[str]:
        return await _current_hs_codes_helper(conn, logger)

    async def _upsert_competitor(
        self,
        conn,
        supplier_slug: str,
        supplier_name: str,
        address: Optional[str],
        country_code: str,
        hs_codes: List[str],
        total_shipments: Optional[int],
        matching_shipments: Optional[int],
        total_customers: Optional[int],
        customer_companies: List[str],
        specialization: Optional[float],
        weight_kg: Optional[float],
        product_descriptions: List[str],
    ):
        return await _upsert_competitor_helper(
            conn=conn,
            supplier_slug=supplier_slug,
            supplier_name=supplier_name,
            address=address,
            country_code=country_code,
            hs_codes=hs_codes,
            total_shipments=total_shipments,
            matching_shipments=matching_shipments,
            total_customers=total_customers,
            customer_companies=customer_companies,
            specialization=specialization,
            weight_kg=weight_kg,
            product_descriptions=product_descriptions,
            logger=logger,
        )

    async def _upsert_cached_competitor(
        self,
        conn,
        hs_code: str,
        competitor: Dict[str, Any],
        supplier_slug: str,
    ) -> None:
        return await _upsert_cached_competitor_helper(
            conn=conn,
            hs_code=hs_code,
            competitor=competitor,
            supplier_slug=supplier_slug,
            logger=logger,
        )

    async def _compute_competitor_overlap(
        self, conn, user_email: str, auth_token: str, hs_descriptions: dict = None,
    ):
        return await _compute_competitor_overlap_helper(conn=conn, logger=logger)

    @staticmethod
    def _extract_city_from_address(address: str) -> Optional[str]:
        return extract_city_from_address(address)

    @staticmethod
    def _extract_cached_competitor_slug(competitor: Dict[str, Any]) -> Optional[str]:
        from importyeti.competitors.common import extract_cached_competitor_slug
        return extract_cached_competitor_slug(competitor)

    @staticmethod
    def _list_or_empty(value: Any) -> List[Any]:
        return list_or_empty(value)

    @staticmethod
    def _list_or_none(value: Any) -> Optional[List[Any]]:
        return list_or_none(value)

    @staticmethod
    def _merge_hs_codes(raw_hs_codes: Any, hs_code: str) -> List[str]:
        return merge_hs_codes(raw_hs_codes, hs_code)

    @staticmethod
    def _json_or_none(value: Any) -> Optional[Any]:
        return json_or_none(value)

    @staticmethod
    def _normalize_trend_yoy(value: Any) -> Optional[float]:
        return normalize_trend_yoy(value)

    async def _recompute_single_competitor_overlap(
        self, conn, competitor: Dict[str, Any], auth_token: str,
    ) -> List[str]:
        return await _recompute_single_competitor_overlap_helper(conn=conn, competitor=competitor)

    async def _compute_threat_levels(self, conn, max_volume: int):
        return await _compute_threat_levels_helper(conn=conn)

    @staticmethod
    def _compute_threat_level(competitor: Dict[str, Any], max_volume: int) -> tuple:
        return _compute_threat_level_helper(competitor, max_volume)

    async def get_competitors(self, conn, user_email: str) -> Dict[str, Any]:
        """
        Fetch all competitors for user from tenant DB.
        Returns competitors list + KPI summary.
        """
        # Frontend visibility: show all hydrated competitors. Hydrate step already
        # scopes insertion to tenant-relevant rows; the HS overlap filter we used
        # to apply here silently hid competitors whose arrays don't happen to
        # include a confirmed tenant HS (e.g. adjacent product categories from CSV
        # ingest).
        base_query = """
            SELECT id, supplier_slug, supplier_name, supplier_name_cn, country, country_code, address, city,
                   hs_codes, total_shipments, total_customers, matching_shipments,
                   specialization, weight_kg, customer_companies, product_descriptions,
                   overlap_count, overlap_buyer_slugs, threat_level, threat_score,
                   trend_yoy, is_tracked, notes, first_seen_at, last_updated_at
            FROM bol_competitors
        """
        rows = await conn.fetch(
            base_query + " ORDER BY threat_score DESC NULLS LAST, matching_shipments DESC NULLS LAST"
        )

        competitors = []
        top_volume_name = None
        top_volume_shipments = 0
        shared_count = 0
        vulnerable_count = 0

        for row in rows:
            comp = dict(row)
            comp["id"] = str(comp["id"])
            if comp.get("first_seen_at"):
                comp["first_seen_at"] = comp["first_seen_at"].isoformat()
            if comp.get("last_updated_at"):
                comp["last_updated_at"] = comp["last_updated_at"].isoformat()
            comp["is_refresh_stale"] = is_refresh_stale(comp.get("last_updated_at"))
            competitors.append(comp)

            ms = comp.get("matching_shipments") or 0
            if ms > top_volume_shipments:
                top_volume_shipments = ms
                top_volume_name = comp.get("supplier_name")

            if (comp.get("overlap_count") or 0) > 0:
                shared_count += 1

            trend = float(comp.get("trend_yoy") or 0)
            if trend < -15:
                vulnerable_count += 1

        kpi = {
            "total_competitors": len(competitors),
            "top_volume_name": top_volume_name,
            "top_volume_shipments": top_volume_shipments,
            "shared_buyers_count": shared_count,
            "vulnerable_count": vulnerable_count,
        }

        # Generate alerts from data — top 3 most significant declines only
        alerts = []
        for comp in competitors:
            trend = float(comp.get("trend_yoy") or 0)
            if trend < -15:
                alerts.append({
                    "type": "volume_drop",
                    "supplier_slug": comp.get("supplier_slug"),
                    "supplier_name": comp.get("supplier_name"),
                    "trend_yoy": trend,
                })
        alerts.sort(key=lambda a: a["trend_yoy"])
        alerts = alerts[:3]

        return {"competitors": competitors, "kpis": kpi, "alerts": alerts}

    async def get_competitor_detail(
        self, conn, supplier_slug: str, user_email: str, auth_token: str,
        skip_lazy_enrich: bool = False,
    ) -> Dict[str, Any]:
        """
        Get single competitor detail. Lazy-enrich via /supplier/{supplier}
        if time_series not cached (1 credit).
        """
        row = await conn.fetchrow(
            """
            SELECT id, supplier_slug, supplier_name, supplier_name_cn, country, country_code, address, city,
                   hs_codes, total_shipments, total_customers, matching_shipments,
                   specialization, weight_kg, customer_companies, product_descriptions,
                   overlap_count, overlap_buyer_slugs, threat_level, threat_score,
                   trend_yoy, time_series, is_tracked, notes, first_seen_at, last_updated_at,
                   companies_table, also_known_names, recent_bols, carriers_per_country
            FROM bol_competitors
            WHERE supplier_slug = $1
            """,
            supplier_slug,
        )
        if not row:
            return None
        # Previously we dropped the row when its hs_codes didn't overlap the
        # tenant's confirmed set. That silently hid competitors with adjacent
        # category codes and broke deep-link access for those slugs.
        competitor = dict(row)
        competitor["id"] = str(competitor["id"])
        if competitor.get("first_seen_at"):
            competitor["first_seen_at"] = competitor["first_seen_at"].isoformat()
        if competitor.get("last_updated_at"):
            competitor["last_updated_at"] = competitor["last_updated_at"].isoformat()

        # Lazy-enrich if no time_series (costs 1 credit)
        if not competitor.get("time_series") and not skip_lazy_enrich:
            try:
                detail = await self.client.get_supplier_detail(supplier_slug)
                raw = detail.get("data", {}) if isinstance(detail.get("data"), dict) else detail

                time_series = raw.get("time_series")
                companies_table = raw.get("companies_table")
                also_known_names = raw.get("also_known_names")
                recent_bols = raw.get("recent_bols")
                carriers_per_country = raw.get("carriers_per_country")

                competitor["time_series"] = time_series
                competitor["companies_table"] = companies_table
                competitor["also_known_names"] = also_known_names
                competitor["recent_bols"] = recent_bols
                competitor["carriers_per_country"] = carriers_per_country

                # Compute trend_yoy from time_series if available
                trend_yoy = None
                if time_series and isinstance(time_series, dict):
                    from importyeti.domain.transformers import compute_supplier_company_yoy
                    yoy = compute_supplier_company_yoy(time_series)
                    if yoy is not None:
                        trend_yoy = round(yoy * 100, 1)
                elif time_series and isinstance(time_series, list) and len(time_series) >= 12:
                    recent_12 = sum(m.get("shipments", 0) for m in time_series[-12:])
                    prev_12 = sum(m.get("shipments", 0) for m in time_series[-24:-12]) if len(time_series) >= 24 else 0
                    if prev_12 > 0:
                        trend_yoy = round((recent_12 - prev_12) / prev_12 * 100, 1)
                competitor["trend_yoy"] = trend_yoy

                # Update DB with all enrichment data
                await conn.execute(
                    """
                    UPDATE bol_competitors
                    SET time_series = $1::jsonb,
                        trend_yoy = $3,
                        companies_table = $4::jsonb,
                        also_known_names = $5,
                        recent_bols = $6::jsonb,
                        carriers_per_country = $7::jsonb,
                        last_updated_at = NOW()
                    WHERE supplier_slug = $2
                    """,
                    time_series if time_series else None,
                    supplier_slug,
                    trend_yoy,
                    companies_table if companies_table else None,
                    also_known_names,
                    recent_bols if recent_bols else None,
                    carriers_per_country if carriers_per_country else None,
                )

                if auth_token:
                    try:
                        await internal_bol_client.update_competitor_enrichment(supplier_slug, {
                            "time_series": time_series,
                            "trend_yoy": (trend_yoy / 100.0) if trend_yoy is not None else None,
                            "companies_table": companies_table,
                            "also_known_names": also_known_names,
                            "recent_bols": recent_bols,
                            "carriers_per_country": carriers_per_country,
                            "supplier_name_cn": competitor.get("supplier_name_cn"),
                            "enrichment_status": "detail_enriched",
                        }, auth_token=auth_token)
                    except Exception as cache_err:
                        logger.warning(f"[Competitors] Competitor enrich write failed for {supplier_slug}: {cache_err}")

                competitor["_lazy_enriched"] = True

                # Recompute overlap using full companies_table (not just top-5)
                try:
                    new_overlap = await self._recompute_single_competitor_overlap(
                        conn, competitor, auth_token,
                    )
                    competitor["overlap_count"] = len(new_overlap)
                    competitor["overlap_buyer_slugs"] = new_overlap

                    await conn.execute(
                        """
                        UPDATE bol_competitors
                        SET overlap_count = $1, overlap_buyer_slugs = $2,
                            last_updated_at = NOW()
                        WHERE supplier_slug = $3
                        """,
                        len(new_overlap), new_overlap,
                        supplier_slug,
                    )
                except Exception as e:
                    logger.warning(f"[Competitors] Overlap recompute failed for {supplier_slug}: {e}")

                # Always recompute threat with fresh trend_yoy + overlap
                try:
                    max_vol = await conn.fetchval(
                        "SELECT COALESCE(MAX(matching_shipments), 1) FROM bol_competitors"
                    ) or 1
                    new_score, new_label = self._compute_threat_level(competitor, max_vol)
                    competitor["threat_score"] = new_score
                    competitor["threat_level"] = new_label

                    await conn.execute(
                        """
                        UPDATE bol_competitors
                        SET threat_score = $1, threat_level = $2,
                            last_updated_at = NOW()
                        WHERE supplier_slug = $3
                        """,
                        new_score, new_label,
                        supplier_slug,
                    )
                    logger.info(
                        f"[Competitors] Recomputed {supplier_slug}: "
                        f"overlap={competitor.get('overlap_count')}, threat={new_score}/{new_label}"
                    )
                except Exception as e:
                    logger.warning(f"[Competitors] Threat recompute failed for {supplier_slug}: {e}")

                # Log credit usage
                asyncio.create_task(internal_bol_client.log_api_call(
                    endpoint=f"/supplier/{supplier_slug}",
                    status_code=200,
                    credits_used=1.0,
                    result_count=1,
                    user_email=user_email,
                    auth_token=auth_token,
                ))
            except Exception as e:
                logger.warning(f"[Competitors] Lazy-enrich failed for {supplier_slug}: {e}")

        # Get shared buyers from per-tenant leads table (single query).
        # Stale overlap_buyer_slugs from pre-UUID refactor can contain non-UUID
        # strings; filter per-entry so one bad slug doesn't empty the whole list.
        shared_buyers = []
        overlap_ids = competitor.get("overlap_buyer_slugs") or []
        if overlap_ids:
            uuids: list[uuid.UUID] = []
            invalid: list[str] = []
            for lid in overlap_ids:
                if isinstance(lid, uuid.UUID):
                    uuids.append(lid)
                    continue
                try:
                    uuids.append(uuid.UUID(str(lid)))
                except (ValueError, AttributeError, TypeError):
                    invalid.append(str(lid))
            if invalid:
                logger.warning(
                    f"[Competitors] {supplier_slug}: skipping {len(invalid)} invalid overlap slug(s): {invalid[:5]}"
                )
            if uuids:
                try:
                    rows = await conn.fetch(
                        "SELECT lead_id, company, score FROM leads WHERE lead_id = ANY($1::uuid[])",
                        uuids,
                    )
                    shared_buyers = [
                        {"buyer_slug": str(r["lead_id"]), "buyer_name": r["company"], "buyer_score": r["score"]}
                        for r in rows
                    ]
                except Exception as e:
                    logger.warning(f"[Competitors] shared_buyers query failed for {supplier_slug}: {e}")

        competitor["shared_buyers"] = shared_buyers

        # Customer concentration from companies_table
        concentration = None
        ct = competitor.get("companies_table")
        if ct:
            if isinstance(ct, str):
                try:
                    ct = json.loads(ct)
                except Exception:
                    ct = []
            if isinstance(ct, list) and len(ct) > 0:
                # Sort by shipment share descending
                sorted_customers = sorted(ct, key=lambda x: float(x.get("shipments_percents_company") or 0), reverse=True)
                top_share = float(sorted_customers[0].get("shipments_percents_company") or 0)
                top_3_share = sum(float(c.get("shipments_percents_company") or 0) for c in sorted_customers[:3])
                active_buyers = sum(1 for c in ct if (c.get("shipments_12m") or 0) > 0)
                concentration = {
                    "top_buyer_name": sorted_customers[0].get("company_name"),
                    "top_buyer_share": round(top_share, 1),
                    "top_3_share": round(top_3_share, 1),
                    "total_active_buyers": active_buyers,
                }
        competitor["customer_concentration"] = concentration

        # Recent BOLs — pass through, limit to 10
        raw_bols = competitor.get("recent_bols")
        if raw_bols and isinstance(raw_bols, str):
            try:
                raw_bols = json.loads(raw_bols)
            except Exception:
                raw_bols = []
        if isinstance(raw_bols, list):
            competitor["recent_bols"] = raw_bols[:10]
        else:
            competitor["recent_bols"] = []

        # Carriers — pass through China carriers
        raw_carriers = competitor.get("carriers_per_country")
        if raw_carriers and isinstance(raw_carriers, str):
            try:
                raw_carriers = json.loads(raw_carriers)
            except Exception:
                raw_carriers = {}
        if isinstance(raw_carriers, dict):
            competitor["carriers"] = raw_carriers.get("China") or []
        else:
            competitor["carriers"] = []

        return competitor


async def get_visible_competitor_slugs(conn, sub_info: dict) -> set:
    return await _get_visible_competitor_slugs_helper(
        conn=conn,
        visible_limit=sub_info["entitlements"]["competitors"]["visible_limit"],
    )
