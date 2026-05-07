"""Pydantic draft schemas for the four document-ingestion lanes.

These are the typed shapes the extractors produce and that the frontend
pre-fills from. They are stored verbatim in ``ingestion_jobs.draft_payload``
until the user commits, at which point they are mapped to the authoritative
tables (``tenant_subscription``, ``factory_certifications``, ``product_catalog``).

All fields on the draft models are optional so partial extractions still
round-trip — the user reviews and edits before commit.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


JobKind = Literal["company_profile", "product_csv", "product_pdf", "certification"]
JobStatus = Literal[
    "queued",
    "processing",
    "ready_for_review",
    "committed",
    "failed",
    "discarded",
]

BusinessType = Literal["manufacturer", "trading", "oem", "odm", "other"]


class CompanyProfileDraft(BaseModel):
    """Extracted fields for the factory company profile (wizard step 1)."""

    company_name_en: Optional[str] = None
    company_name_local: Optional[str] = None
    year_founded: Optional[int] = None
    headquarters_location: Optional[str] = None
    employee_count_range: Optional[str] = None
    business_type: Optional[BusinessType] = None
    product_description: Optional[str] = None
    main_markets: list[str] = Field(default_factory=list)
    factory_location: Optional[str] = None
    factory_size_sqm: Optional[int] = None
    production_capacity: Optional[str] = None
    certifications_mentioned: list[str] = Field(default_factory=list)
    key_customers_mentioned: list[str] = Field(default_factory=list)


class PriceRange(BaseModel):
    """Optional structured price block on a product row."""

    min: Optional[float] = None
    max: Optional[float] = None
    currency: Optional[str] = None
    unit: Optional[str] = None


class ProductRecordDraft(BaseModel):
    """One product row — CSV or PDF lane."""

    name: str
    description: Optional[str] = None
    specs: dict[str, str] = Field(default_factory=dict)
    image_url: Optional[str] = None
    moq: Optional[int] = None
    price_range: Optional[PriceRange] = None
    hs_code_suggestion: Optional[str] = None


class ProductCatalogDraft(BaseModel):
    """Full catalog draft — wraps the row list plus optional CSV-lane mapping."""

    products: list[ProductRecordDraft] = Field(default_factory=list)
    column_mapping: Optional[dict[str, str]] = None


class CertificationDraft(BaseModel):
    """Extracted fields for a single certification document.

    Mirrors the ``factory_certifications`` columns exactly. Dates are ISO-8601
    strings so the draft JSON round-trips cleanly; the commit path parses them.
    """

    cert_type: Optional[str] = None
    cert_number: Optional[str] = None
    issuing_body: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    notes: Optional[str] = None
