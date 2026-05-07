"""
Scraping Utils feature module.

Shared scraping utilities, rate limiting, proxy management,
and common web scraping infrastructure.
"""

from .schemas import (
    ScrapingConfig,
    ProxyConfig,
    RateLimitConfig,
    ScrapingRequest,
    ScrapingResponse,
    ProxyRotation,
    UserAgentRotation,
    RetryPolicy,
    ScrapingSession,
    RequestHeaders,
    ResponseData,
    ScrapingMetrics,
    ProxyStatus,
    RequestMethod,
    ScrapingError
)

from .services import (
    ScrapingUtilsService,
    ProxyManager,
    RateLimiter,
    UserAgentManager,
    SessionManager,
    RetryManager,
    ScrapingUtilsError,
    get_scraping_utils_service
)

__all__ = [
    # Schemas
    "ScrapingConfig",
    "ProxyConfig",
    "RateLimitConfig",
    "ScrapingRequest",
    "ScrapingResponse",
    "ProxyRotation",
    "UserAgentRotation",
    "RetryPolicy",
    "ScrapingSession",
    "RequestHeaders",
    "ResponseData",
    "ScrapingMetrics",
    "ProxyStatus",
    "RequestMethod",
    "ScrapingError",
    
    # Services
    "ScrapingUtilsService",
    "ProxyManager",
    "RateLimiter",
    "UserAgentManager",
    "SessionManager",
    "RetryManager",
    "ScrapingUtilsError",
    "get_scraping_utils_service"
]