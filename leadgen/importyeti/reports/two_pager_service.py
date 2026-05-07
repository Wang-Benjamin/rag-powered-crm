"""
Two-Pager Report Service

Generates the data payload for the two-page market intelligence PDF:
  - Page 1: 4 category stat cards + top-15 US buyer table with raw 0-100 scores
  - Page 2: top-3 buyer cards with Apollo decision-maker contact + AI outreach email

Cache-first on the buyer path (internal 8007 leads DB). Deep enrichment only on
buyers missing `supplier_breakdown`. Apollo + LLM are deferred to A3+A4 and
integrated in A5 — this file leaves `buyer_contacts=[]` for now.

SCORE DIVERGENCE NOTE:
  Scores returned here are RAW `compute_full_score` output (0-100). They do NOT
  go through `normalize_scores`, which requires >=20 inputs (see
  `importyeti/domain/scoring.py:374`). The two-pager passes only 15. The Buyers
  page normalizes across 50+ buyers, so the same company can show a different
  score on the two-pager vs. the Buyers page. This is intentional.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

# Two-pager enrichment is Apollo-only. The `ENRICHMENT_PROVIDER` switch used
# to allow falling back to lemlist, but the two-pager's contact_adapter is
# written directly against Apollo's interface, so lemlist mode was only
# working via duck-typing. Locked to Apollo to keep contact quality + cost
# predictable.
from apollo_io.client import ApolloClient as _EnrichClient
from apollo_io.schemas import ApolloConfig as _EnrichConfig

_KEY_VAR = "APOLLO_API_KEY"
_URL_DEFAULT = "https://api.apollo.io"

from importyeti.clients import internal_bol_client
from importyeti.clients.api_client import ImportYetiClient
from importyeti.domain.company_identity import dedupe_companies
from importyeti.domain.scoring import compute_full_score, compute_preliminary_score
from importyeti.domain.supplier_signals import (
    derive_cn_supplier_change,
    get_cn_supplier_subheader,
)
from importyeti.domain.transformers import (
    build_company_data,
    build_query_data,
    compute_growth_12m,
    compute_order_regularity_cv,
    compute_supplier_company_yoy,
    compute_supplier_hhi,
)
from importyeti.reports.enrichment import (
    deep_enrich_buyers as _deep_enrich_buyers_helper,
)
from importyeti.reports.pricing import weight_to_containers
from importyeti.reports.sources import (
    fetch_buyers_api as _fetch_buyers_api_helper,
    fetch_buyers_cached as _fetch_buyers_cached_helper,
)
from importyeti.reports.contact_adapter import (
    ContactResult,
    fetch_top3_contacts,
)
from importyeti.reports.demo_contacts import synthesize_demo_contact
from importyeti.reports.email_generator import (
    _TRANSLITERATED_CHINESE_RE,
    classify_low_value_buyers,
    generate_category_title,
    generate_outreach_emails,
    normalize_and_fabricate_buyer_fields,
)
from importyeti.reports.two_pager_models import (
    Buyer,
    BuyerContact,
    CategoryStats,
    TwoPagerResponse,
)
from importyeti.reports.real_company_filter import classify_real_companies

logger = logging.getLogger(__name__)

# ── Module-level asyncpg pool for prelude_lead_db (lazy-init) ───────────────
_lead_db_pool: Optional["asyncpg.Pool"] = None
_lead_db_pool_lock: Optional[asyncio.Lock] = None


async def _get_lead_db_pool():
    """Lazy-init a shared asyncpg pool for prelude_lead_db.

    One pool per process, bounded to 5 connections. Eliminates the
    per-call connect+close overhead and prevents connection exhaustion
    under batch load (5 concurrent reports × 2 DB methods = 10 calls).

    Raises on missing env vars or connect failure — callers must guard.
    """
    import asyncpg  # local, matches existing pattern in this module

    global _lead_db_pool, _lead_db_pool_lock
    if _lead_db_pool is not None:
        return _lead_db_pool
    if _lead_db_pool_lock is None:
        _lead_db_pool_lock = asyncio.Lock()
    async with _lead_db_pool_lock:
        if _lead_db_pool is None:
            _lead_db_pool = await asyncpg.create_pool(
                user=os.environ.get("SESSIONS_DB_USER"),
                password=os.environ.get("SESSIONS_DB_PASSWORD"),
                host=os.environ.get("SESSIONS_DB_HOST"),
                port=int(os.environ.get("SESSIONS_DB_PORT", "5432")),
                database="prelude_lead_db",
                min_size=1,
                max_size=5,
                timeout=5.0,
            )
    return _lead_db_pool


# Brand override map: email domain → display name for Page 2 only.
_DOMAIN_BRAND_MAP: Dict[str, str] = {
    "songmics.com": "SONGMICS",
    "crateandbarrel.com": "Crate & Barrel",
}

# Minimal HS-prefix → Chinese label fallback for Page 1 / Page 2 headers
# when the request used HS-only mode and no human description was passed.
# Kept intentionally short — covers only the HS prefixes Prelude actively
# demos. Anything missing falls through to "HS <code>" on the frontend.
_HS_CN_LABELS: Dict[str, str] = {
    "9405": "灯具",
    "8541": "光伏",
    "8504": "变压器",
    "8536": "开关电器",
    "8481": "阀门",
    "7326": "钢制品",
    "9403": "家具",
    "6404": "鞋类",
}

# Display-score curve (60-95 positional, 15 slots). The raw `compute_full_score`
# output drives the initial ordering; contactable buyers are then promoted to
# rows 1-3 (Step 5b) so Page 2 always surfaces 95/92/90 alongside emails. The
# curve preserves "top 15 buyers for this category all look premium" framing
# — even rank 15 stays above 60 (C+ tier).
_SCORE_CURVE: Tuple[int, ...] = (
    95, 92, 90, 87, 85, 82, 80, 77, 75, 72, 70, 67, 65, 62, 60,
)

# US state + territory 2-letter codes. Used to distinguish legitimate US
# importers (even ones whose legal name starts with a Chinese-city prefix
# like "Xiamen Tools Inc") from shell consignees with no US footprint.
_US_STATE_CODES: frozenset[str] = frozenset({
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC", "PR", "VI", "GU", "AS", "MP",
})


# Tokens to strip from the END of a buyer name when deriving a corporate
# email domain. Keeps the brand stem intact ("Verka Food International" → "verka food").
_DOMAIN_STRIP_TOKENS: frozenset[str] = frozenset({
    "inc", "incorporated", "llc", "corp", "corporation", "co", "company",
    "ltd", "limited", "lp", "international", "intl", "group", "holdings",
    "us", "usa", "global", "the", "and",
})


_GENERIC_LEADERS: frozenset[str] = frozenset({"the", "a", "an"})

# Free-mail domains the LLM was told to avoid; we double-check on output.
_FREEMAIL_DOMAINS: frozenset[str] = frozenset({
    "gmail.com", "googlemail.com",
    "yahoo.com", "ymail.com", "yahoo.co.uk",
    "hotmail.com", "hotmail.co.uk", "outlook.com", "live.com", "msn.com",
    "aol.com", "icloud.com", "me.com",
    "protonmail.com", "proton.me",
    "mail.com", "zoho.com", "gmx.com", "gmx.us",
})

# Generic role-account local parts the LLM was told to avoid.
_DISALLOWED_LOCAL_PARTS: frozenset[str] = frozenset({
    "noreply", "no-reply", "donotreply", "do-not-reply",
    "info", "admin", "support", "contact", "hello",
    "test", "demo", "example", "sales",
})

# TLDs the prompt forbids (only `.com` is allowed for synth emails).
_DISALLOWED_TLDS: frozenset[str] = frozenset({
    "net", "org", "io", "co", "biz", "info", "us", "tv",
})


def _is_safe_synth_email(email: str) -> bool:
    """Reject LLM-generated synth emails that escape the prompt's guardrails
    (free-mail providers, generic role accounts, non-`.com` TLDs)."""
    if not email or "@" not in email:
        return False
    local, _, domain = email.partition("@")
    local = local.strip().lower()
    domain = domain.strip().lower()
    if "." not in domain:
        return False
    if domain in _FREEMAIL_DOMAINS:
        return False
    if local in _DISALLOWED_LOCAL_PARTS:
        return False
    tld = domain.rsplit(".", 1)[-1]
    if tld in _DISALLOWED_TLDS:
        return False
    return True


def _heuristic_synth_email(first_name: str, buyer_name: str) -> str:
    """Fallback corporate-email generator when the LLM doesn't return one.

    Mirrors the LLM rules: lowercase first name as local part, derive the
    domain from the company name by stripping legal/generic suffixes from
    the END only and concatenating the remaining 1-2 brand words.
    "Verka Food International" + "Alex" → "alex@verkafood.com".
    """
    first = (first_name or "").strip().split()[0].lower() if first_name else "contact"
    local = re.sub(r"[^a-z]", "", first) or "contact"

    clean = re.sub(r"[^a-z0-9\s]", "", (buyer_name or "").lower())
    words = clean.split()
    # Strip stop tokens from the END only — matches the LLM prompt rules so
    # the heuristic-fallback path produces the same shape ("Verka Food
    # International" → verkafood.com, not "International Golden Foods" →
    # goldenfoods.com which the older anywhere-strip variant produced).
    while words and words[-1] in _DOMAIN_STRIP_TOKENS:
        words.pop()
    # Guard: if end-stripping nuked the brand and only generic leaders ("the",
    # "a", "an") remain, fall back to the original tokens so we never emit
    # "the.com" or "a.com".
    if not words or all(w in _GENERIC_LEADERS for w in words):
        words = clean.split() or ["company"]
    base = "".join(words[:2])
    domain = re.sub(r"[^a-z0-9]", "", base) or "example"
    return f"{local}@{domain}.com"


def _apply_brand_override(
    contact_result: ContactResult,
    buyer_name: str,
) -> Tuple[Optional[str], ContactResult]:
    """If the contact email domain matches _DOMAIN_BRAND_MAP, return the
    brand display name override. Otherwise return None.

    Returns (override_name_or_none, contact_result_unchanged).
    Page 1 Buyer.name keeps BOL legal name; only BuyerContact.buyer_name
    is overridden when a match is found.
    """
    email = contact_result.contact_email or ""
    if "@" in email:
        domain = email.split("@", 1)[1].lower().strip()
        override = _DOMAIN_BRAND_MAP.get(domain)
        if override:
            return override, contact_result
    return None, contact_result


class TwoPagerService:
    """Orchestrates Page 1 + Page 2 data for the two-pager report."""

    def __init__(self) -> None:
        self.client = ImportYetiClient()

    # ── Helpers — score ────────────────────────────────────────────────

    @staticmethod
    def _compute_preliminary_score(buyer_cached: Dict[str, Any]) -> int:
        """Compute raw `compute_preliminary_score` (0-80) for a single buyer.

        Cheap version of `_compute_buyer_score` — uses S2+S4+S6+S7 only and
        tolerates missing `supplier_breakdown` (returns 0 on any failure).
        Drives the narrow-from-survivors → 30 pool selection.
        """
        sb = (
            buyer_cached.get("supplier_breakdown")
            or buyer_cached.get("supplierBreakdown")
        )
        ts = buyer_cached.get("time_series") or buyer_cached.get("timeSeries") or {}

        derived_hhi = compute_supplier_hhi(sb) if isinstance(sb, list) else None
        yoy_frac = compute_supplier_company_yoy(ts) if ts else None
        total_suppliers = len(sb) if isinstance(sb, list) else None

        company = build_company_data(
            most_recent_shipment=(
                buyer_cached.get("most_recent_shipment")
                or buyer_cached.get("mostRecentShipment")
            ),
            total_suppliers=total_suppliers,
            company_total_shipments=buyer_cached.get("company_total_shipments"),
            supplier_breakdown=sb if isinstance(sb, list) else None,
            matching_shipments=(
                buyer_cached.get("matching_shipments")
                or buyer_cached.get("matchingShipments")
            ),
            weight_kg=buyer_cached.get("weight_kg") or buyer_cached.get("weightKg"),
            teu=buyer_cached.get("teu"),
            derived_supplier_hhi=derived_hhi,
        )
        query = build_query_data(
            china_concentration=None,
            cn_dominated_hs_code=False,
            supplier_company_yoy=yoy_frac,
        )
        try:
            return int(compute_preliminary_score(company, query))
        except Exception as e:
            logger.warning(
                f"[TwoPager] prelim score failed for {buyer_cached.get('slug')}: {e}"
            )
            return 0

    @staticmethod
    def _compute_buyer_score(buyer_cached: Dict[str, Any]) -> int:
        """Compute raw `compute_full_score` (0-100) for a single buyer.

        Builds company_data + query_data from cached enrichment fields. Falls
        back to 0 when `supplier_breakdown` is missing entirely (prelim only).
        """
        sb = (
            buyer_cached.get("supplier_breakdown")
            or buyer_cached.get("supplierBreakdown")
        )
        ts = buyer_cached.get("time_series") or buyer_cached.get("timeSeries") or {}

        derived_growth = compute_growth_12m(ts) if ts else None
        derived_hhi = compute_supplier_hhi(sb) if isinstance(sb, list) else None
        derived_cv = compute_order_regularity_cv(ts) if ts else None
        yoy_frac = compute_supplier_company_yoy(ts) if ts else None

        total_suppliers = len(sb) if isinstance(sb, list) else None

        company = build_company_data(
            most_recent_shipment=(
                buyer_cached.get("most_recent_shipment")
                or buyer_cached.get("mostRecentShipment")
            ),
            total_suppliers=total_suppliers,
            company_total_shipments=buyer_cached.get("company_total_shipments"),
            supplier_breakdown=sb if isinstance(sb, list) else None,
            matching_shipments=(
                buyer_cached.get("matching_shipments")
                or buyer_cached.get("matchingShipments")
            ),
            weight_kg=buyer_cached.get("weight_kg") or buyer_cached.get("weightKg"),
            teu=buyer_cached.get("teu"),
            derived_growth_12m_pct=derived_growth,
            derived_supplier_hhi=derived_hhi,
            derived_order_regularity_cv=derived_cv,
        )
        query = build_query_data(
            china_concentration=None,
            cn_dominated_hs_code=False,
            supplier_company_yoy=yoy_frac,
        )
        try:
            return int(compute_full_score(company, query))
        except Exception as e:
            logger.warning(f"[TwoPager] score failed for {buyer_cached.get('slug')}: {e}")
            return 0

    async def _fetch_category_aggregates(
        self,
        hs_code_wildcard: Optional[str] = None,
        product_description: Optional[str] = None,
    ) -> Dict[str, Optional[float]]:
        """Fetch active-importer count direct from IY (0.1 credits).

        Churn is computed locally in `_derive_local_stats` from the top-15
        supplier_breakdown — the net-supplier-count approximation we used
        to run here always returned 0% because CN supplier pools grow
        year-over-year. Returns {active_importer_count}.

        Dual-mode: pass either an HS wildcard (e.g. "9405*") or a product
        description (PowerQuery free-text). If both are missing we skip the
        IY call and return a null count.
        """
        if not hs_code_wildcard and not product_description:
            return {"active_importer_count": None}

        now = datetime.now(timezone.utc)
        fmt = "%m/%d/%Y"
        d_now = now.strftime(fmt)
        d_12mo = (now - timedelta(days=365)).strftime(fmt)

        try:
            resp = await self.client.power_query_buyers(
                hs_code=hs_code_wildcard,
                product_description=product_description,
                start_date=d_12mo,
                end_date=d_now,
                page_size=1,
                supplier_country="china",
            )
        except Exception as e:
            logger.warning(f"[TwoPager] active importer count fetch failed: {e}")
            return {"active_importer_count": None}

        comp_12 = None
        if getattr(resp, "data", None) is not None:
            comp_12 = resp.data.totalCompanies

        return {"active_importer_count": comp_12}

    @staticmethod
    def _derive_local_stats(
        top_15: List[Dict[str, Any]],
        years_elapsed: float = 0.5,
    ) -> Tuple[
        Optional[float], Optional[int], Optional[int], Optional[float], Optional[float],
    ]:
        """Derive (total_tons, total_containers, total_shipments, YoY%, churn%).

        All volume signals come from real ImportYeti fields on the
        already-fetched top-15 buyers — no USD estimates, no synthesized
        churn. The PowerQuery window is 6 months by default, so we
        annualize by scaling by `1 / years_elapsed` (=2x).

        YoY: weight-weighted mean of per-buyer trend_yoy (derived from
        time_series during deep enrichment). Per-buyer trends are capped
        at ±150% to prevent single-outlier spikes from skewing the
        aggregate.

        Churn: aggregate top-15 supplier_breakdown — unique CN suppliers
        who shipped in months 12-24 but NOT last 12 months divided by
        unique CN suppliers active in months 12-24. Returns None when
        the breakdown is missing or every CN supplier still active —
        the frontend renders that as `数据不足` rather than a fake
        deterministic number.
        """
        scale = 1.0 / max(years_elapsed, 0.01)

        total_kg = 0.0
        total_shipments = 0
        for b in top_15:
            w = float(b.get("weight_kg") or 0)
            if w > 0:
                total_kg += w
            ms = b.get("matching_shipments")
            if isinstance(ms, (int, float)) and ms > 0:
                total_shipments += int(ms)

        total_tons: Optional[float] = (
            round(total_kg * scale / 1000.0, 1) if total_kg > 0 else None
        )
        total_containers = weight_to_containers(total_kg * scale) if total_kg > 0 else None
        total_shipments_annual: Optional[int] = (
            int(round(total_shipments * scale)) if total_shipments > 0 else None
        )

        # Weighted YoY from top-15 trend_yoy (already in % units)
        weighted_num = 0.0
        weight_sum = 0.0
        for b in top_15:
            trend = b.get("trend_yoy")
            w = float(b.get("weight_kg") or 0)
            if trend is None or w <= 0:
                continue
            capped = max(min(float(trend), 150.0), -150.0)
            weighted_num += capped * w
            weight_sum += w
        yoy_pct = round(weighted_num / weight_sum, 1) if weight_sum > 0 else None

        # Churn from top-15 supplier_breakdown
        seen_cn: Dict[str, Dict[str, Any]] = {}
        for b in top_15:
            sb = b.get("supplier_breakdown") or b.get("supplierBreakdown")
            if not isinstance(sb, list):
                continue
            for entry in sb:
                if not isinstance(entry, dict):
                    continue
                country = (entry.get("country") or entry.get("supplier_address_country") or "")
                if country.upper() not in ("CN", "CHINA"):
                    continue
                name = entry.get("supplier_name") or entry.get("supplier_address") or ""
                if not name:
                    continue
                seen_cn.setdefault(name, entry)

        churn_pct: Optional[float] = None
        active_prior = 0
        churned = 0
        for entry in seen_cn.values():
            s24 = entry.get("shipments_12_24m") or 0
            s12 = entry.get("shipments_12m") or 0
            if s24 > 0:
                active_prior += 1
                if s12 == 0:
                    churned += 1
        # Only surface churn when at least one CN supplier actually
        # rolled off — active_prior > 0 with churned == 0 reads as
        # "no churn" visually but the signal is usually noise (every
        # 12-24m supplier still in the 12m window). Plan: prefer None
        # so the frontend shows 数据不足 over a misleading 0%.
        if active_prior > 0 and churned > 0:
            churn_pct = round(churned / active_prior * 100.0, 1)

        return total_tons, total_containers, total_shipments_annual, yoy_pct, churn_pct

    @staticmethod
    def _is_likely_non_us(buyer: Dict[str, Any]) -> bool:
        """Return True when a buyer's name looks transliterated-Chinese AND
        there's no US state evidence to counter it.

        A legit US company called "Xiamen Tools Inc" with state="CA" passes
        through (returns False). A shell like "Xiamen Yongqilong Trade"
        with no state or a non-US state code gets flagged (returns True).
        Name-regex match alone is NOT enough — must also lack US footprint.
        """
        name = buyer.get("name") or ""
        if not _TRANSLITERATED_CHINESE_RE.match(name):
            return False
        state = (buyer.get("state") or "").strip().upper()
        return state not in _US_STATE_CODES

    # ── Public entry point ─────────────────────────────────────────────

    async def generate_report(
        self,
        hs_code: Optional[str] = None,
        product_description: Optional[str] = None,
        conn=None,
        auth_token: str = "",
        user_email: Optional[str] = None,
    ) -> TwoPagerResponse:
        if not hs_code and not product_description:
            raise ValueError(
                "generate_report requires at least one of hs_code or product_description"
            )
        t_start = time.perf_counter()
        clean_hs = hs_code.replace(".", "") if hs_code else ""
        # Category label used for LLM prompts (email + normalization) and
        # aggregate stats logging. Replaces the removed hs_code_description +
        # HS→category translation paths.
        description = hs_code or product_description or ""

        warnings: List[str] = []

        # Kick off bilingual category-title generation (Haiku, ~5–10s) up front
        # so it overlaps with the buyer fetch + hard blocklist. The English
        # title is fed into the real-company filter (Step 1c) so Perplexity has
        # a meaningful category like "Rice" instead of the raw HS code "1006.30"
        # — that fixes a major cause of false-positive likely_shell verdicts.
        ai_title_task: asyncio.Task = asyncio.create_task(
            generate_category_title(hs_code, product_description)
        )

        # ── Step 1: Buyers (cache → API) ────────────────────────────────
        # Slim-first: cache search returns scalar fields only (~2s warm vs
        # 15-50s for the full payload). Heavy JSONB (supplier_breakdown,
        # time_series, recent_bols) is hydrated below for the top-30 pool
        # only — see Step 1d.
        cache_t0 = time.perf_counter()
        buyers_response = await self._fetch_buyers_cached(
            hs_code=clean_hs or None,
            product_description=product_description,
            auth_token=auth_token,
        )
        cache_search_ms = int((time.perf_counter() - cache_t0) * 1000)
        cached_companies = buyers_response.get("companies") or []

        # Top up from the IY API when the cache returned too few rows for the
        # blocklist + dedupe + real-filter chain to whittle down to 15.
        # Previous behavior fell back only on a fully empty cache, which left
        # thinly-seeded HS codes producing 9-10-row reports. MIN_CACHE_ROWS=30
        # matches the post-filter pool target (top_15 = top_3 + backfill_12
        # off pool[:30]). `api_called` is tracked so the late top-up at the
        # end of Step 2b doesn't double-fire the API.
        MIN_CACHE_ROWS = 30
        api_called = False
        if len(cached_companies) < MIN_CACHE_ROWS:
            if cached_companies:
                logger.info(
                    "[TwoPager] Cache returned %d/%d buyers; topping up from IY API",
                    len(cached_companies), MIN_CACHE_ROWS,
                )
            else:
                logger.info("[TwoPager] Cache miss for buyers, falling back to API")
            try:
                api_response = await self._fetch_buyers_api(
                    hs_code=clean_hs or None,
                    product_description=product_description,
                    auth_token=auth_token,
                )
                api_called = True
                cached_slugs = {c["slug"] for c in cached_companies}
                new_from_api = [
                    c for c in (api_response.get("companies") or [])
                    if c["slug"] not in cached_slugs
                ]
                if new_from_api or not cached_companies:
                    buyers_response = {
                        "total_companies": (
                            api_response.get("total_companies")
                            or buyers_response.get("total_companies")
                        ),
                        "companies": cached_companies + new_from_api,
                        "total_weight_kg": (
                            (buyers_response.get("total_weight_kg") or 0)
                            + (api_response.get("total_weight_kg") or 0)
                        ),
                        # Keep `from_cache=True` whenever the cache contributed
                        # any rows so Step 2c still uses the partial-enrich
                        # path. API-added rows naturally fall into `missing`
                        # (no supplier_breakdown) and get enriched on demand.
                        "from_cache": bool(cached_companies),
                    }
            except Exception as e:
                logger.error("[TwoPager] Buyer API fetch failed: %s", e)
                if not cached_companies:
                    warnings.append("buyer_source_exhausted")
                    buyers_response = {
                        "total_companies": None,
                        "companies": [],
                        "total_weight_kg": 0,
                        "from_cache": False,
                    }

        companies: List[Dict[str, Any]] = buyers_response["companies"]

        # ── Step 1b: Drop Fortune 500 retailers + logistics/3PL firms ───
        # The classifier returns two buckets:
        #   hard — regex-blocklisted (Amazon, Walmart, Midea, "freight",
        #          "logistics", etc.). NEVER re-admit, even to fill the table.
        #   soft — Haiku's borderline suggestions. MAY re-admit to top up
        #          toward 15 rows if the remaining pool is thin.
        # Final pool: kept + (soft backfill if still short). If we end up
        # with fewer than 15 clean buyers, the table just runs short —
        # honest beats polluted.
        if companies:
            try:
                verdict = await classify_low_value_buyers(companies)
                hard_skip: set[str] = verdict.get("hard") or set()
                soft_skip: set[str] = verdict.get("soft") or set()
                kept = [c for c in companies if c["slug"] not in hard_skip and c["slug"] not in soft_skip]
                soft_pool = [c for c in companies if c["slug"] in soft_skip]
                if len(kept) < 15:
                    need = 15 - len(kept)
                    kept = kept + soft_pool[:need]
                companies = kept
            except Exception as e:
                logger.warning(f"[TwoPager] Buyer classifier failed: {e}")

        # ── Step 1b (dedup): Merge near-duplicate company entries ───────
        try:
            before_dedup = len(companies)
            companies = dedupe_companies(companies)
            after_dedup = len(companies)
            if before_dedup != after_dedup:
                logger.info(
                    f"[TwoPager] dedup merged {before_dedup} → {after_dedup} companies"
                )
        except Exception as e:
            logger.warning(f"[TwoPager] Dedup failed: {e}")

        # ── Step 1c: Real-company pre-filter (web-search-backed) ────────
        # Classifies each survivor as 'real' / 'unclear' / 'likely_shell'
        # using Perplexity Sonar. Drop 'likely_shell' slugs to avoid
        # burning IY deep-enrich credits on shell LLCs / Amazon-FBA
        # dropshippers.
        #
        # Shadow mode (REAL_COMPANY_FILTER_SHADOW): default "true" — verdicts
        # are logged but no buyers are dropped. The classifier was over-
        # aggressive on commodity/food importers (HS 1006.30 dropped 27/45 as
        # likely_shell), so we run in shadow until prompt + category-label
        # tuning is verified. Set "false" once we trust the verdicts.
        #
        # Graceful degrade: returns {} on any failure → keep all survivors.
        _shadow_mode = os.environ.get("REAL_COMPANY_FILTER_SHADOW", "true").lower() == "true"

        # Await the bilingual title task so we can pass a real category label
        # ("Rice") to Perplexity instead of the raw HS code ("1006.30"). The
        # task may still be in flight; resolve here and reuse at the bottom.
        try:
            ai_title = await ai_title_task
        except Exception as e:
            logger.warning(f"[TwoPager/title] AI title task raised: {e}")
            ai_title = {"title_cn": None, "title_en": None}
        hs_desc_en: Optional[str] = ai_title.get("title_en")
        hs_desc_cn: Optional[str] = ai_title.get("title_cn")
        if not hs_desc_en:
            if product_description:
                hs_desc_en = product_description
            elif hs_code:
                hs_desc_en = f"HS {hs_code}"
        if not hs_desc_cn and clean_hs:
            hs_desc_cn = _HS_CN_LABELS.get(clean_hs[:4])
        # Use the cleanest available label as the category passed to the LLM
        # filter + email generator. Falls back to the raw `description`.
        llm_category = hs_desc_en or description

        if companies:
            try:
                real_verdicts = await classify_real_companies(
                    buyers=companies,
                    hs_category=llm_category,
                    timeout=30.0,
                )
                if real_verdicts:
                    n_real = sum(1 for v in real_verdicts.values() if v == "real")
                    n_unclear = sum(1 for v in real_verdicts.values() if v == "unclear")
                    n_shell = sum(1 for v in real_verdicts.values() if v == "likely_shell")
                    shell_slugs = {s for s, v in real_verdicts.items() if v == "likely_shell"}
                    n_dropped = len(shell_slugs)
                    logger.info(
                        "[TwoPager/real-filter] verdicts: %d real, %d unclear, %d likely_shell "
                        "(dropped %d) shadow=%s",
                        n_real, n_unclear, n_shell, n_dropped if not _shadow_mode else 0,
                        _shadow_mode,
                    )
                    if not _shadow_mode and shell_slugs:
                        companies = [c for c in companies if c["slug"] not in shell_slugs]
                else:
                    logger.info(
                        "[TwoPager/real-filter] classifier unavailable; keeping all survivors"
                    )
            except Exception as e:
                logger.warning("[TwoPager/real-filter] classifier raised: %s; keeping all survivors", e)

        # ── Step 2: Two-tier scoring — prelim on all survivors, narrow to 30 ─
        # Prelim score is cheap (S2+S4+S6+S7 only) and works on unenriched
        # rows. Full score runs later on the final 15 only. Rank the full
        # survivor pool by prelim + weight so the pool[:30] we hand to Apollo
        # contains the highest-prelim-score contactable buyers.
        for c in companies:
            c["quick_score"] = self._compute_preliminary_score(c)
        companies.sort(
            key=lambda c: (
                -(c.get("quick_score") or 0),
                -(float(c.get("weight_kg") or 0)),
            )
        )
        pool = companies[:30]

        # ── Step 1d: Hydrate heavy JSONB for the 30-pool ────────────────
        # Cache search ran slim, so supplier_breakdown / time_series /
        # recent_bols are missing. Per-slug GET on /bol/company/{slug}
        # returns the full row. Bound at Semaphore(8) for connection-pool
        # safety. Per-slug failures degrade gracefully — downstream
        # filters and scoring already tolerate missing breakdown.
        # Run as a background task so contact fetch + agg overlap with it.
        hydrate_t0 = time.perf_counter()
        hydrate_sem = asyncio.Semaphore(8)
        hydrate_count = 0

        async def _hydrate_one(c: Dict[str, Any]) -> bool:
            async with hydrate_sem:
                full = await internal_bol_client.fetch_company_by_slug(
                    c["slug"], auth_token=auth_token,
                )
            if not full:
                return False
            for k in ("supplier_breakdown", "time_series", "recent_bols"):
                v = full.get(k)
                if v is not None:
                    c[k] = v
            # Re-derive trend_yoy from time_series (slim cache search left
            # it None because the heavy field wasn't returned).
            ts = c.get("time_series")
            if ts and isinstance(ts, dict) and c.get("trend_yoy") is None:
                yoy = compute_supplier_company_yoy(ts)
                if yoy is not None:
                    c["trend_yoy"] = round(yoy * 100, 1)
            return True

        async def _hydrate_pool() -> None:
            nonlocal hydrate_count
            results = await asyncio.gather(*[_hydrate_one(c) for c in pool])
            hydrate_count = sum(1 for r in results if r)

        hydrate_task: Optional[asyncio.Task] = (
            asyncio.create_task(_hydrate_pool()) if pool else None
        )

        # ── Step 2a: Contact fetch on the 30-pool (Apollo only) ─────────
        # fetch_top3_contacts internally walks top3 + fallback together (cache
        # pass across the whole pool, then up to 8 Apollo chains). Passing
        # pool[:3] as top3 and pool[3:30] as fallback preserves its current
        # call shape while widening coverage from 15 to 30.
        agg_task: Optional[asyncio.Task] = asyncio.create_task(
            self._fetch_category_aggregates(
                hs_code_wildcard=f"{clean_hs}*" if clean_hs else None,
                product_description=product_description,
            )
        )
        contact_results, apollo_metrics = await self._fetch_apollo_contacts(
            pool[:3], pool[3:30], auth_token=auth_token,
        )
        if apollo_metrics["apollo_found"] == 0 and pool:
            warnings.append("apollo_unavailable")
        elif apollo_metrics["apollo_found"] < 3 and len(pool) >= 3:
            warnings.append("apollo_short_page")
        if apollo_metrics.get("credit_exhausted"):
            warnings.append("enrichment_credits_exhausted")

        # ── Step 2b: Partition pool by contactability and pick final 15 ──
        # Top 3 = highest prelim-score buyers with a `found` contact.
        # Backfill 12 = next-highest prelim-score buyers regardless of contact.
        found_slugs_initial = {
            r.buyer_slug for r in contact_results if r.fetch_status == "found"
        }
        contactable_pool = [c for c in pool if c["slug"] in found_slugs_initial]
        top_3 = contactable_pool[:3]
        top_3_slugs = {c["slug"] for c in top_3}
        remaining_pool = [c for c in pool if c["slug"] not in top_3_slugs]
        backfill_12 = remaining_pool[:12]
        top_15 = top_3 + backfill_12

        # ── Step 2b.1: Late top-up if filters trimmed pool below 15 ────
        # Last-ditch refill: the cache+API merge in Step 1 guarantees ≥30 raw
        # rows for most HS codes, but blocklist + transliterated-CN + dedupe
        # can still drop the pool below 15 in CN-heavy categories. If we
        # haven't already called the API in Step 1, call it now and append
        # the shortfall. Buyers added here lack `supplier_breakdown` so they
        # fall into Step 2c's `missing` set and get deep-enriched naturally.
        # Apollo top-3 has already been picked from the original pool — the
        # top-up only fills backfill positions, never card_buyers[:3].
        if len(top_15) < 15 and not api_called:
            shortage = 15 - len(top_15)
            logger.info(
                "[TwoPager] top_15 short by %d after filters; fetching IY API top-up",
                shortage,
            )
            try:
                topup_response = await self._fetch_buyers_api(
                    hs_code=clean_hs or None,
                    product_description=product_description,
                    auth_token=auth_token,
                )
                api_called = True
                existing_slugs = {c["slug"] for c in companies}
                topup_pool = [
                    c for c in (topup_response.get("companies") or [])
                    if c["slug"] not in existing_slugs
                ]
                if topup_pool:
                    v = await classify_low_value_buyers(topup_pool)
                    hard = v.get("hard") or set()
                    topup_pool = [c for c in topup_pool if c["slug"] not in hard]
                    for c in topup_pool:
                        c["quick_score"] = self._compute_preliminary_score(c)
                    topup_pool.sort(
                        key=lambda c: (
                            -(c.get("quick_score") or 0),
                            -(float(c.get("weight_kg") or 0)),
                        )
                    )
                    additions = topup_pool[:shortage]
                    if additions:
                        top_15.extend(additions)
                        logger.info(
                            "[TwoPager] late top-up added %d buyers; top_15 now %d",
                            len(additions), len(top_15),
                        )
            except Exception as e:
                logger.warning("[TwoPager] late API top-up failed: %s", e)

        if len(top_15) < 15:
            logger.warning(
                f"[TwoPager] Only {len(top_15)} survivors made it to final 15; "
                f"display curve will be truncated"
            )

        # ── Step 2b.5: Wait for hydrate before any code reads heavy JSONB ─
        # Deep-enrich, post-enrichment filters, and scoring all need
        # supplier_breakdown / time_series. Block here for completion.
        hydrate_ms = 0
        if hydrate_task is not None:
            try:
                await hydrate_task
            except Exception as e:
                logger.warning(f"[TwoPager] hydrate gather raised: {e}")
            hydrate_ms = int((time.perf_counter() - hydrate_t0) * 1000)
            logger.info(
                "[TwoPager] hydrate top-30: %d/%d hydrated in %dms",
                hydrate_count, len(pool), hydrate_ms,
            )

        # ── Step 2c: Deep-enrich the final 15 only ──────────────────────
        if top_15:
            missing = [c for c in top_15 if not c.get("supplier_breakdown")]
            needs_enrich = bool(missing) or not buyers_response.get("from_cache")
            if needs_enrich:
                targets = missing if missing else top_15
                logger.info(
                    f"[TwoPager] Enriching {len(targets)}/{len(top_15)} buyers"
                )
                try:
                    if buyers_response.get("from_cache"):
                        deep_res = await self._deep_enrich_buyers(targets, auth_token=auth_token)
                    else:
                        deep_res = await self._deep_enrich_buyers(top_15, auth_token=auth_token)

                    # Merge enrichment results directly into top_15 dicts — do NOT
                    # rely on the 8007 cache refresh, which silently returns empty
                    # when the internal leads service isn't running.
                    for c in top_15:
                        slug = c["slug"]
                        for k, v in (deep_res.get(slug) or {}).items():
                            if v is not None:
                                c[k] = v
                except Exception as e:
                    logger.warning(f"[TwoPager] Enrichment failed: {e}")
                    warnings.append("Some buyers could not be deep-enriched.")

        # ── Step 2d: Post-enrichment filters (none currently active) ────
        # Both post-enrichment filters were removed 2026-04-25:
        #
        # 1. CN-concentration ≥ 40% gate — PowerQuery already filters
        #    `supplier_country=china`, so every survivor here has CN supplier
        #    activity. The 40% threshold was an additional "must be CN-
        #    DOMINANT" gate that wrongly killed diversified-sourcing buyers
        #    in commodity categories (rice, grains, oils — globally sourced).
        #
        # 2. Dead-buyer filter (`is_dead_buyer`) — flagged buyers with CN
        #    suppliers in months 12-24 but none in the last 12. For a report
        #    whose product is "match CN suppliers to US importers who may
        #    need one now", that pattern is a LEAD signal, not a kill signal.
        #    Buyers who just dropped their CN suppliers are the prime
        #    prospects for our supplier customers. The cn_prev → cn_curr
        #    chip on each card surfaces the change so users can judge.
        #
        # Both predicates (`china_concentration`, `is_dead_buyer`) live in
        # importyeti.domain.supplier_signals for potential category-aware reintroduction.
        # Reintroduce as soft re-rankers, not hard kill switches.
        # ────────────────────────────────────────────────────────────────

        # ── Step 3: Compute full score, CN supplier change, annual volume ─
        # Volume signals come from real ImportYeti fields (weight_kg,
        # matching_shipments) annualized from the 6-month query window.
        # No more landed-price estimates — see pricing.py docstring.
        WINDOW_YEARS = 0.5  # PowerQuery window in sources.py
        scale = 1.0 / WINDOW_YEARS

        # Stage raw data; keep existing display order (top_3 first, then
        # prelim-ranked backfill). Full score drives the display-curve nudge
        # but does NOT re-sort — we already committed to the top-3 selection.
        staged: List[Dict[str, Any]] = []
        for comp in top_15:
            prev_cn, curr_cn = derive_cn_supplier_change(comp)
            raw_score = self._compute_buyer_score(comp)
            weight = float(comp.get("weight_kg") or 0)
            annualized_kg = weight * scale if weight > 0 else 0
            annual_tons = round(annualized_kg / 1000.0, 1) if annualized_kg > 0 else None
            containers = weight_to_containers(annualized_kg) if annualized_kg > 0 else None
            ms_raw = comp.get("matching_shipments")
            hs_shipments = (
                int(round(float(ms_raw) * scale))
                if isinstance(ms_raw, (int, float)) and ms_raw > 0
                else None
            )
            staged.append({
                "_orig": comp,
                "slug": comp["slug"],
                "name": comp["name"],
                "city": comp.get("city"),
                "state": comp.get("state"),
                "annual_tons": annual_tons,
                "containers": containers,
                "hs_shipments": hs_shipments,
                "cn_prev": prev_cn,
                "cn_curr": curr_cn,
                "trend": comp.get("trend_yoy"),
                "raw_score": raw_score,
                "weight_kg": weight,
            })

        # ── Step 3b: Sonnet pass — clean locations + fabricate (0,0) ───
        # Single Sonnet call normalizes weird "2Nd Fl New York" city values
        # into clean US city + 2-letter state, and fabricates plausible
        # CN supplier counts for buyers whose real supplier_breakdown
        # returned empty (both cn_prev and cn_curr == 0). Real data is
        # preserved — the prompt tells Sonnet never to overwrite non-zero
        # input. Failure is non-fatal; we just keep the raw values.
        #
        # Country gate: skip entries whose name matches the transliterated-
        # Chinese prefix regex — don't let Sonnet fabricate US addresses
        # for foreign-named entities.
        #
        # Run as a background task (rank-3 speed win); awaited just before
        # buyers_out assembly.
        norm_task: Optional[asyncio.Task] = None
        if staged:
            # Country gate: only skip entries whose name matches the
            # transliterated-Chinese regex AND lack a US state code. A
            # legit US company "Xiamen Tools Inc" with state "CA" still
            # flows through and gets location-normalized.
            norm_input = [
                {
                    "slug": s["slug"],
                    "name": s["name"],
                    "city": s["city"],
                    "state": s["state"],
                    "cn_prev": s["cn_prev"],
                    "cn_curr": s["cn_curr"],
                }
                for s in staged
                if not self._is_likely_non_us(s)
            ]
            if norm_input:
                norm_task = asyncio.create_task(
                    normalize_and_fabricate_buyer_fields(norm_input, description)
                )

        # ── Step 4: Category stats (Page 1) ─────────────────────────────
        # agg_task was launched at the top of Step 2 alongside the contact
        # fetch so it overlaps with Apollo I/O.
        try:
            agg = await agg_task
        except Exception as e:
            logger.warning(f"[TwoPager] Category aggregates fetch failed: {e}")
            agg = {"active_importer_count": None}

        total_tons, total_containers, total_shipments_annual, yoy_pct, churn_pct = (
            self._derive_local_stats(top_15)
        )
        stats = CategoryStats(
            total_import_tons=total_tons,
            total_containers=total_containers,
            total_hs_shipments=total_shipments_annual,
            yoy_growth_pct=yoy_pct,
            active_importer_count=agg.get("active_importer_count")
                or buyers_response.get("total_companies"),
            supplier_churn_pct=churn_pct,
        )

        # ── Step 5: Brand override (post-Apollo, display-only) ─────────
        # Contact fetch ran earlier at Step 2a as part of the pool-narrowing
        # pipeline. Here we only apply display-side tweaks (brand name
        # override) and await the Sonnet normalization task.
        # If a contact email domain is in _DOMAIN_BRAND_MAP, override the
        # buyer name on Page 2 (BuyerContact.buyer_name) only.
        # Page 1 Buyer.name keeps the BOL legal name.
        brand_overrides: Dict[str, str] = {}
        for r in contact_results:
            override_name, _ = _apply_brand_override(r, "")
            if override_name:
                brand_overrides[r.buyer_slug] = override_name

        # Await the Sonnet normalization background task before assembling output.
        norm: Dict[str, Any] = {}
        if norm_task is not None:
            try:
                norm = await norm_task
            except Exception as e:
                logger.warning(f"[TwoPager] Buyer normalization failed: {e}")
        if norm:
            for s in staged:
                patch = norm.get(s["slug"])
                if not patch:
                    continue
                if patch.get("city"):
                    s["city"] = patch["city"]
                    s["_orig"]["city"] = patch["city"]
                if patch.get("state"):
                    s["state"] = patch["state"]
                    s["_orig"]["state"] = patch["state"]
                # Only accept fabricated counts when raw was (0, 0).
                if (s["cn_prev"] or 0) == 0 and (s["cn_curr"] or 0) == 0:
                    s["cn_prev"] = int(patch.get("cn_prev", 0) or 0)
                    s["cn_curr"] = int(patch.get("cn_curr", 0) or 0)

        # Display-score computation: curve + raw-score delta.
        # Base is the positional curve (95/92/90/.../60), nudged by how this
        # buyer's raw_score compares to the cohort average. Small coefficient
        # (0.15) keeps the nudge under ~3 points so rank order visually holds,
        # while letting real-data differences show up across reports.
        # Bounds guard: _SCORE_CURVE has 15 entries. If fewer than 15 survivors
        # made it here, iteration must clamp, not IndexError.
        raw_scores = [float(s["raw_score"] or 0) for s in staged]
        cohort_avg_raw = sum(raw_scores) / len(raw_scores) if raw_scores else 0.0

        buyers_out: List[Buyer] = []
        for i, s in enumerate(staged):
            base = _SCORE_CURVE[min(i, len(_SCORE_CURVE) - 1)]
            delta = (float(s["raw_score"] or 0) - cohort_avg_raw) * 0.15
            display_score = int(round(max(60, min(95, base + delta))))
            buyers_out.append(Buyer(
                rank=i + 1,
                slug=s["slug"],
                name=s["name"],
                city=s["city"],
                state=s["state"],
                annual_volume_tons=s["annual_tons"],
                containers_count=s["containers"],
                hs_shipments_count=s["hs_shipments"],
                cn_prev_supplier_count=s["cn_prev"],
                cn_curr_supplier_count=s["cn_curr"],
                trend_yoy_pct=s["trend"],
                score=display_score,
            ))

        # ── Step 6 prep: Pick 3 card slots; mix real Apollo + synth ─────
        # Strategy: take the first 3 buyers from `top_15` (top_3 contactable
        # come first by construction in Step 2b, then prelim-ranked backfill).
        # For each slot, use the real Apollo contact if found, otherwise
        # synthesize a placeholder name/title/email. This unifies the UX —
        # frontend renders all 3 the same regardless of source. The
        # `is_synthesized` flag on BuyerContact lets the backend distinguish
        # for logging / cache write-back without surfacing it in the UI.
        TOP3_CARDS = 3
        results_by_slug = {r.buyer_slug: r for r in contact_results}
        staged_by_slug = {s["slug"]: s for s in staged}
        card_buyers = top_15[:TOP3_CARDS]
        contact_plan: List[Dict[str, Any]] = []
        synth_index = 0
        for comp in card_buyers:
            slug = comp["slug"]
            r = results_by_slug.get(slug)
            if r and r.fetch_status == "found" and r.contact_name:
                contact_plan.append({
                    "comp": comp,
                    "is_synth": False,
                    "name": r.contact_name,
                    "title": r.contact_title or "Decision-maker",
                    "email": r.contact_email,
                })
            else:
                synth = synthesize_demo_contact(
                    buyer_slug=slug,
                    buyer_name=comp.get("name") or slug,
                    subject=llm_category,
                    index=synth_index,
                )
                synth_index += 1
                contact_plan.append({
                    "comp": comp,
                    "is_synth": True,
                    "name": synth["name"],
                    "title": synth["title"],
                    "email": synth["email"],
                })

        synth_slugs = [p["comp"]["slug"] for p in contact_plan if p["is_synth"]]
        if synth_slugs:
            logger.info(
                "[TwoPager/synth] %d/%d card contacts AI-mocked (Apollo miss): %s",
                len(synth_slugs), len(card_buyers), synth_slugs,
            )

        # ── Step 6: Batched LLM outreach emails for ALL 3 card buyers ──
        # Use the AI-resolved English category label (e.g. "Rice") as the
        # subject context — passing the raw HS code led to subjects like
        # "9505.10 Festive Décor — Reliable CN Supplier" which leaked the
        # HS code into the visible email subject.
        llm_contexts: List[Dict[str, Any]] = []
        for plan in contact_plan:
            comp = plan["comp"]
            slug = comp["slug"]
            s_ref = staged_by_slug.get(slug)
            if s_ref is not None:
                prev_cn = int(s_ref.get("cn_prev") or 0)
                curr_cn = int(s_ref.get("cn_curr") or 0)
            else:
                prev_cn, curr_cn = derive_cn_supplier_change(comp)
            score = next(
                (b.score for b in buyers_out if b.slug == slug), 0
            )
            llm_contexts.append({
                "slug": slug,
                "name": comp.get("name"),
                "city": comp.get("city"),
                "state": comp.get("state"),
                "annual_volume_tons": next(
                    (b.annual_volume_tons for b in buyers_out if b.slug == slug), None
                ),
                "trend_yoy_pct": comp.get("trend_yoy"),
                "cn_prev_supplier_count": prev_cn,
                "cn_curr_supplier_count": curr_cn,
                "cn_subheader": get_cn_supplier_subheader(prev_cn, curr_cn),
                "contact_name": plan["name"],
                "contact_title": plan["title"],
                "score": score,
                # Tells the LLM to also generate a corporate email for synth
                # contacts (alex@verka.com), so we don't have to expose the
                # demo+slug@preludeos.com placeholder in the rendered card.
                "synth_email_needed": plan["is_synth"],
            })

        emails_by_slug: Dict[str, Dict[str, str]] = {}
        llm_calls = 0
        if llm_contexts:
            llm_calls = 1
            try:
                emails_by_slug = await generate_outreach_emails(
                    llm_contexts, llm_category,
                )
            except Exception as e:
                logger.warning(f"[TwoPager] email generation raised: {e}")
                emails_by_slug = {}
            if not emails_by_slug:
                warnings.append("llm_unavailable")

        # ── Step 7: Assemble buyer_contacts (Page 2) ───────────────────
        # Always 3 slots when top_15 has ≥ 3 entries. Synth contacts ride the
        # same `fetch_status="found"` path so the frontend renders them as
        # real cards — `is_synthesized=True` is metadata-only.
        buyer_contacts: List[BuyerContact] = []
        for plan in contact_plan:
            comp = plan["comp"]
            slug = comp["slug"]
            s_ref = staged_by_slug.get(slug)
            if s_ref is not None:
                prev_cn = int(s_ref.get("cn_prev") or 0)
                curr_cn = int(s_ref.get("cn_curr") or 0)
            else:
                prev_cn, curr_cn = derive_cn_supplier_change(comp)
            subheader = get_cn_supplier_subheader(prev_cn, curr_cn)
            display_score = next(
                (b.score for b in buyers_out if b.slug == slug), 0
            )
            buyer_row = next((b for b in buyers_out if b.slug == slug), None)
            email = emails_by_slug.get(slug)
            location = (
                f"{comp.get('city') or ''}, {comp.get('state') or ''}".strip(", ")
                or None
            )
            # Apply brand override for Page 2 display name only.
            display_buyer_name = brand_overrides.get(slug) or comp.get("name") or ""

            # For synth slots, replace the demo+<slug>@preludeos.com placeholder
            # with a corporate-style email (alex@verkafood.com). Prefer the
            # LLM's output, but only if it passes the freemail / role-account
            # / TLD guardrails — Sonnet occasionally ignores prompt rules.
            # Fall back to the Python heuristic otherwise.
            contact_email = plan["email"]
            if plan["is_synth"]:
                llm_email = email.get("email") if email else None
                if llm_email and _is_safe_synth_email(llm_email):
                    contact_email = llm_email
                else:
                    contact_email = _heuristic_synth_email(
                        plan["name"], comp.get("name") or slug,
                    )

            buyer_contacts.append(BuyerContact(
                buyer_slug=slug,
                buyer_name=display_buyer_name,
                score=display_score,
                location=location,
                annual_volume_tons=buyer_row.annual_volume_tons if buyer_row else None,
                containers_count=buyer_row.containers_count if buyer_row else None,
                hs_shipments_count=buyer_row.hs_shipments_count if buyer_row else None,
                trend_yoy_pct=comp.get("trend_yoy"),
                cn_prev_supplier_count=prev_cn,
                cn_curr_supplier_count=curr_cn,
                cn_subheader=subheader,
                contact_name=plan["name"],
                contact_title=plan["title"],
                contact_email=contact_email,
                fetch_status="found",
                email_subject=email.get("subject") if email else None,
                email_body=email.get("body") if email else None,
                is_synthesized=plan["is_synth"],
            ))

        # ── Observability ──────────────────────────────────────────────
        elapsed_ms = int((time.perf_counter() - t_start) * 1000)
        logger.info(
            "[TwoPager] metrics hs=%s product=%s "
            "two_pager.cache_search_ms=%d two_pager.hydrate_ms=%d "
            "two_pager.apollo_calls=%d two_pager.apollo_found=%d "
            "two_pager.llm_calls=%d two_pager.generation_time_ms=%d "
            "two_pager.warnings_count=%d",
            hs_code,
            product_description,
            cache_search_ms,
            hydrate_ms,
            apollo_metrics["apollo_calls"],
            apollo_metrics["apollo_found"],
            llm_calls,
            elapsed_ms,
            len(warnings),
        )

        # `hs_desc_en` / `hs_desc_cn` were resolved earlier (Step 1c) so we
        # could feed a real category label to the real-company filter; reuse
        # them here for the response header — no second LLM call needed.

        return TwoPagerResponse(
            hs_code=hs_code,
            product_description=product_description,
            hs_code_description=hs_desc_en,
            hs_code_description_cn=hs_desc_cn,
            stats=stats,
            buyers=buyers_out,
            buyer_contacts=buyer_contacts,
            generated_at=datetime.now(timezone.utc).isoformat(),
            warnings=warnings,
        )

    @staticmethod
    async def _load_validated_contacts(
        slugs: List[str],
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """Fetch validated contact fields for the given slugs. Returns
        {slug: {"email", "name", "title"}}; empty dict on any failure.
        """
        if not slugs:
            return {}
        try:
            import asyncpg  # local import
        except ImportError:
            return {}
        db_user = os.environ.get("SESSIONS_DB_USER")
        db_pw = os.environ.get("SESSIONS_DB_PASSWORD")
        db_host = os.environ.get("SESSIONS_DB_HOST")
        if not (db_user and db_pw and db_host):
            return {}
        try:
            pool = await _get_lead_db_pool()
        except Exception as e:
            logger.warning("[TwoPager] Could not acquire lead_db pool: %s", e)
            return {}
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT importyeti_slug,
                       validated_email,
                       validated_contact_name,
                       validated_contact_title
                  FROM bol_companies
                 WHERE importyeti_slug = ANY($1::text[])
                """,
                slugs,
            )
        out: Dict[str, Dict[str, Optional[str]]] = {}
        for r in rows:
            slug = r["importyeti_slug"]
            if not slug:
                continue
            if not (r["validated_email"] or r["validated_contact_name"]):
                continue
            out[slug] = {
                "email": r["validated_email"],
                "name": r["validated_contact_name"],
                "title": r["validated_contact_title"],
            }
        return out

    async def _fetch_apollo_contacts(
        self,
        top3: List[Dict[str, Any]],
        fallback: List[Dict[str, Any]],
        auth_token: str = "",
    ) -> Tuple[List[ContactResult], Dict[str, int]]:
        """Fetch Apollo contacts. Never raises — returns [] + apollo_unavailable metric on failure.

        Returns (contact_results, {"apollo_calls": int, "apollo_found": int}).
        """
        if not top3:
            return [], {"apollo_calls": 0, "apollo_found": 0}

        api_key = os.getenv(_KEY_VAR)
        if not api_key:
            logger.warning(f"[TwoPager] {_KEY_VAR} not set; skipping contacts")
            return (
                [
                    ContactResult(buyer_slug=b["slug"], fetch_status="failed")
                    for b in top3
                ],
                {"apollo_calls": 0, "apollo_found": 0},
            )

        config = _EnrichConfig(
            api_key=api_key,
            base_url=os.getenv("APOLLO_BASE_URL", _URL_DEFAULT),
            timeout_seconds=int(os.getenv("APOLLO_TIMEOUT", "30")),
        )
        credit_exhausted = False
        try:
            async with _EnrichClient(config) as apollo:
                results = await fetch_top3_contacts(top3, apollo, fallback, auth_token=auth_token)
                # `credit_exhausted` was a Lemlist-only attribute; Apollo
                # surfaces rate limits as errors handled inside fetch_top3_contacts.
                credit_exhausted = bool(getattr(apollo, "credit_exhausted", False))
        except Exception as e:
            logger.error(f"[TwoPager] Enrichment session failed: {e}")
            return (
                [
                    ContactResult(buyer_slug=b["slug"], fetch_status="failed")
                    for b in top3
                ],
                {"apollo_calls": 0, "apollo_found": 0, "credit_exhausted": 0},
            )

        apollo_calls = len(results)
        apollo_found = sum(1 for r in results if r.fetch_status == "found")
        return results, {
            "apollo_calls": apollo_calls,
            "apollo_found": apollo_found,
            "credit_exhausted": int(credit_exhausted),
        }

    # ── Cache-first buyer fetching (delegate to shared helpers) ─────────

    async def _fetch_buyers_cached(
        self,
        hs_code: Optional[str] = None,
        product_description: Optional[str] = None,
        auth_token: str = "",
    ) -> Dict[str, Any]:
        return await _fetch_buyers_cached_helper(
            client=self.client,
            hs_code=hs_code,
            product_description=product_description,
            auth_token=auth_token,
            logger=logger,
        )

    async def _fetch_buyers_api(
        self,
        hs_code: Optional[str] = None,
        product_description: Optional[str] = None,
        auth_token: str = "",
    ) -> Dict[str, Any]:
        return await _fetch_buyers_api_helper(
            client=self.client,
            hs_code=hs_code,
            product_description=product_description,
            auth_token=auth_token,
            logger=logger,
        )

    async def _deep_enrich_buyers(
        self, companies: List[Dict], auth_token: str = ""
    ) -> Dict[str, Dict]:
        return await _deep_enrich_buyers_helper(
            client=self.client, companies=companies, auth_token=auth_token, logger=logger,
        )
