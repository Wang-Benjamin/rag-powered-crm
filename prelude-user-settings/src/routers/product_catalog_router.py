"""
Product Catalog Router
======================
Tenant-scoped CRUD + publish flow for the storefront 待上线/已上线 tabs.

The ingestion router still owns the bulk-insert path for the
``product_pdf`` and ``product_csv`` lanes (see
``ingestion_router.commit_job``); rows it inserts default to
``status='pending'`` and surface here on the next list call. This router
covers everything else: read, manual add, edit, delete, and publish.

JSONB columns (``specs``, ``price_range``) are passed as Python dicts
directly. The connection-level codec in
``service_core.pool._init_connection`` encodes via ``json.dumps`` —
wrapping again would double-encode and produce a JSONB string scalar.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from data.repositories import product_catalog_repository as repo
from service_core.db import get_tenant_connection
from utils.json_helpers import parse_jsonb

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/product-catalog")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class PriceRange(BaseModel):
    min: Optional[float] = None
    max: Optional[float] = None
    currency: Optional[str] = None
    unit: Optional[str] = None


class ProductCatalogItem(BaseModel):
    product_id: str
    name: str
    description: Optional[str] = None
    specs: Dict[str, Any] = Field(default_factory=dict)
    image_url: Optional[str] = None
    moq: Optional[int] = None
    price_range: Optional[Dict[str, Any]] = None
    hs_code: Optional[str] = None
    source_job_id: Optional[str] = None
    status: str
    published_at: Optional[str] = None
    created_at: str
    updated_at: str


class ProductCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    specs: Optional[Dict[str, Any]] = None
    image_url: Optional[str] = None
    moq: Optional[int] = None
    price_range: Optional[PriceRange] = None
    hs_code: Optional[str] = None


class ProductUpdateRequest(BaseModel):
    """Partial update — every field optional. Status / published_at are
    deliberately not writable here; use the publish endpoints."""
    name: Optional[str] = Field(default=None, max_length=500)
    description: Optional[str] = None
    specs: Optional[Dict[str, Any]] = None
    image_url: Optional[str] = None
    moq: Optional[int] = None
    price_range: Optional[PriceRange] = None
    hs_code: Optional[str] = None


class BulkPublishRequest(BaseModel):
    product_ids: List[str] = Field(default_factory=list)


class ProductListResponse(BaseModel):
    success: bool
    products: List[ProductCatalogItem]


class ProductResponse(BaseModel):
    success: bool
    product: Optional[ProductCatalogItem] = None


class BulkPublishResponse(BaseModel):
    success: bool
    published_count: int
    products: List[ProductCatalogItem]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _row_to_item(row: dict) -> ProductCatalogItem:
    """Map a repository row dict to the response model."""
    return ProductCatalogItem(
        product_id=str(row["product_id"]),
        name=row["name"],
        description=row.get("description"),
        specs=parse_jsonb(row.get("specs")) or {},
        image_url=row.get("image_url"),
        moq=row.get("moq"),
        price_range=parse_jsonb(row.get("price_range")),
        hs_code=row.get("hs_code"),
        source_job_id=str(row["source_job_id"]) if row.get("source_job_id") else None,
        status=row["status"],
        published_at=_iso(row.get("published_at")),
        created_at=_iso(row["created_at"]) or "",
        updated_at=_iso(row["updated_at"]) or "",
    )


def _parse_uuid(value: str, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail=f"invalid {label}: {value!r}")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=ProductListResponse)
async def list_products_endpoint(
    status: Optional[str] = Query(default=None, pattern="^(pending|live)$"),
    tenant=Depends(get_tenant_connection),
):
    """List the caller's catalog rows, newest first.

    Optional ``?status=pending|live`` filter. The 待上线 tab uses
    ``status=pending``; the 已上线 tab uses ``status=live``. Omitting it
    returns everything, which is what ``StorefrontClient`` does on mount so
    the leave/enter publish animation can stay client-side.
    """
    conn, user = tenant
    user_email = user.get("email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        rows = await repo.list_products(conn, email=user_email, status=status)
        return ProductListResponse(
            success=True,
            products=[_row_to_item(r) for r in rows],
        )
    except Exception as e:
        logger.error(f"Error listing product catalog: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to list products: {str(e)}"
        )


@router.post("", response_model=ProductResponse)
async def create_product(
    request: ProductCreateRequest,
    tenant=Depends(get_tenant_connection),
):
    """Manual add. Inserts a row with ``status='pending'``."""
    conn, user = tenant
    user_email = user.get("email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        row = await repo.insert_product(
            conn,
            email=user_email,
            name=request.name,
            description=request.description,
            specs=request.specs,
            image_url=request.image_url,
            moq=request.moq,
            price_range=request.price_range.model_dump(exclude_none=True)
                if request.price_range
                else None,
            hs_code=request.hs_code,
        )
        return ProductResponse(success=True, product=_row_to_item(row))
    except Exception as e:
        logger.error(f"Error creating product: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create product: {str(e)}"
        )


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product_endpoint(
    product_id: str,
    request: ProductUpdateRequest,
    tenant=Depends(get_tenant_connection),
):
    """Partial update. 404 if the row doesn't belong to the caller."""
    conn, user = tenant
    user_email = user.get("email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    pid = _parse_uuid(product_id, "product_id")

    # Strip unset fields so we can distinguish "user wants to clear" from
    # "user didn't touch this". model_dump(exclude_unset=True) gives us the
    # patch semantics the repo helper expects.
    fields = request.model_dump(exclude_unset=True)
    if "price_range" in fields and request.price_range is not None:
        fields["price_range"] = request.price_range.model_dump(exclude_none=True)

    try:
        row = await repo.update_product(
            conn, product_id=pid, email=user_email, fields=fields,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Product not found")
        return ProductResponse(success=True, product=_row_to_item(row))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating product: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to update product: {str(e)}"
        )


@router.delete("/{product_id}")
async def delete_product_endpoint(
    product_id: str,
    tenant=Depends(get_tenant_connection),
):
    conn, user = tenant
    user_email = user.get("email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    pid = _parse_uuid(product_id, "product_id")

    try:
        deleted = await repo.delete_product(conn, product_id=pid, email=user_email)
        if not deleted:
            raise HTTPException(status_code=404, detail="Product not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting product: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to delete product: {str(e)}"
        )


@router.post("/{product_id}/publish", response_model=ProductResponse)
async def publish_product(
    product_id: str,
    tenant=Depends(get_tenant_connection),
):
    """Flip status to ``live``. Idempotent — published_at is preserved on
    re-publish via ``COALESCE(published_at, NOW())`` in the repo."""
    conn, user = tenant
    user_email = user.get("email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    pid = _parse_uuid(product_id, "product_id")

    try:
        row = await repo.set_status(
            conn, product_id=pid, email=user_email, status="live",
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Product not found")
        return ProductResponse(success=True, product=_row_to_item(row))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error publishing product: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to publish product: {str(e)}"
        )


@router.post("/publish-bulk", response_model=BulkPublishResponse)
async def publish_products_bulk(
    request: BulkPublishRequest,
    tenant=Depends(get_tenant_connection),
):
    """Bulk publish. Single transactional UPDATE; ids the caller doesn't
    own are silently skipped, mirroring the per-row 404 semantics applied
    across a list."""
    conn, user = tenant
    user_email = user.get("email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    parsed: list[uuid.UUID] = [
        _parse_uuid(pid, "product_id") for pid in request.product_ids
    ]

    try:
        async with conn.transaction():
            rows = await repo.set_status_bulk(
                conn, product_ids=parsed, email=user_email, status="live",
            )
        return BulkPublishResponse(
            success=True,
            published_count=len(rows),
            products=[_row_to_item(r) for r in rows],
        )
    except Exception as e:
        logger.error(f"Error bulk-publishing products: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to bulk-publish: {str(e)}"
        )
