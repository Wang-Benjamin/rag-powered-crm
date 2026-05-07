"""
CSV Bypass Onboarding — skip PowerQuery entirely.

Pre-requisites (done via internal-leads-db ingest_csv.sh):
  1. Buyer CSVs ingested into 8007 cache (bol_companies with hs_metrics JSONB)
  2. Competitor CSVs ingested into 8007 cache (bol_competitor_companies with hs_metrics JSONB)

This module reads from the pre-populated cache, runs contact-first filtering
to find companies with confirmed contacts, deep-enriches top buyers and
competitors, then populates the tenant's lead pipeline.
"""

import asyncio
import logging
import os
from typing import Dict, Any, List, Optional

from importyeti.buyers.service import BolSearchService
from importyeti.clients import internal_bol_client
from importyeti.competitors.service import BolCompetitorService
from importyeti.contracts.competitor_onboarding import build_competitor_completion_state
from importyeti.contracts.subscription import (
    heartbeat_onboarding,
    set_onboarding_status,
    update_onboarding_progress,
)
from importyeti.services.lead_enrichment import check_company_contact
from importyeti.services.lead_pipeline import add_slugs_to_pipeline

logger = logging.getLogger(__name__)

# ── Contact-first constants ─────────────────────────────────────────────────
# Switch between testing (minimal credits) and production
ONBOARDING_MODE = {
    "test": {
        "contact_target": 10,
        "over_fetch": 2,
        "buyer_enrich_cap": 1,
        "competitor_hydrate": 30,    # always hydrate 30 into tenant DB
        "competitor_enrich_cap": 1,  # deep-enrich only 1 during testing
    },
    "production": {
        "contact_target": 100,
        "over_fetch": 3,
        "buyer_enrich_cap": 20,
        "competitor_hydrate": 30,
        "competitor_enrich_cap": 1,
    },
}
_MODE = os.getenv("ONBOARDING_MODE", "production")
_CFG = ONBOARDING_MODE.get(_MODE, ONBOARDING_MODE["production"])

CONTACT_TARGET = _CFG["contact_target"]
CONTACT_OVER_FETCH = _CFG["over_fetch"]
DEEP_ENRICH_CAP = _CFG["buyer_enrich_cap"]

# Sub-batch size for contact-first loop — allows early exit when target reached
# mid-batch instead of waiting for entire (up to ~300 company) gather to complete.
CONTACT_SUB_BATCH_SIZE = 50


