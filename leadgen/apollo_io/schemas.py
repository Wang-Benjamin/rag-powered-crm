"""
Apollo.io schemas focused on essential lead data fields.

Streamlined data models optimized for the four most important lead fields:
- Company name
- Contact name
- Contact email  
- Website URL
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator


class ApolloSearchRequest(BaseModel):
    """Request model for Apollo.io lead search - focused on essential parameters."""
    
    # Core search parameters
    industry: str = Field(..., min_length=2, max_length=100, description="Industry or business type")
    location: str = Field(..., min_length=2, max_length=100, description="Geographic location")
    max_results: int = Field(default=50, ge=1, le=200, description="Maximum number of leads")

    # Optional company filters
    company_size: Optional[str] = Field(default=None, description="Company size (1-10, 11-50, 51-200, etc.)")
    keywords: Optional[List[str]] = Field(default=None, description="Additional search keywords")

    # Optional contact/people filters
    job_titles: Optional[List[str]] = Field(default=None, description="Specific job titles to target")
    department: Optional[str] = Field(default=None, description="Department to target")
    seniority_level: Optional[str] = Field(default=None, description="Seniority level filter")

    @field_validator('keywords')
    @classmethod
    def validate_keywords(cls, v):
        if v is not None and len(v) > 5:
            raise ValueError("Maximum 5 keywords allowed")
        return v

    @field_validator('job_titles')
    @classmethod
    def validate_job_titles(cls, v):
        if v is not None and len(v) > 10:
            raise ValueError("Maximum 10 job titles allowed")
        return v


class ApolloLead(BaseModel):
    """
    Simplified Apollo lead model focused on the four essential fields.
    Maps to existing frontend display requirements.
    """
    
    # Essential lead fields (the most important)
    company_name: str = Field(..., description="Business/company name")
    contact_name: Optional[str] = Field(default=None, description="Primary contact person name")
    contact_email: Optional[str] = Field(default=None, description="Primary contact email address")
    contact_phone: Optional[str] = Field(default=None, description="Primary contact phone number")
    website: Optional[str] = Field(default=None, description="Company website URL")
    
    # Additional context for compatibility with existing system
    industry: Optional[str] = Field(default=None, description="Company industry")
    location: Optional[str] = Field(default=None, description="Company location")
    title: Optional[str] = Field(default=None, description="Contact person title/position")
    
    # Scoring and metadata
    final_score: int = Field(default=50, ge=0, le=100, description="Lead quality score")
    source: str = Field(default="apollo", description="Data source identifier")
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Data extraction timestamp")
    
    # Apollo-specific metadata
    apollo_person_id: Optional[str] = Field(default=None, description="Apollo person ID")
    apollo_company_id: Optional[str] = Field(default=None, description="Apollo company ID")
    
    @field_validator('contact_email')
    @classmethod
    def validate_email(cls, v):
        if v and '@' not in v:
            return None  # Invalid email, set to None
        return v
    
    @field_validator('website')
    @classmethod
    def validate_website(cls, v):
        if v and not v.startswith(('http://', 'https://')):
            return f"https://{v}"
        return v


class ApolloSearchResponse(BaseModel):
    """Response model for Apollo.io search operations."""
    
    status: str = Field(..., description="Operation status")
    message: Optional[str] = Field(default=None, description="Status message")
    
    # Results focused on essential data
    leads: List[ApolloLead] = Field(default_factory=list, description="Extracted lead data")
    total_found: int = Field(default=0, description="Total leads found")
    
    # Quality metrics for the four essential fields
    leads_with_email: int = Field(default=0, description="Leads with valid email addresses")
    leads_with_website: int = Field(default=0, description="Leads with website URLs")
    leads_with_contact_name: int = Field(default=0, description="Leads with contact person names")
    leads_with_complete_data: int = Field(default=0, description="Leads with all four essential fields")
    
    # Timing
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Search start time")
    completed_at: Optional[datetime] = Field(default=None, description="Search completion time")
    duration_seconds: Optional[float] = Field(default=None, description="Total operation duration")
    
    # Error tracking
    errors: List[str] = Field(default_factory=list, description="Errors encountered")
    apollo_credits_used: Optional[int] = Field(default=None, description="Apollo API credits consumed")


class ApolloConfig(BaseModel):
    """Configuration for Apollo.io API integration."""
    
    # API settings
    api_key: str = Field(..., description="Apollo.io API key")
    base_url: str = Field(default="https://api.apollo.io", description="Apollo API base URL")
    
    # Rate limiting 
    requests_per_minute: int = Field(default=60, description="API requests per minute limit")
    timeout_seconds: int = Field(default=30, description="Request timeout")
    
    # Data quality settings
    require_email: bool = Field(default=True, description="Only return leads with email addresses")
    require_website: bool = Field(default=False, description="Only return leads with websites")
    min_lead_score: int = Field(default=30, description="Minimum lead quality score")
    
    # Search preferences
    prioritize_decision_makers: bool = Field(default=True, description="Prioritize C-level and VP contacts")
    exclude_generic_emails: bool = Field(default=True, description="Exclude info@, admin@ type emails")

    # Smart fetching parameters
    fetch_multiplier: float = Field(default=1.5, description="Initial raw leads multiplier")
    max_retry_attempts: int = Field(default=1, description="Max attempts to reach target")
    estimated_filter_rate: float = Field(default=0.7, description="Estimated filtering success rate")


class ApolloPreviewLead(BaseModel):
    """Preview lead without contact enrichment (Stage 1 - cheap)."""

    # Apollo IDs for enrichment (optional for internal DB leads)
    apollo_company_id: Optional[str] = Field(default=None, description="Apollo company ID for enrichment")

    # Company information only (no contact details)
    company_name: str = Field(..., description="Business/company name")
    website: Optional[str] = Field(default=None, description="Company website URL")
    industry: Optional[str] = Field(default=None, description="Company industry")
    location: Optional[str] = Field(default=None, description="Company location")
    employee_count: Optional[int] = Field(default=None, description="Number of employees")
    revenue_estimate: Optional[str] = Field(default=None, description="Estimated revenue range")
    description: Optional[str] = Field(default=None, description="Company description")
    company_size: Optional[str] = Field(default=None, description="Company size range")

    # Contact fields (populated for internal DB leads that are already enriched)
    contact_name: Optional[str] = Field(default=None, description="Contact name (for internal DB leads)")
    contact_email: Optional[str] = Field(default=None, description="Contact email (for internal DB leads)")
    contact_title: Optional[str] = Field(default=None, description="Contact title (for internal DB leads)")
    contact_phone: Optional[str] = Field(default=None, description="Contact phone (for internal DB leads)")
    is_decision_maker: bool = Field(default=False, description="Whether contact is a decision maker")

    # Source tracking (no underscore prefix - Pydantic V2 compatibility)
    lead_source: Optional[str] = Field(default="apollo", description="Lead source: 'apollo' or 'internal_db'")
    internal_company_id: Optional[str] = Field(default=None, description="Internal DB company ID")
    has_contact: bool = Field(default=False, description="Whether lead already has contact info")

    # Status flag
    is_enriched: bool = Field(default=False, description="Whether this lead has been enriched")
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Preview extraction timestamp")

    @field_validator('website')
    @classmethod
    def validate_website(cls, v):
        if v and not v.startswith(('http://', 'https://')):
            return f"https://{v}"
        return v


class ApolloEnrichedLead(ApolloPreviewLead):
    """Fully enriched lead with contact email (Stage 2 - expensive, email only, no phone)."""

    # Original company name for matching (when Apollo name differs from input)
    original_company_name: Optional[str] = Field(default=None, description="Original company name from Google Maps for matching")

    # Contact information (added after enrichment)
    contact_name: Optional[str] = Field(default=None, description="Decision maker name")
    contact_email: Optional[str] = Field(default=None, description="Decision maker email")
    contact_title: Optional[str] = Field(default=None, description="Decision maker job title")

    # Apollo person ID (added after enrichment)
    apollo_person_id: Optional[str] = Field(default=None, description="Apollo person ID")

    # NO phone field - email only enrichment

    # Update status flag
    is_enriched: bool = Field(default=True, description="This lead has been enriched with contact details")
    final_score: int = Field(default=50, ge=0, le=100, description="Lead quality score")

    @field_validator('contact_email')
    @classmethod
    def validate_email(cls, v):
        if v and '@' not in v:
            return None  # Invalid email, set to None
        return v


class ApolloPreviewResponse(BaseModel):
    """Response for preview search with automatic deduplication."""

    status: str = Field(..., description="Operation status")
    message: Optional[str] = Field(default=None, description="Status message")

    # Preview results
    leads: List[ApolloPreviewLead] = Field(default_factory=list, description="Preview lead data (no contact details)")
    total_found: int = Field(default=0, description="Total preview leads found")

    # Timing
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Search start time")
    completed_at: Optional[datetime] = Field(default=None, description="Search completion time")
    duration_seconds: Optional[float] = Field(default=None, description="Total operation duration")

    # Error tracking
    errors: List[str] = Field(default_factory=list, description="Errors encountered")

    # NO deduplication stats (silent in backend)


class ApolloEnrichmentRequest(BaseModel):
    """Request to enrich selected preview leads with contact details."""

    company_ids: List[str] = Field(..., description="Apollo company IDs to enrich")
    job_titles: Optional[List[str]] = Field(default=None, description="Specific job titles to target")
    department: Optional[str] = Field(default=None, description="Department to target")
    seniority_level: Optional[str] = Field(default=None, description="Seniority level filter")
    companies: Optional[List[Dict[str, Any]]] = Field(default=None, description="Full company data for hybrid enrichment")

    @field_validator('company_ids')
    @classmethod
    def validate_company_ids(cls, v):
        if not v or len(v) == 0:
            raise ValueError("At least one company ID required")
        if len(v) > 100:
            raise ValueError("Maximum 100 companies per enrichment request")
        return v


class ApolloEnrichmentResponse(BaseModel):
    """Response for enrichment operation."""

    status: str = Field(..., description="Operation status")
    message: Optional[str] = Field(default=None, description="Status message")

    # Enriched results (email only, no phone)
    leads: List[ApolloEnrichedLead] = Field(default_factory=list, description="Enriched leads with contact emails")
    total_enriched: int = Field(default=0, description="Total leads successfully enriched")
    failed_count: int = Field(default=0, description="Number of enrichments that failed")

    # Timing
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Enrichment start time")
    completed_at: Optional[datetime] = Field(default=None, description="Enrichment completion time")
    duration_seconds: Optional[float] = Field(default=None, description="Total operation duration")

    # Error tracking
    errors: List[str] = Field(default_factory=list, description="Errors encountered")


class ApolloApiError(Exception):
    """Apollo.io API specific exception."""

    def __init__(self, message: str, status_code: Optional[int] = None, apollo_error_code: Optional[str] = None):
        self.message = message
        self.status_code = status_code
        self.apollo_error_code = apollo_error_code
        super().__init__(message)


