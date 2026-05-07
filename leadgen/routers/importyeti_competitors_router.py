"""ImportYeti competitor endpoints."""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from importyeti.competitors.service import BolCompetitorService, get_visible_competitor_slugs
from importyeti.contracts.subscription import get_subscription_info
from importyeti.domain.transformers import apply_competitor_blur
from service_core.db import get_tenant_connection

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/importyeti/competitors")
async def get_competitors(
    tenant=Depends(get_tenant_connection),
):
    """
    List competitors for current user with KPI summary.
    Visibility is tier-gated by the current subscription entitlements.
    """
    conn, user = tenant
    user_email = user.get("email", "unknown")

    sub_info = await get_subscription_info(conn, user_email)

    try:
        service = BolCompetitorService()
        result = await service.get_competitors(conn, user_email)

        visible_limit = sub_info["entitlements"]["competitors"]["visible_limit"]
        all_competitors = result.get("competitors", [])
        result["competitors"] = apply_competitor_blur(all_competitors, visible_limit)
        result["totalCompetitors"] = len(all_competitors)
        result["visibleLimit"] = visible_limit

        return result
    except Exception as e:
        logger.error(f"Competitor list error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/importyeti/competitor/{slug}")
async def get_competitor_detail(
    slug: str,
    tenant=Depends(get_tenant_connection),
    authorization: str = Header(None),
):
    """
    Get competitor detail. All competitors are pre-enriched at onboarding.
    Gated by the subscription-configured competitor visibility limit.
    """
    conn, user = tenant
    user_email = user.get("email", "unknown")
    auth_token = authorization.replace("Bearer ", "") if authorization else ""

    sub_info = await get_subscription_info(conn, user_email)

    visible_slugs = await get_visible_competitor_slugs(conn, sub_info)
    if slug not in visible_slugs:
        raise HTTPException(status_code=404, detail=f"Competitor not found: {slug}")

    try:
        service = BolCompetitorService()
        result = await service.get_competitor_detail(
            conn, slug, user_email, auth_token,
            skip_lazy_enrich=True,
        )
        if result is None:
            raise HTTPException(status_code=404, detail=f"Competitor not found: {slug}")

        result.pop("_lazy_enriched", None)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Competitor detail error for {slug}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class TrackRequest(BaseModel):
    is_tracked: bool


@router.post("/importyeti/competitor/{slug}/track")
async def track_competitor(
    slug: str,
    body: TrackRequest,
    tenant=Depends(get_tenant_connection),
):
    """Set tracking state for a competitor. Gated by visibility."""
    conn, user = tenant
    user_email = user.get("email", "unknown")

    sub_info = await get_subscription_info(conn, user_email)

    visible_slugs = await get_visible_competitor_slugs(conn, sub_info)
    if slug not in visible_slugs:
        raise HTTPException(status_code=404, detail=f"Competitor not found: {slug}")

    try:
        row = await conn.fetchrow(
            "UPDATE bol_competitors SET is_tracked = $1, last_updated_at = NOW() "
            "WHERE supplier_slug = $2 RETURNING supplier_slug, is_tracked",
            body.is_tracked, slug,
        )
        if not row:
            raise HTTPException(status_code=404, detail=f"Competitor not found: {slug}")
        return {"supplier_slug": row["supplier_slug"], "is_tracked": row["is_tracked"]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Track competitor error for {slug}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/importyeti/buyer/{lead_id}/competitors")
async def get_buyer_competitor_exposure(
    lead_id: str,
    tenant=Depends(get_tenant_connection),
    authorization: str = Header(None),
):
    """
    Return competitors whose overlap_buyer_slugs contains this lead.
    Shows which suppliers are selling to one of the user's leads (buyers).
    """
    conn, user = tenant
    user_email = user.get("email", "unknown")

    sub_info = await get_subscription_info(conn, user_email)

    try:
        from uuid import UUID
        UUID(lead_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid lead ID format: {lead_id}")

    lead = await conn.fetchrow(
        "SELECT lead_id, company FROM leads WHERE lead_id = $1::uuid",
        lead_id,
    )
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead not found: {lead_id}")

    try:
        # Join bol_competitors with this buyer's supplier_context.suppliers JSONB
        # (persisted on leads by lead_pipeline) to surface per-competitor share
        # of the buyer's purchases. Match on normalized supplier_name — both
        # sides originate from the same IY canonicalization, so verbatim matches
        # are the norm; LOWER+TRIM absorbs minor drift.
        rows = await conn.fetch(
            """
            WITH buyer_suppliers AS (
              -- DISTINCT ON de-dupes on normalized name (keeps highest-TEU entry).
              -- The jsonb_typeof guard protects against malformed legacy rows
              -- where supplier_context->'suppliers' exists but isn't an array.
              -- NB: we cast leads.lead_id to text so $1 stays text throughout
              -- the query — bc.overlap_buyer_slugs is text[], and mixing a
              -- uuid-typed $1 here breaks the `$1 = ANY(...)` check below.
              SELECT DISTINCT ON (LOWER(TRIM(s->>'name')))
                     LOWER(TRIM(s->>'name')) AS n,
                     (s->>'teu')::float      AS teu,
                     (s->>'share')::float    AS share
              FROM leads,
                   LATERAL jsonb_array_elements(supplier_context->'suppliers') AS s
              WHERE lead_id::text = $1
                AND supplier_context IS NOT NULL
                AND jsonb_typeof(supplier_context->'suppliers') = 'array'
              ORDER BY LOWER(TRIM(s->>'name')), (s->>'teu')::float DESC NULLS LAST
            )
            SELECT bc.supplier_slug, bc.supplier_name,
                   COALESCE(bc.threat_level, 'LOW')   AS threat_level,
                   COALESCE(bc.threat_score, 0)       AS threat_score,
                   bc.trend_yoy,
                   COALESCE(bc.matching_shipments, 0) AS matching_shipments,
                   COALESCE(bc.is_tracked, false)     AS is_tracked,
                   COALESCE(bs.teu,   0)              AS buyer_teu,
                   COALESCE(bs.share, 0)              AS buyer_share_pct
            FROM bol_competitors bc
            LEFT JOIN buyer_suppliers bs
              ON bs.n = LOWER(TRIM(bc.supplier_name))
            WHERE $1 = ANY(bc.overlap_buyer_slugs)
            ORDER BY bc.threat_score DESC NULLS LAST
            """,
            lead_id,
        )

        competitors = []
        for row in rows:
            competitors.append({
                "supplier_slug": row["supplier_slug"],
                "supplier_name": row["supplier_name"],
                "threat_level": row["threat_level"],
                "threat_score": row["threat_score"],
                "trend_yoy": row["trend_yoy"],
                "matching_shipments": row["matching_shipments"],
                "is_tracked": row["is_tracked"],
                "buyer_teu": row["buyer_teu"],
                "buyer_share_pct": row["buyer_share_pct"],
            })

        visible_limit = sub_info["entitlements"]["competitors"]["visible_limit"]
        competitors = apply_competitor_blur(competitors, visible_limit)

        return {
            "lead_id": lead_id,
            "company": lead["company"],
            "competitors": competitors,
            "total": len(competitors),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Buyer competitor exposure error for lead {lead_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
