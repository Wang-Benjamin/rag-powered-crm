"""ImportYeti onboarding endpoints."""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException

from importyeti.contracts.subscription import (
    ONBOARDING_WARMING_MESSAGE,
    claim_onboarding,
    get_subscription_info,
    get_tenant_hs_codes,
    get_tenant_products,
    set_onboarding_status,
    set_trial_started,
)
from service_core.db import get_tenant_connection

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/importyeti/onboarding/csv-kickoff")
async def csv_onboarding_kickoff(
    tenant=Depends(get_tenant_connection),
    authorization: str = Header(None),
):
    """CSV-bypass onboarding — skip PowerQuery entirely.

    Pre-requisites (all done via internal-leads-db ingest_csv.sh):
      - Buyer CSVs ingested into 8007 cache (bol_companies with hs_metrics JSONB)
      - Competitor CSVs ingested into 8007 cache (bol_competitor_companies with hs_metrics JSONB)

    Reads buyers from cache, deep-enriches top N, deep-enriches the configured competitor cap,
    computes scores, and populates the pipeline.
    """
    conn, user = tenant
    user_email = user.get("email", "unknown")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"error": "missing_auth", "message": "Authorization header required"})
    auth_token = authorization.replace("Bearer ", "")
    db_name = user.get("db_name")

    hs_data = await get_tenant_hs_codes(conn)
    confirmed_codes = [
        c.get("code").replace(".", "")
        for c in hs_data
        if c.get("confirmed") and c.get("code")
    ]
    products = await get_tenant_products(conn)
    if not confirmed_codes and not products:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "no_search_criteria",
                "message": "Cannot start onboarding — no confirmed HS codes or target products on tenant profile.",
            },
        )

    sub_info = await get_subscription_info(conn, user_email)
    current_status = sub_info["onboardingStatus"]

    if current_status == "complete":
        onboarding_meta = sub_info.get("onboarding") or {}
        return {
            "status": "already_complete",
            "buyersReady": onboarding_meta.get("buyersReady"),
            "competitorsReady": onboarding_meta.get("competitorsReady"),
        }

    won = await claim_onboarding(conn)
    if not won:
        sub_info = await get_subscription_info(conn, user_email)
        status_now = sub_info["onboardingStatus"]
        if status_now == "failed":
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "onboarding_failed",
                    "message": (
                        "Previous onboarding attempt failed. Run "
                        "scripts/post_onboard_recovery.py to finish any remaining work, "
                        "or have an admin reset tenant_subscription.bol_onboarding_status "
                        "to 'pending' to retry the full pipeline."
                    ),
                },
            )
        return {"status": "already_running", "message": ONBOARDING_WARMING_MESSAGE}

    try:
        tier = sub_info["tier"]
        if tier == "trial":
            await set_trial_started(conn)

        from importyeti.csv_onboarding import csv_onboard
        result = await csv_onboard(
            conn=conn,
            hs_codes=confirmed_codes,
            products=products,
            user_email=user_email,
            auth_token=auth_token,
            db_name=db_name,
        )

        status = result.get("status", "complete")
        response = {
            "status": status,
            "buyersInCache": result.get("buyers_in_cache", 0),
            "buyersEnriched": result.get("buyers_enriched", 0),
            "buyersWithContacts": result.get("buyers_with_contacts", 0),
            "competitorsEnriched": result.get("competitors_enriched", 0),
            "pipelineCreated": result.get("pipeline_created", 0),
        }
        if status == "failed":
            response["error"] = result.get("error", "csv_onboarding_failed")
            raise HTTPException(status_code=500, detail=response)
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CSV onboarding kickoff failed for {user_email}: {e}", exc_info=True)
        await set_onboarding_status(conn, user_email, "failed")
        raise HTTPException(
            status_code=500,
            detail={"error": "csv_onboarding_failed", "message": str(e)},
        )
