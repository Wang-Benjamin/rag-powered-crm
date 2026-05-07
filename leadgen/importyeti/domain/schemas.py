"""Pydantic models for ImportYeti API responses and internal data."""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any


# === ImportYeti API Response Models ===

class ImportYetiBaseResponse(BaseModel):
    """Common fields in all ImportYeti API responses."""
    requestCost: Optional[float] = None
    creditsRemaining: Optional[float] = None
    executionTime: Optional[str] = None


class KeyCount(BaseModel):
    """Key-value pair with doc_count (used in PowerQuery aggregations)."""
    key: str
    doc_count: int = 0


class ContactInfo(BaseModel):
    """Contact info structure from ImportYeti."""
    emails: List[KeyCount] = []
    phone_numbers: List[KeyCount] = []


class PowerQueryCompany(BaseModel):
    """A single company from PowerQuery /us-import/companies response."""
    key: str  # Company name
    doc_count: int = 0  # Matching shipments for this HS code
    total_shipments: Optional[int] = None
    company_link: Optional[str] = None  # e.g. "/company/ikea-supply"
    company_country_code: Optional[str] = None
    company_address: Optional[List[KeyCount]] = None
    company_website: Optional[List[KeyCount]] = None
    company_contact_info: Optional[ContactInfo] = None
    notify_party_name: Optional[List[KeyCount]] = None
    notify_party_contact_info: Optional[ContactInfo] = None
    shipping_port: Optional[List[KeyCount]] = None
    port_of_entry: Optional[List[KeyCount]] = None
    product_description: Optional[List[KeyCount]] = None
    hs_code: Optional[List[KeyCount]] = None
    weight: Optional[float] = None
    teu: Optional[float] = None


class PowerQueryData(BaseModel):
    """Nested data object in PowerQuery companies response."""
    totalCompanies: Optional[int] = None
    data: List[PowerQueryCompany] = []


class PowerQueryCompaniesResponse(ImportYetiBaseResponse):
    """Response from GET /v1.0/powerquery/us-import/companies."""
    data: Optional[PowerQueryData] = None


class CompanyDetailResponse(ImportYetiBaseResponse):
    """Response from GET /v1.0/company/{company} (1 credit)."""
    data: Optional[Dict[str, Any]] = None  # Full company detail — too dynamic for strict typing


class ProductSupplier(BaseModel):
    """A single supplier from GET /v1.0/product/{product}/suppliers."""
    supplier_link: Optional[str] = None
    supplier_name: Optional[str] = None
    matching_shipments: Optional[int] = None
    specialization: Optional[float] = None
    supplier_country_code: Optional[str] = None
    supplier_address: Optional[str] = None
    supplier_total_shipments: Optional[int] = None
    supplier_experience: Optional[float] = None
    product_description: Optional[List[str]] = None
    customer_companies: Optional[List[str]] = None
    total_customers: Optional[int] = None
    weight: Optional[float] = None
    relevance_score: Optional[float] = None


class DatabaseUpdatedResponse(BaseModel):
    """Response from GET /v1.0/database-updated."""
    data: Optional[str] = None  # mm/dd/yyyy format
    executionTime: Optional[str] = None


# === Internal Models (parsed from ImportYeti for cache storage) ===

class ParsedBolCompany(BaseModel):
    """A company parsed from PowerQuery results, ready for cache storage."""
    importyeti_slug: str
    company_name: str
    company_total_shipments: Optional[int] = None
    total_suppliers: Optional[int] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "USA"
    website: Optional[str] = None
    shipping_ports: Optional[List[str]] = None
    ports_of_entry: Optional[List[str]] = None
    product_descriptions: Optional[List[str]] = None
    hs_codes: Optional[List[str]] = None
    # Per-query metrics (flattened from hs_metrics JSONB for the queried HS)
    matching_shipments: Optional[int] = None
    weight_kg: Optional[float] = None
    teu: Optional[float] = None
    # Deep enrichment fields (from /company/{company}, 1 credit)
    most_recent_shipment: Optional[str] = None
    avg_order_cycle_days: Optional[int] = None
    top_suppliers: Optional[List[str]] = None
    supplier_breakdown: Optional[List[Dict[str, Any]]] = None
    time_series: Optional[Dict[str, Any]] = None
    recent_bols: Optional[Dict[str, Any]] = None
    also_known_names: Optional[List[str]] = None
    phone_number: Optional[str] = None
    enrichment_status: str = "pending"
    ai_action_brief: Optional[str] = None
