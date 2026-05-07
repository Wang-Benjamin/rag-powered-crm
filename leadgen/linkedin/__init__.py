"""
LinkedIn scraping feature module.

LinkedIn profile scraping, company research, and personnel data extraction
with compliance, rate limiting, and data enrichment capabilities.
"""

from .schemas import (
    LinkedInSearchRequest,
    LinkedInSearchResponse,
    LinkedInScrapeRequest,
    LinkedInBatchRequest,
    LinkedInProfile,
    LinkedInSearchResult,
    PersonnelData,
    CompanyProfile,
    CompanyResearchRequest,
    LinkedInJobMetrics,
    LinkedInEnrichmentRequest,
    WorkExperience,
    Education,
    Certification,
    LinkedInJobStatus,
    ScrapeReason,
    ProfilePrivacyLevel,
    ConnectionLevel
)

from .services import (
    LinkedInService,
    LinkedInScrapingError,
    LinkedInRateLimitError,
    get_linkedin_service
)

__all__ = [
    # Schemas
    "LinkedInSearchRequest",
    "LinkedInSearchResponse",
    "LinkedInScrapeRequest",
    "LinkedInBatchRequest",
    "LinkedInProfile",
    "LinkedInSearchResult",
    "PersonnelData",
    "CompanyProfile",
    "CompanyResearchRequest",
    "LinkedInJobMetrics",
    "LinkedInEnrichmentRequest",
    "WorkExperience",
    "Education",
    "Certification",
    "LinkedInJobStatus",
    "ScrapeReason",
    "ProfilePrivacyLevel",
    "ConnectionLevel",
    
    # Services
    "LinkedInService",
    "LinkedInScrapingError",
    "LinkedInRateLimitError",
    "get_linkedin_service"
]