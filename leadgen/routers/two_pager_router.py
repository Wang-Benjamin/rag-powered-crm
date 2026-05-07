"""Two-Pager report endpoint — generates 2-page market intelligence for a single HS code."""

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from service_core.db import get_tenant_connection
from importyeti.reports.two_pager_models import (
    TwoPagerBatchError,
    TwoPagerBatchItem,
    TwoPagerBatchRequest,
    TwoPagerBatchResponse,
    TwoPagerBatchResult,
    TwoPagerRequest,
    TwoPagerResponse,
)
from importyeti.reports.two_pager_service import TwoPagerService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/importyeti/two-pager", response_model=TwoPagerResponse)
async def generate_two_pager(
    request: TwoPagerRequest,
    tenant=Depends(get_tenant_connection),
    authorization: str = Header(None),
):
    """
    Generate a two-pager market intelligence report for a given HS code.

    Cache-first buyer fetch from internal leads DB. Partial re-enrichment on
    top-15 buyers missing supplier_breakdown. Apollo contacts + AI outreach
    emails for the top 3 buyers are filled in by TwoPagerService (A5).
    """
    conn, user = tenant
    user_email = user.get("email", "unknown")
    auth_token = authorization.replace("Bearer ", "") if authorization else ""

    # Rollback gate: when ENABLE_PRODUCT_DESCRIPTION_MODE=false, drop product_description
    # or 422 if no hs_code is also present.
    if os.getenv("ENABLE_PRODUCT_DESCRIPTION_MODE", "true").lower() != "true":
        if request.product_description and not request.hs_code:
            raise HTTPException(status_code=422, detail="product_description mode is disabled")
        # If both set, silently drop product_description
        request = request.model_copy(update={"product_description": None})

    logger.info(
        "[TwoPager] Generating report hs_code=%s product_description=%s user=%s",
        request.hs_code,
        request.product_description,
        user_email,
    )

    service = TwoPagerService()
    # TODO(phase3): generate_report dual-mode — widen signature to accept product_description
    report = await service.generate_report(
        hs_code=request.hs_code,
        product_description=request.product_description,
        user_email=user_email,
        conn=conn,
        auth_token=auth_token,
    )

    logger.info(
        "[TwoPager] Report generated hs_code=%s: %d buyers, %d contacts, %d warnings",
        request.hs_code,
        len(report.buyers),
        len(report.buyer_contacts),
        len(report.warnings),
    )

    return report


@router.post("/importyeti/two-pager/batch", response_model=TwoPagerBatchResponse)
async def generate_two_pager_batch(
    request: TwoPagerBatchRequest,
    tenant=Depends(get_tenant_connection),
    authorization: str = Header(None),
):
    """
    Generate two-pager reports for up to 14 HS codes in a single request.

    Runs up to 5 reports concurrently. Always returns 200 — per-item failures
    are captured in the result's error field rather than aborting the batch.
    """
    conn, user = tenant
    user_email = user.get("email", "unknown")
    auth_token = authorization.replace("Bearer ", "") if authorization else ""
    logger.info(
        "[TwoPager/batch] Starting batch for %d items (user=%s)",
        len(request.items),
        user_email,
    )

    t0 = time.perf_counter()
    svc = TwoPagerService()
    sem = asyncio.Semaphore(5)

    async def _one(item: TwoPagerBatchItem) -> TwoPagerBatchResult:
        async with sem:
            t_item = time.perf_counter()
            try:
                data = await svc.generate_report(
                    hs_code=item.hs_code,
                    conn=None,  # never share the tenant conn across concurrent tasks
                    auth_token=auth_token,
                )
                return TwoPagerBatchResult(hs_code=item.hs_code, data=data)
            except Exception as e:
                elapsed = int((time.perf_counter() - t_item) * 1000)
                logger.exception("[TwoPager/batch] %s failed", item.hs_code)
                return TwoPagerBatchResult(
                    hs_code=item.hs_code,
                    error=TwoPagerBatchError(
                        hs_code=item.hs_code,
                        message=str(e)[:500],
                        elapsed_ms=elapsed,
                    ),
                )

    results = await asyncio.gather(*[_one(i) for i in request.items])
    succeeded = sum(1 for r in results if r.data is not None)
    failed = len(results) - succeeded
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    logger.info(
        "[TwoPager/batch] metrics total=%d succeeded=%d failed=%d elapsed_ms=%d credits_est=%d",
        len(results),
        succeeded,
        failed,
        elapsed_ms,
        len(results) * 18,
    )

    return TwoPagerBatchResponse(
        results=list(results),
        total=len(results),
        succeeded=succeeded,
        failed=failed,
        elapsed_ms=elapsed_ms,
    )


# Removed 2026-04-25: the /importyeti/two-pager/demo-fill route was a
# user-triggered ghost-slot filler that the new auto-synth flow in
# two_pager_service.py now handles inline (every Page 2 card is filled —
# real or synth — server-side, before the report is returned). The route
# was orphaned by the frontend simplification and lacked tenant-context auth,
# so deleting it both shrinks the surface area and closes that gap.
