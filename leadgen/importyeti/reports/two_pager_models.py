"""Pydantic models for the Two-Pager report response.

Defines the API shape returned from POST /importyeti/two-pager. Consumed by
the frontend TwoPagerPage1 (stats + buyers table) and TwoPagerPage2
(top-3 contact cards with outreach emails).
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class Buyer(BaseModel):
    rank: int
    slug: str
    name: str
    city: Optional[str] = None
    state: Optional[str] = None
    # Real ImportYeti volume signals — replaces the old hardcoded
    # weight × FOB-per-kg estimate (which was never sourced from
    # actual procurement data, only an internal price table).
    annual_volume_tons: Optional[float] = None
    containers_count: Optional[int] = None
    hs_shipments_count: Optional[int] = None
    cn_prev_supplier_count: int = 0
    cn_curr_supplier_count: int = 0
    trend_yoy_pct: Optional[float] = None
    score: int = 0


class BuyerContact(BaseModel):
    buyer_slug: str
    buyer_name: str
    score: int
    location: Optional[str] = None
    annual_volume_tons: Optional[float] = None
    containers_count: Optional[int] = None
    hs_shipments_count: Optional[int] = None
    trend_yoy_pct: Optional[float] = None
    cn_prev_supplier_count: int = 0
    cn_curr_supplier_count: int = 0
    cn_subheader: str = ""

    # Apollo contact (None when fetch_status != "found")
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    contact_email: Optional[str] = None
    fetch_status: str = "not_found"  # "found" | "not_found" | "failed"

    # GPT-5.4-mini outreach email (None when LLM skipped or no contact)
    email_subject: Optional[str] = None
    email_body: Optional[str] = None

    # True when contact name/title/email were AI-mocked because Apollo had no
    # real match. The frontend treats synthesized and real contacts identically;
    # this flag is metadata for backend logging / cache write-back gating.
    is_synthesized: bool = False


class CategoryStats(BaseModel):
    # Sum across the top-15 buyer table — annualized from the 6-month
    # query window. Tons replaces the old USD estimate.
    total_import_tons: Optional[float] = None
    total_containers: Optional[int] = None
    total_hs_shipments: Optional[int] = None
    yoy_growth_pct: Optional[float] = None
    active_importer_count: Optional[int] = None
    # None when supplier_breakdown was empty for every top-15 buyer —
    # frontend renders "—" with a "数据不足" caption rather than a
    # synthetic placeholder.
    supplier_churn_pct: Optional[float] = None


class TwoPagerRequest(BaseModel):
    hs_code: Optional[str] = Field(None, description="HS code (e.g. '9405.42' or '940542')")
    product_description: Optional[str] = Field(
        None, description="Free-text product search (PowerQuery syntax: boolean, wildcards)"
    )

    @model_validator(mode="after")
    def require_at_least_one(self) -> "TwoPagerRequest":
        if not self.hs_code and not self.product_description:
            raise ValueError("Either hs_code or product_description must be provided")
        return self


class TwoPagerResponse(BaseModel):
    hs_code: Optional[str] = None
    product_description: Optional[str] = None
    # Display labels for Page 1 / Page 2 headers. EN side falls back to
    # the raw product_description (or HS code) when the request used HS
    # mode and no human-readable label was provided.
    hs_code_description: Optional[str] = None
    hs_code_description_cn: Optional[str] = None
    stats: CategoryStats
    buyers: List[Buyer] = []  # top 15
    buyer_contacts: List[BuyerContact] = []  # top 3
    generated_at: str
    warnings: List[str] = []


class TwoPagerBatchItem(BaseModel):
    hs_code: str


class TwoPagerBatchRequest(BaseModel):
    items: List[TwoPagerBatchItem] = Field(..., min_length=1, max_length=14)


class TwoPagerBatchError(BaseModel):
    hs_code: str
    status: str = "error"
    message: str
    elapsed_ms: int


class TwoPagerBatchResult(BaseModel):
    """Either data is present (success) or error is present (failure). Never both."""
    hs_code: str
    data: Optional[TwoPagerResponse] = None
    error: Optional[TwoPagerBatchError] = None


class TwoPagerBatchResponse(BaseModel):
    results: List[TwoPagerBatchResult]
    total: int
    succeeded: int
    failed: int
    elapsed_ms: int
