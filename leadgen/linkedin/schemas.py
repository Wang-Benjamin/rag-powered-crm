"""
LinkedIn scraping schemas and models.

Pydantic models for LinkedIn profile scraping, company research,
and personnel data extraction.
"""

from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timezone
from pydantic import BaseModel, Field, HttpUrl, validator
from enum import Enum

from ..utils.validators import validate_email, validate_phone, validate_website, validate_company_name


class LinkedInJobStatus(str, Enum):
    """Status enumeration for LinkedIn scraping jobs."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class ScrapeReason(str, Enum):
    """Reasons for LinkedIn scraping operations."""
    LEAD_GENERATION = "lead_generation"
    TALENT_ACQUISITION = "talent_acquisition"
    MARKET_RESEARCH = "market_research"
    COMPETITIVE_ANALYSIS = "competitive_analysis"
    BUSINESS_INTELLIGENCE = "business_intelligence"


class ProfilePrivacyLevel(str, Enum):
    """LinkedIn profile privacy levels."""
    PUBLIC = "public"
    SEMI_PRIVATE = "semi_private"
    PRIVATE = "private"
    UNKNOWN = "unknown"


class ConnectionLevel(str, Enum):
    """LinkedIn connection levels."""
    FIRST = "1st"
    SECOND = "2nd"
    THIRD = "3rd"
    OUT_OF_NETWORK = "out_of_network"


class LinkedInSearchRequest(BaseModel):
    """Request model for LinkedIn search operations."""
    company_name: str = Field(..., min_length=2, max_length=200, description="Company name to search for")
    role_name: str = Field(..., min_length=2, max_length=100, description="Role/position to search for")
    num_results: int = Field(default=10, ge=1, le=100, description="Number of results to return")
    keywords: Optional[List[str]] = Field(default=None, description="Additional keywords for search")
    location: Optional[str] = Field(default=None, description="Geographic location filter")
    industry: Optional[str] = Field(default=None, description="Industry filter")
    seniority_level: Optional[str] = Field(default=None, description="Seniority level filter")
    company_size: Optional[str] = Field(default=None, description="Company size filter")
    scrape_profiles: bool = Field(default=True, description="Whether to scrape found profiles")
    scrape_reason: ScrapeReason = Field(default=ScrapeReason.LEAD_GENERATION, description="Reason for scraping")
    include_premium_data: bool = Field(default=False, description="Include premium LinkedIn data if available")
    
    @validator('keywords')
    def validate_keywords(cls, v):
        if v is not None:
            if len(v) > 10:
                raise ValueError("Maximum 10 keywords allowed")
            for keyword in v:
                if not keyword.strip() or len(keyword) > 50:
                    raise ValueError("Keywords must be 1-50 characters long")
        return v
    
    @validator('company_name')
    def validate_company(cls, v):
        return validate_company_name(v, required=True)


class LinkedInScrapeRequest(BaseModel):
    """Request model for direct LinkedIn profile scraping."""
    profile_urls: List[HttpUrl] = Field(..., min_items=1, max_items=100, description="LinkedIn profile URLs to scrape")
    scrape_reason: ScrapeReason = Field(default=ScrapeReason.LEAD_GENERATION, description="Reason for scraping")
    max_retries: int = Field(default=3, ge=1, le=10, description="Maximum retry attempts per profile")
    memory_threshold_mb: float = Field(default=200.0, ge=50.0, le=1000.0, description="Memory threshold for scraping")
    include_connections: bool = Field(default=False, description="Include connection information")
    include_recent_activity: bool = Field(default=False, description="Include recent LinkedIn activity")
    
    @validator('profile_urls')
    def validate_linkedin_urls(cls, v):
        for url in v:
            url_str = str(url)
            if 'linkedin.com' not in url_str or '/in/' not in url_str:
                raise ValueError(f"Invalid LinkedIn profile URL: {url_str}")
        return v


class LinkedInBatchRequest(BaseModel):
    """Request model for batch LinkedIn operations."""
    companies: List[str] = Field(..., min_items=1, max_items=50, description="List of company names to process")
    roles: List[str] = Field(..., min_items=1, max_items=20, description="List of roles to search for")
    max_results_per_company: int = Field(default=20, ge=1, le=100, description="Max results per company")
    scrape_reason: ScrapeReason = Field(default=ScrapeReason.LEAD_GENERATION, description="Reason for batch operation")
    location_filter: Optional[str] = Field(default=None, description="Location filter for all searches")
    priority_companies: Optional[List[str]] = Field(default=None, description="Companies to process first")
    
    @validator('companies')
    def validate_companies(cls, v):
        for company in v:
            validate_company_name(company, required=True)
        return v


class WorkExperience(BaseModel):
    """Work experience entry."""
    company: str = Field(..., description="Company name")
    position: str = Field(..., description="Job title/position")
    location: Optional[str] = Field(default=None, description="Job location")
    start_date: Optional[str] = Field(default=None, description="Start date")
    end_date: Optional[str] = Field(default=None, description="End date (null for current)")
    duration: Optional[str] = Field(default=None, description="Employment duration")
    description: Optional[str] = Field(default=None, description="Job description")
    skills_used: Optional[List[str]] = Field(default=None, description="Skills used in this role")
    is_current: bool = Field(default=False, description="Whether this is current employment")


class Education(BaseModel):
    """Education entry."""
    institution: str = Field(..., description="Educational institution")
    degree: Optional[str] = Field(default=None, description="Degree obtained")
    field_of_study: Optional[str] = Field(default=None, description="Field of study")
    start_year: Optional[int] = Field(default=None, description="Start year")
    end_year: Optional[int] = Field(default=None, description="End year")
    grade: Optional[str] = Field(default=None, description="Grade/GPA")
    activities: Optional[str] = Field(default=None, description="Activities and societies")


class Certification(BaseModel):
    """Professional certification."""
    name: str = Field(..., description="Certification name")
    issuing_organization: str = Field(..., description="Issuing organization")
    issue_date: Optional[str] = Field(default=None, description="Issue date")
    expiration_date: Optional[str] = Field(default=None, description="Expiration date")
    credential_id: Optional[str] = Field(default=None, description="Credential ID")
    credential_url: Optional[HttpUrl] = Field(default=None, description="Credential verification URL")


class PersonnelData(BaseModel):
    """Personnel data extracted from LinkedIn profiles."""
    # Basic information
    full_name: str = Field(..., description="Full name")
    first_name: Optional[str] = Field(default=None, description="First name")
    last_name: Optional[str] = Field(default=None, description="Last name")
    headline: Optional[str] = Field(default=None, description="Professional headline")
    location: Optional[str] = Field(default=None, description="Geographic location")
    about: Optional[str] = Field(default=None, description="About/summary section")
    
    # Contact information
    email: Optional[str] = Field(default=None, description="Email address")
    phone: Optional[str] = Field(default=None, description="Phone number")
    
    # Professional information
    current_company: Optional[str] = Field(default=None, description="Current company")
    current_position: Optional[str] = Field(default=None, description="Current job title")
    industry: Optional[str] = Field(default=None, description="Industry")
    seniority_level: Optional[str] = Field(default=None, description="Seniority level")
    
    # Profile metrics
    followers_count: Optional[int] = Field(default=None, description="Number of followers")
    connections_count: Optional[int] = Field(default=None, description="Number of connections")
    connection_level: Optional[ConnectionLevel] = Field(default=None, description="Connection level")
    
    # Professional history
    experience: List[WorkExperience] = Field(default_factory=list, description="Work experience")
    education: List[Education] = Field(default_factory=list, description="Education history")
    certifications: List[Certification] = Field(default_factory=list, description="Professional certifications")
    
    # Skills and expertise
    skills: List[str] = Field(default_factory=list, description="Skills and endorsements")
    languages: List[str] = Field(default_factory=list, description="Languages spoken")
    
    # Additional data
    volunteering: Optional[List[Dict[str, Any]]] = Field(default=None, description="Volunteer experience")
    awards: Optional[List[str]] = Field(default=None, description="Awards and honors")
    publications: Optional[List[Dict[str, Any]]] = Field(default=None, description="Publications")
    
    @validator('email')
    def validate_personnel_email(cls, v):
        return validate_email(v) if v else None
    
    @validator('phone')
    def validate_personnel_phone(cls, v):
        return validate_phone(v) if v else None


class LinkedInProfile(BaseModel):
    """Complete LinkedIn profile model."""
    # Identifiers
    profile_id: Optional[str] = Field(default=None, description="Internal profile ID")
    linkedin_url: HttpUrl = Field(..., description="LinkedIn profile URL")
    linkedin_id: Optional[str] = Field(default=None, description="LinkedIn internal ID")
    
    # Basic profile data
    personnel_data: PersonnelData = Field(..., description="Personnel information")
    
    # Profile metadata
    profile_image_url: Optional[HttpUrl] = Field(default=None, description="Profile picture URL")
    background_image_url: Optional[HttpUrl] = Field(default=None, description="Background image URL")
    privacy_level: ProfilePrivacyLevel = Field(default=ProfilePrivacyLevel.UNKNOWN, description="Profile privacy level")
    
    # Activity and engagement
    recent_activity: Optional[List[Dict[str, Any]]] = Field(default=None, description="Recent LinkedIn activity")
    mutual_connections: Optional[List[str]] = Field(default=None, description="Mutual connections")
    
    # Professional network
    company_size: Optional[str] = Field(default=None, description="Current company size")
    company_industry: Optional[str] = Field(default=None, description="Current company industry")
    company_website: Optional[HttpUrl] = Field(default=None, description="Current company website")
    
    # Data quality and scoring
    profile_completeness: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Profile completeness score")
    data_quality_score: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Data quality score")
    lead_score: Optional[int] = Field(default=None, ge=0, le=100, description="Lead priority score")
    
    # Scraping metadata
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When profile was scraped")
    scrape_reason: ScrapeReason = Field(..., description="Reason for scraping")
    scraped_by: Optional[str] = Field(default=None, description="User or system that scraped")
    memory_usage_mb: Optional[float] = Field(default=None, description="Memory usage during scraping")
    attempt_number: int = Field(default=1, description="Scraping attempt number")
    
    # Verification and enrichment
    email_verified: bool = Field(default=False, description="Whether email is verified")
    phone_verified: bool = Field(default=False, description="Whether phone is verified")
    enrichment_sources: List[str] = Field(default_factory=list, description="Sources used for data enrichment")


class LinkedInSearchResult(BaseModel):
    """Single search result from LinkedIn."""
    profile_url: HttpUrl = Field(..., description="LinkedIn profile URL")
    name: str = Field(..., description="Person's name")
    headline: Optional[str] = Field(default=None, description="Professional headline")
    location: Optional[str] = Field(default=None, description="Location")
    current_company: Optional[str] = Field(default=None, description="Current company")
    current_position: Optional[str] = Field(default=None, description="Current position")
    connection_level: Optional[ConnectionLevel] = Field(default=None, description="Connection level")
    profile_image_url: Optional[HttpUrl] = Field(default=None, description="Profile picture URL")
    premium_user: bool = Field(default=False, description="Whether user has LinkedIn Premium")
    
    # Search context
    search_relevance: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Search relevance score")
    search_position: Optional[int] = Field(default=None, description="Position in search results")


class LinkedInSearchResponse(BaseModel):
    """Response model for LinkedIn search operations."""
    status: str = Field(..., description="Operation status")
    message: Optional[str] = Field(default=None, description="Status message")
    
    # Search parameters
    search_request: LinkedInSearchRequest = Field(..., description="Original search request")
    
    # Search results
    results: List[LinkedInSearchResult] = Field(default_factory=list, description="Search results")
    total_found: int = Field(default=0, description="Total results found")
    
    # Scraped profiles (if requested)
    profiles: List[LinkedInProfile] = Field(default_factory=list, description="Fully scraped profiles")
    
    # Performance metrics
    search_time_seconds: Optional[float] = Field(default=None, description="Search execution time")
    scraping_time_seconds: Optional[float] = Field(default=None, description="Profile scraping time")
    success_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Scraping success rate")
    
    # Error handling
    errors: List[str] = Field(default_factory=list, description="Errors encountered")
    failed_profiles: List[str] = Field(default_factory=list, description="Profiles that failed to scrape")
    
    # Timestamps
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Search start time")
    completed_at: Optional[datetime] = Field(default=None, description="Search completion time")


class LinkedInJobMetrics(BaseModel):
    """Metrics for LinkedIn scraping jobs."""
    job_id: str = Field(..., description="Unique job identifier")
    status: LinkedInJobStatus = Field(..., description="Current job status")
    
    # Counts
    total_profiles_requested: int = Field(default=0, description="Total profiles requested")
    profiles_processed: int = Field(default=0, description="Profiles successfully processed")
    profiles_failed: int = Field(default=0, description="Profiles that failed")
    profiles_skipped: int = Field(default=0, description="Profiles skipped")
    
    # Performance
    average_processing_time: Optional[float] = Field(default=None, description="Average time per profile")
    memory_usage_peak_mb: Optional[float] = Field(default=None, description="Peak memory usage")
    rate_limit_hits: int = Field(default=0, description="Number of rate limit encounters")
    
    # Quality metrics
    data_completeness_avg: Optional[float] = Field(default=None, description="Average data completeness")
    profiles_with_email: int = Field(default=0, description="Profiles with email addresses")
    profiles_with_phone: int = Field(default=0, description="Profiles with phone numbers")
    
    # Timestamps
    started_at: datetime = Field(..., description="Job start time")
    completed_at: Optional[datetime] = Field(default=None, description="Job completion time")
    last_activity_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last activity timestamp")
    
    # Progress tracking
    progress_percentage: float = Field(default=0.0, ge=0.0, le=100.0, description="Job completion percentage")
    estimated_time_remaining: Optional[float] = Field(default=None, description="Estimated seconds remaining")


class CompanyResearchRequest(BaseModel):
    """Request for LinkedIn company research."""
    company_name: str = Field(..., description="Company name to research")
    include_employees: bool = Field(default=True, description="Include employee profiles")
    employee_limit: int = Field(default=50, ge=1, le=500, description="Maximum employees to extract")
    target_roles: Optional[List[str]] = Field(default=None, description="Specific roles to target")
    seniority_levels: Optional[List[str]] = Field(default=None, description="Target seniority levels")
    departments: Optional[List[str]] = Field(default=None, description="Target departments")
    
    @validator('company_name')
    def validate_research_company(cls, v):
        return validate_company_name(v, required=True)


class CompanyProfile(BaseModel):
    """LinkedIn company profile information."""
    company_name: str = Field(..., description="Company name")
    linkedin_url: Optional[HttpUrl] = Field(default=None, description="LinkedIn company page URL")
    website: Optional[HttpUrl] = Field(default=None, description="Company website")
    industry: Optional[str] = Field(default=None, description="Company industry")
    company_size: Optional[str] = Field(default=None, description="Company size range")
    headquarters: Optional[str] = Field(default=None, description="Headquarters location")
    founded_year: Optional[int] = Field(default=None, description="Year founded")
    
    # Company details
    description: Optional[str] = Field(default=None, description="Company description")
    specialties: List[str] = Field(default_factory=list, description="Company specialties")
    followers_count: Optional[int] = Field(default=None, description="LinkedIn followers")
    
    # Key personnel
    employees: List[PersonnelData] = Field(default_factory=list, description="Employee profiles")
    leadership_team: List[PersonnelData] = Field(default_factory=list, description="Leadership profiles")
    
    # Metadata
    research_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Research completion date")
    data_quality_score: Optional[float] = Field(default=None, description="Overall data quality score")


class LinkedInEnrichmentRequest(BaseModel):
    """Request for LinkedIn profile enrichment."""
    profiles: List[Dict[str, Any]] = Field(..., description="Profiles to enrich")
    enrichment_fields: List[str] = Field(default_factory=list, description="Specific fields to enrich")
    use_external_sources: bool = Field(default=False, description="Use external enrichment sources")
    verify_contact_info: bool = Field(default=False, description="Verify contact information")
    
    @validator('profiles')
    def validate_enrichment_profiles(cls, v):
        if len(v) > 100:
            raise ValueError("Maximum 100 profiles per enrichment request")
        return v