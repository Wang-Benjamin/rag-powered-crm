"""ImportYeti buyer search and add-to-pipeline endpoints."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from importyeti.buyers.service import BolSearchService
from importyeti.clients import internal_bol_client
from importyeti.contracts.bol_contract import best_score as _best_score
from importyeti.contracts.subscription import (
    ONBOARDING_WARMING_MESSAGE,
    get_subscription_info,
    get_tenant_hs_codes,
)
from importyeti.domain.transformers import (
    apply_trial_blur,
    normalize_for_dedup,
    parse_city_state,
    redact_buyer_personnel_emails,
)
from importyeti.services.lead_pipeline import add_slugs_to_pipeline
from service_core.db import get_tenant_connection
from pydantic import model_validator

logger = logging.getLogger(__name__)
router = APIRouter()
_MAX_CACHE_FETCH = 5000


class BolSearchRequest(BaseModel):
    """Search request. At least one of hs_codes or products must be provided."""
    hs_codes: Optional[List[str]] = Field(None, description="HS codes from user profile")
    products: Optional[List[str]] = Field(None, description="Product description terms (OR semantics across the list)")
    max_results: int = Field(500, ge=1, le=500)
    supplier_country: str = Field("china", description="Filter buyers importing from this country")

    @model_validator(mode="after")
    def _require_hs_or_products(self):
        if not (self.hs_codes or self.products):
            raise ValueError("At least one of hs_codes or products must be provided")
        return self


class AddToPipelineRequest(BaseModel):
    slugs: List[str] = Field(..., min_length=1, description="ImportYeti company slugs to add as leads")
    # Search params the client used to produce the result list. Required so the
    # server can reconstruct the exact cohort and reject slugs outside it.
    hs_codes: Optional[List[str]] = Field(None, description="HS codes submitted in the originating search")
    products: Optional[List[str]] = Field(None, description="Product terms submitted in the originating search")
    max_results: int = Field(500, ge=1, le=500, description="max_results submitted in the originating search")

    @model_validator(mode="after")
    def _require_hs_or_products(self):
        if not (self.hs_codes or self.products):
            raise ValueError("At least one of hs_codes or products must be provided")
        return self


@router.post("/importyeti/search")
async def search_buyers(
    request: BolSearchRequest,
    tenant=Depends(get_tenant_connection),
    authorization: str = Header(None),
):
    """
    Search for US importers by HS code(s). Internal-only endpoint.

    Onboarding fetch is NOT triggered by this endpoint — it fires exactly once
    per tenant from `POST /importyeti/onboarding/csv-kickoff`, invoked by the
    onboarding wizard's final Save click. This handler only performs ongoing
    search under entitlement gates.

    During onboarding in-flight: cache-only with a warming message.
    All tiers: cache-only read returning rows with is_blurred stamped per resolved visible_limit.
    """
    conn, user = tenant
    user_email = user.get("email", "unknown")
    auth_token = authorization.replace("Bearer ", "") if authorization else ""

    try:
        # Only enforce HS-profile membership when the caller passed hs_codes.
        # Product-only searches bypass the profile check by design.
        if request.hs_codes:
            hs_data = await get_tenant_hs_codes(conn)
            if hs_data:
                confirmed_codes = {
                    c.get("code").replace(".", "") for c in hs_data if c.get("confirmed") and c.get("code")
                }
                invalid = [code for code in request.hs_codes if code.replace(".", "") not in confirmed_codes]
                if invalid:
                    raise HTTPException(
                        status_code=400,
                        detail=f"HS codes not in company profile: {invalid}. "
                        f"Confirmed codes: {sorted(confirmed_codes)}",
                    )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Could not validate HS codes for {user_email}: {e}")

    sub_info = await get_subscription_info(conn, user_email)
    tier = sub_info["tier"]
    onboarding_status = sub_info["onboardingStatus"]

    cache_only_message = None

    if onboarding_status in ("pending", "enriching", "competitors", "failed"):
        cache_only_message = ONBOARDING_WARMING_MESSAGE

    existing_leads: set = set()
    try:
        hs_codes_for_query = [c.replace(".", "") for c in (request.hs_codes or []) if c]
        if hs_codes_for_query:
            rows = await conn.fetch(
                "SELECT company, location FROM leads "
                "WHERE import_context->'hsCodes' ?| $1::text[]",
                hs_codes_for_query,
            )
            existing_leads = {(normalize_for_dedup(r["company"]), normalize_for_dedup(r["location"])) for r in rows}
    except Exception as e:
        logger.warning(f"Pipeline pre-check in search failed: {e}")

    try:
        fetch_limit = min(
            request.max_results + len(existing_leads),
            _MAX_CACHE_FETCH,
        )
        if fetch_limit < request.max_results + len(existing_leads):
            logger.info(
                "Buyer cache fetch capped at %d (pipeline has %d existing leads for requested HS codes)",
                _MAX_CACHE_FETCH, len(existing_leads),
            )

        service = BolSearchService()
        result = await service.search_companies(
            hs_codes=request.hs_codes,
            products=request.products,
            max_results=fetch_limit,
            supplier_country=request.supplier_country,
            user_email=user_email,
            auth_token=auth_token,
            db_name=user.get("db_name"),
            cache_only=True,
            is_onboarding=False,
            requested_results=request.max_results,
        )

        companies = result.get("companies", [])
        buyers_visible_limit = sub_info["entitlements"]["buyers"]["visible_limit"]
        if companies:
            companies = apply_trial_blur(companies, buyers_visible_limit)
            if not sub_info["entitlements"].get("show_buyer_emails", False):
                companies = redact_buyer_personnel_emails(companies)

        if existing_leads and companies:
            def _in_pipeline(c: dict) -> bool:
                loc_parts = [p for p in [c.get("city"), c.get("state")] if p]
                loc = ", ".join(loc_parts) if loc_parts else parse_city_state(c.get("address") or "")
                return (normalize_for_dedup(c.get("company_name")), normalize_for_dedup(loc)) in existing_leads
            companies = [c for c in companies if not _in_pipeline(c)]
        companies = companies[:request.max_results]

        if len(companies) >= 20:
            from importyeti.domain.scoring import normalize_scores
            raw_quick = [c.get("quick_score") or c.get("quickScore") or 0 for c in companies]
            normed = normalize_scores(raw_quick, max_score=100)
            for company, display in zip(companies, normed):
                if "quick_score" in company:
                    company["quick_score"] = display
                if "quickScore" in company:
                    company["quickScore"] = display

        result["companies"] = companies

        result["subscription"] = {
            "tier": tier,
            "onboardingStatus": onboarding_status,
            "trialDaysRemaining": sub_info["trialDaysRemaining"],
            "creditsUsedThisMonth": sub_info["creditsUsedThisMonth"],
            "monthlyCreditsRemaining": sub_info["monthlyCreditsRemaining"],
            "onboarding": sub_info.get("onboarding"),
        }

        if result.get("in_progress") and not cache_only_message:
            cache_only_message = ONBOARDING_WARMING_MESSAGE

        if cache_only_message:
            result["creditCapMessage"] = cache_only_message

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"BoL search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/importyeti/add-to-pipeline")
async def add_to_pipeline(
    request: AddToPipelineRequest,
    tenant=Depends(get_tenant_connection),
    authorization: str = Header(None),
):
    """
    Add one or more BoL companies to the leads pipeline.
    Fetches each from BoL cache and creates a lead with import_context
    and supplier_context (if deep-enriched).

    Enforces rank-within-visible_limit by score regardless of tier.
    Slugs outside the top-N visible by score return 422.
    """
    conn, user = tenant
    user_email = user.get("email", "unknown")
    auth_token = authorization.replace("Bearer ", "") if authorization else ""

    sub_info = await get_subscription_info(conn, user_email)
    visible_limit = sub_info["entitlements"]["buyers"]["visible_limit"]

    # Enforce that requested slugs come from the cohort produced by the client's
    # own submitted search params. Using the client's declared filters (not
    # tenant-wide HS codes) binds auth to the specific search the user saw —
    # a client lying about filters only gets what those filters allow.
    # The cohort reconstruction here mirrors /importyeti/search: overfetch by
    # existing-pipeline count, dedup, sort, remove in-pipeline slugs, slice.
    # Unlimited tenants (visible_limit == -1) skip the slice but still must
    # submit valid filters — slugs outside that cohort are rejected.
    existing_slugs_in_pipeline: set = set()
    try:
        hs_codes_for_query = [c.replace(".", "") for c in (request.hs_codes or []) if c]
        if hs_codes_for_query:
            rows = await conn.fetch(
                "SELECT import_context FROM leads "
                "WHERE import_context->'hsCodes' ?| $1::text[]",
                hs_codes_for_query,
            )
            for r in rows:
                ctx = r["import_context"] or {}
                slug_val = ctx.get("importyetiSlug") or ctx.get("importyeti_slug")
                if slug_val:
                    existing_slugs_in_pipeline.add(slug_val)
    except Exception as e:
        logger.warning(f"Add-to-pipeline existing-leads pre-check failed: {e}")

    fetch_limit = min(request.max_results + len(existing_slugs_in_pipeline), _MAX_CACHE_FETCH)
    all_cached = await internal_bol_client.search_cache(
        hs_codes=request.hs_codes or None,
        products=request.products or None,
        max_results=fetch_limit,
        auth_token=auth_token,
        slim=True,
    ) or []

    allowed_slugs: set = set()
    if all_cached:
        seen: Dict[str, Any] = {}
        for c in all_cached:
            slug_val = c.get("importyeti_slug") or c.get("importyetiSlug") or ""
            if not slug_val or slug_val in existing_slugs_in_pipeline:
                continue
            score = _best_score(c)
            if slug_val not in seen or score > _best_score(seen[slug_val]):
                seen[slug_val] = c
        # Secondary sort by supplier_slug for stable tie-breaking at the cutoff boundary.
        deduped = sorted(
            seen.values(),
            key=lambda r: (-_best_score(r), r.get("importyeti_slug") or r.get("importyetiSlug") or ""),
        )
        if visible_limit is not None and visible_limit >= 0:
            deduped = deduped[:visible_limit]
        allowed_slugs = {
            (c.get("importyeti_slug") or c.get("importyetiSlug")) for c in deduped
        }

    blocked = [s for s in request.slugs if s not in allowed_slugs]
    if blocked:
        cap_desc = "unlimited" if visible_limit is None or visible_limit < 0 else f"top {visible_limit}"
        raise HTTPException(
            status_code=422,
            detail={
                "error": "rank_violation",
                "message": (
                    f"Requested slugs are outside the {cap_desc} "
                    "visible companies by score for the submitted search."
                ),
                "blockedSlugs": blocked,
            },
        )

    return await add_slugs_to_pipeline(
        conn=conn,
        user=user,
        auth_token=auth_token,
        slugs=request.slugs,
    )