def _first_present(company: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = company.get(key)
        if value is not None:
            return value
    return None


def _company_enriched_score(company: Dict[str, Any]) -> Any:
    return _first_present(company, "enriched_score", "enrichedScore")


def _company_rank_score(company: Dict[str, Any]) -> Any:
    score = _first_present(
        company,
        "enriched_score",
        "enrichedScore",
        "quick_score",
        "quickScore",
    )
    return 0 if score is None else score


async def csv_onboard(
    *,
    conn,
    hs_codes: List[str],
    products: Optional[List[str]] = None,
    user_email: str,
    auth_token: str,
    db_name: str,
    buyer_enrich_cap: int = DEEP_ENRICH_CAP,
    buyer_result_limit: int = CONTACT_TARGET,
) -> Dict[str, Any]:
    """
    CSV-bypass onboarding kickoff.

    Assumes buyer + competitor data is already in 8007 cache
    (ingested via internal-leads-db ingest_csv.sh). Skips PowerQuery.

    Flow:
      1. Read buyers from 8007 cache
      2. Contact-first loop — filter to companies with confirmed contacts
      3. Deep-enrich the buyer-enrichment cap of survivors (1 credit each, Prelude pays)
      4. Hydrate competitors from 8007 cache -> tenant bol_competitors
      5. Deep-enrich the onboarding-capped competitors (1 credit each, Prelude pays)
      6. Refresh final survivors from 8007 (picks up fresh detail after deep-enrich)
      7. Populate pipeline with contact-confirmed survivors
    """
    hs_codes = [code.replace(".", "") for code in (hs_codes or [])]
    products = products or []

    if not hs_codes and not products:
        await set_onboarding_status(conn, user_email, "failed")
        return {"status": "failed", "error": "no_search_criteria", "buyers_enriched": 0, "competitors_enriched": 0, "pipeline_created": 0}

    contact_target = buyer_result_limit

    await set_onboarding_status(conn, user_email, "enriching")
    await update_onboarding_progress(conn, buyers_target=contact_target)

    # ── Step 1-2: Contact-first loop ───────────────────────────────
    attempted_slugs: set = set()
    survivors: List[Dict[str, Any]] = []  # companies with confirmed contacts
    contact_sem = asyncio.Semaphore(50)

    async def _check_one(company):
        slug = company.get("importyeti_slug") or company.get("importyetiSlug")
        async with contact_sem:
            return await check_company_contact(
                slug=slug,
                company_name=company.get("company_name") or company.get("companyName") or "",
                website=company.get("website"),
                city=company.get("city"),
                state=company.get("state"),
                country=company.get("country"),
                validated_email=company.get("validated_email") or company.get("validatedEmail"),
                validated_contact_name=company.get("validated_contact_name") or company.get("validatedContactName"),
                auth_token=auth_token,
            )

    while len(survivors) < contact_target:
        # Fetch from cache, over-fetching to account for contact attrition + multi-HS dedup.
        # Add attempted_slugs count so we fetch past already-checked companies.
        remaining_needed = contact_target - len(survivors)
        fetch_limit = CONTACT_OVER_FETCH * remaining_needed + len(attempted_slugs)
        cached = await internal_bol_client.search_cache(
            hs_codes=hs_codes or None,
            products=products or None,
            max_results=fetch_limit,
            auth_token=auth_token,
            slim=True,
        ) or []

        # Dedupe and filter out already-attempted
        candidates: List[Dict[str, Any]] = []
        seen_slugs: set = set()
        for row in cached:
            slug = row.get("importyeti_slug") or row.get("importyetiSlug")
            if slug and slug not in attempted_slugs and slug not in seen_slugs:
                candidates.append(row)
                seen_slugs.add(slug)

        if not candidates:
            break  # cache exhausted

        # Sort: validated_email first, then by matching_shipments
        candidates.sort(key=lambda c: (
            (c.get("validated_email") or c.get("validatedEmail")) is not None,
            c.get("matching_shipments") or 0,
        ), reverse=True)

        batch = candidates[:CONTACT_OVER_FETCH * (contact_target - len(survivors))]

        # Sub-batch the gather so we can break early when target is reached
        # mid-batch instead of waiting for ~300 Apollo calls to all complete.
        for chunk_start in range(0, len(batch), CONTACT_SUB_BATCH_SIZE):
            if len(survivors) >= contact_target:
                break
            sub_batch = batch[chunk_start:chunk_start + CONTACT_SUB_BATCH_SIZE]
            results = await asyncio.gather(*[_check_one(c) for c in sub_batch])
            for company, result in zip(sub_batch, results):
                slug = company.get("importyeti_slug") or company.get("importyetiSlug")
                attempted_slugs.add(slug)
                if result.get("has_contact"):
                    survivors.append(company)
            logger.info(
                "[CsvOnboard] Contact chunk: %s survivors / %s target (attempted %s total)",
                len(survivors), contact_target, len(attempted_slugs),
            )
            await heartbeat_onboarding(conn)

    if not survivors:
        logger.warning("[CsvOnboard] No buyers with contacts found for HS codes %s, products=%s", hs_codes, products)
        await set_onboarding_status(conn, user_email, "failed")
        return {"status": "failed", "error": "no_cached_buyers", "buyers_enriched": 0, "competitors_enriched": 0, "pipeline_created": 0}

    # Rank survivors: enriched_score > quick_score > matching_shipments (tiebreaker).
    # Slim HS/hybrid search rows include quick_score; product-only returns NULL and
    # falls back to the matching_shipments tiebreaker cleanly.
    survivors.sort(
        key=lambda c: (_company_rank_score(c), c.get("matching_shipments") or 0),
        reverse=True,
    )
    survivors = survivors[:contact_target]

    logger.info("[CsvOnboard] %s survivors with contacts (HS codes: %s, products=%s)", len(survivors), hs_codes, products)

    # ── Step 3: Deep-enrich top N survivors ─────────────────────────
    to_enrich = [
        c for c in survivors[:buyer_enrich_cap]
        if (c.get("enrichment_status") or c.get("enrichmentStatus")) != "detail_enriched"
    ]

    buyer_service = BolSearchService()
    enrich_semaphore = asyncio.Semaphore(3)

    async def _enrich_buyer(slug: str) -> str | None:
        async with enrich_semaphore:
            try:
                result = await buyer_service.enrich_company(slug, auth_token)
                if result.get("enrichment_status") == "detail_enriched":
                    return slug
            except Exception as e:
                logger.warning("[CsvOnboard] Buyer deep-enrich failed for %s: %s", slug, e)
            return None

    enrich_slugs = [
        c.get("importyeti_slug") or c.get("importyetiSlug")
        for c in to_enrich if (c.get("importyeti_slug") or c.get("importyetiSlug"))
    ]
    enriched_slugs: List[str] = []
    if enrich_slugs:
        results = await asyncio.gather(*[_enrich_buyer(s) for s in enrich_slugs])
        enriched_slugs = [s for s in results if s is not None]

    enriched_count = len(enriched_slugs)
    logger.info("[CsvOnboard] Buyer deep-enrich complete: %s/%s", enriched_count, len(enrich_slugs))

    # ── Step 4: Hydrate competitors from 8007 cache -> tenant DB ────
    await set_onboarding_status(conn, user_email, "competitors")

    comp_service = BolCompetitorService()

    # _deep_enrich_all_competitors reads from tenant's bol_competitors,
    # so we must hydrate from 8007 cache first (same as normal onboarding)
    existing_rows = await conn.fetch("SELECT supplier_slug FROM bol_competitors")
    known_slugs = {row["supplier_slug"] for row in existing_rows if row["supplier_slug"]}

    competitor_hydrate = _CFG["competitor_hydrate"]
    competitor_enrich_cap = _CFG["competitor_enrich_cap"]
    if products:
        # Product-text search: one single cache call covers all products
        cached_competitors = await internal_bol_client.search_competitor_cache(
            hs_codes=hs_codes or None,
            products=products,
            max_results=competitor_hydrate + 10,
            auth_token=auth_token,
        )
        if cached_competitors:
            hydrated = await comp_service._hydrate_cached_competitors(
                conn=conn, hs_code=hs_codes[0] if hs_codes else "",
                competitors=cached_competitors, known_slugs=known_slugs,
            )
            logger.info(
                "[CsvOnboard] Hydrated %s competitors for products=%s from 8007 cache",
                hydrated, products,
            )
    else:
        for hs_code in hs_codes:
            cached_competitors = await internal_bol_client.search_competitor_cache(
                hs_codes=[hs_code],
                max_results=competitor_hydrate + 10,
                auth_token=auth_token,
            )
            if cached_competitors:
                hydrated = await comp_service._hydrate_cached_competitors(
                    conn=conn, hs_code=hs_code,
                    competitors=cached_competitors, known_slugs=known_slugs,
                )
                logger.info("[CsvOnboard] Hydrated %s competitors for HS %s from 8007 cache", hydrated, hs_code)

    # ── Step 5: Deep-enrich competitors ─────────────────────────────
    ready_count, candidate_pool_exhausted = await comp_service._deep_enrich_all_competitors(
        conn, auth_token, user_email, enrich_cap=competitor_enrich_cap,
    )
    completion = build_competitor_completion_state(
        ready_count=ready_count,
        target=competitor_enrich_cap,
        candidate_pool_exhausted=candidate_pool_exhausted,
    )
    await update_onboarding_progress(
        conn,
        competitors_target=competitor_enrich_cap,
        competitors_ready=ready_count,
        warning_code=completion.warning_code,
        warning_meta=completion.warning_meta,
    )

    logger.info("[CsvOnboard] Competitor deep-enrich complete: %s ready", ready_count)

    # ── Step 6: Refresh final survivors from 8007 ───────────────────
    # Contact-first screened with slim rows. save_contact_to_cache wrote
    # validated_* back to 8007, and deep-enrich wrote full detail back.
    # Fetch each final survivor by slug to get one fresh dict with everything —
    # avoids the in-memory patchwork that would otherwise be needed.
    final_slugs = [
        (c.get("importyeti_slug") or c.get("importyetiSlug"))
        for c in survivors[:contact_target]
    ]
    final_slugs = [s for s in final_slugs if s]

    refresh_sem = asyncio.Semaphore(10)

    async def _refresh(slug: str):
        async with refresh_sem:
            return slug, await internal_bol_client.get_company(slug, auth_token=auth_token)

    survivor_by_slug: Dict[str, Dict[str, Any]] = {}
    if final_slugs:
        refreshed = await asyncio.gather(*[_refresh(s) for s in final_slugs])
        for slug, fresh in refreshed:
            if fresh:
                survivor_by_slug[slug] = fresh
        logger.info(
            "[CsvOnboard] Refreshed %s/%s final survivors from 8007",
            len(survivor_by_slug), len(final_slugs),
        )
        if not survivor_by_slug:
            logger.error(
                "[CsvOnboard] Survivor refresh returned 0/%s — 8007 reachable? "
                "Pipeline populate will be skipped.",
                len(final_slugs),
            )

    # Rank survivors: enriched_score > quick_score > matching_shipments
    fresh_ranked = sorted(
        survivor_by_slug.values(),
        key=lambda c: (
            _company_rank_score(c),
            c.get("matching_shipments") or 0,
        ),
        reverse=True,
    )

    # ── Step 7: Populate pipeline with contact-confirmed survivors ──
    top_slugs = [
        (c.get("importyeti_slug") or c.get("importyetiSlug"))
        for c in fresh_ranked[:contact_target]
    ]
    top_slugs = [s for s in top_slugs if s]

    pipeline_created = 0
    pipeline_warning = None
    if top_slugs:
        try:
            user = {"email": user_email, "db_name": db_name}
            populate_result = await add_slugs_to_pipeline(
                conn=conn,
                user=user,
                auth_token=auth_token,
                slugs=top_slugs,
                prefetched_companies=survivor_by_slug,
            )
            pipeline_created = populate_result.get("created", 0)
            logger.info(
                "[CsvOnboard] Pipeline populated: %s created, %s assigned, %s errors",
                populate_result.get("created", 0),
                populate_result.get("assigned", 0),
                len(populate_result.get("errors", [])),
            )

            # Recompute overlap now that leads exist
            try:
                hs_descriptions = await comp_service._get_hs_descriptions(conn, user_email)
                await comp_service._compute_competitor_overlap(conn, user_email, auth_token, hs_descriptions)
                logger.info("[CsvOnboard] Recomputed competitor overlap after pipeline populate")
            except Exception as e:
                logger.warning("[CsvOnboard] Post-populate overlap recompute failed: %s", e)
        except Exception as populate_err:
            logger.error("[CsvOnboard] Pipeline populate failed: %s", populate_err, exc_info=True)
            pipeline_warning = "pipeline_populate_failed"
    else:
        pipeline_warning = "pipeline_populate_empty"
        logger.warning("[CsvOnboard] No buyer slugs for pipeline populate")

    # ── Finalize onboarding status ──────────────────────────────────
    await update_onboarding_progress(
        conn,
        buyers_ready=enriched_count,
        warning_code=pipeline_warning,
    )

    await set_onboarding_status(conn, user_email, completion.status)

    return {
        "buyers_in_cache": len(attempted_slugs),
        "buyers_with_contacts": len(survivors),
        "buyers_enriched": enriched_count,
        "competitors_enriched": ready_count,
        "pipeline_created": pipeline_created,
        "status": completion.status,
    }
