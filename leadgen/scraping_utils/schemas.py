from pydantic import BaseModel, Field, HttpUrl, validator
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone
from enum import Enum

class RequestMethod(str, Enum):
    """HTTP request methods"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"

class ProxyStatus(str, Enum):
    """Proxy status types"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"
    TESTING = "testing"
    BANNED = "banned"
    RATE_LIMITED = "rate_limited"

class ProxyConfig(BaseModel):
    """Proxy configuration"""
    proxy_id: str = Field(..., description="Unique proxy identifier")
    host: str = Field(..., description="Proxy host")
    port: int = Field(..., ge=1, le=65535, description="Proxy port")
    protocol: str = Field(default="http", description="Proxy protocol (http, https, socks4, socks5)")
    
    # Authentication
    username: Optional[str] = Field(default=None, description="Proxy username")
    password: Optional[str] = Field(default=None, description="Proxy password")
    
    # Status and metrics
    status: ProxyStatus = Field(default=ProxyStatus.ACTIVE, description="Proxy status")
    success_rate: float = Field(default=100.0, ge=0.0, le=100.0, description="Success rate percentage")
    average_response_time: float = Field(default=0.0, ge=0.0, description="Average response time in seconds")
    last_used: Optional[datetime] = Field(default=None, description="Last usage timestamp")
    
    # Rate limiting
    requests_per_minute: Optional[int] = Field(default=None, ge=1, description="Requests per minute limit")
    concurrent_requests: int = Field(default=1, ge=1, le=10, description="Max concurrent requests")
    
    # Geographical and provider info
    country: Optional[str] = Field(default=None, description="Proxy country")
    provider: Optional[str] = Field(default=None, description="Proxy provider")
    cost_per_request: Optional[float] = Field(default=None, ge=0.0, description="Cost per request")
    
    # Failure tracking
    consecutive_failures: int = Field(default=0, ge=0, description="Consecutive failure count")
    total_requests: int = Field(default=0, ge=0, description="Total requests made")
    successful_requests: int = Field(default=0, ge=0, description="Successful requests")
    
    # Metadata
    tags: List[str] = Field(default_factory=list, description="Proxy tags")
    notes: Optional[str] = Field(default=None, description="Additional notes")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")
    
    @property
    def proxy_url(self) -> str:
        """Get full proxy URL"""
        if self.username and self.password:
            return f"{self.protocol}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.protocol}://{self.host}:{self.port}"

class RateLimitConfig(BaseModel):
    """Rate limiting configuration"""
    requests_per_second: float = Field(default=1.0, ge=0.1, le=100.0, description="Requests per second")
    requests_per_minute: int = Field(default=60, ge=1, le=6000, description="Requests per minute")
    requests_per_hour: int = Field(default=3600, ge=1, le=360000, description="Requests per hour")
    
    # Burst settings
    burst_size: int = Field(default=5, ge=1, le=100, description="Burst size for rate limiting")
    burst_window_seconds: int = Field(default=60, ge=1, le=3600, description="Burst window in seconds")
    
    # Backoff settings
    backoff_factor: float = Field(default=1.5, ge=1.0, le=10.0, description="Exponential backoff factor")
    max_backoff_seconds: int = Field(default=300, ge=1, le=3600, description="Maximum backoff time")
    
    # Domain-specific limits
    domain_limits: Dict[str, Dict[str, int]] = Field(default_factory=dict, description="Per-domain rate limits")
    
    # Recovery settings
    recovery_time_seconds: int = Field(default=3600, ge=60, description="Time to recover from rate limiting")
    adaptive_rate_limiting: bool = Field(default=True, description="Enable adaptive rate limiting")

class UserAgentRotation(BaseModel):
    """User agent rotation configuration"""
    enabled: bool = Field(default=True, description="Enable user agent rotation")
    rotation_frequency: int = Field(default=10, ge=1, le=1000, description="Rotate after N requests")
    
    # User agent lists
    desktop_agents: List[str] = Field(default_factory=list, description="Desktop user agents")
    mobile_agents: List[str] = Field(default_factory=list, description="Mobile user agents")
    tablet_agents: List[str] = Field(default_factory=list, description="Tablet user agents")
    
    # Device type preferences
    desktop_weight: float = Field(default=0.7, ge=0.0, le=1.0, description="Desktop agent probability")
    mobile_weight: float = Field(default=0.2, ge=0.0, le=1.0, description="Mobile agent probability")
    tablet_weight: float = Field(default=0.1, ge=0.0, le=1.0, description="Tablet agent probability")
    
    # Browser distribution
    browser_distribution: Dict[str, float] = Field(default_factory=dict, description="Browser usage distribution")
    
    @validator('desktop_weight', 'mobile_weight', 'tablet_weight')
    def validate_weights_sum(cls, v, values):
        weights = [v]
        if 'desktop_weight' in values:
            weights.append(values['desktop_weight'])
        if 'mobile_weight' in values:
            weights.append(values['mobile_weight'])
        
        if len(weights) == 3 and abs(sum(weights) - 1.0) > 0.01:
            raise ValueError('Device type weights must sum to 1.0')
        return v

class ProxyRotation(BaseModel):
    """Proxy rotation configuration"""
    enabled: bool = Field(default=True, description="Enable proxy rotation")
    rotation_strategy: str = Field(default="round_robin", description="Rotation strategy")
    rotation_frequency: int = Field(default=5, ge=1, le=100, description="Rotate after N requests")
    
    # Health checking
    health_check_enabled: bool = Field(default=True, description="Enable proxy health checking")
    health_check_interval: int = Field(default=300, ge=30, description="Health check interval in seconds")
    health_check_timeout: int = Field(default=10, ge=1, le=60, description="Health check timeout")
    
    # Failure handling
    max_consecutive_failures: int = Field(default=3, ge=1, le=10, description="Max consecutive failures before disabling")
    failure_recovery_time: int = Field(default=1800, ge=60, description="Time before retrying failed proxy")
    
    # Performance-based rotation
    performance_based: bool = Field(default=True, description="Use performance-based rotation")
    min_success_rate: float = Field(default=80.0, ge=0.0, le=100.0, description="Minimum success rate threshold")
    max_response_time: float = Field(default=30.0, ge=1.0, description="Maximum response time threshold")

class RetryPolicy(BaseModel):
    """Retry policy configuration"""
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum retry attempts")
    initial_delay: float = Field(default=1.0, ge=0.1, le=60.0, description="Initial retry delay in seconds")
    max_delay: float = Field(default=60.0, ge=1.0, le=300.0, description="Maximum retry delay")
    exponential_backoff: bool = Field(default=True, description="Use exponential backoff")
    
    # Retry conditions
    retry_on_status_codes: List[int] = Field(default_factory=lambda: [429, 500, 502, 503, 504], description="Status codes to retry on")
    retry_on_exceptions: List[str] = Field(default_factory=lambda: ["ConnectionError", "Timeout", "ReadTimeout"], description="Exception types to retry on")
    
    # Jitter
    jitter: bool = Field(default=True, description="Add random jitter to delays")
    jitter_factor: float = Field(default=0.1, ge=0.0, le=1.0, description="Jitter factor (0-1)")
    
    # Circuit breaker
    circuit_breaker_enabled: bool = Field(default=True, description="Enable circuit breaker")
    circuit_breaker_threshold: int = Field(default=5, ge=1, description="Failures before opening circuit")
    circuit_breaker_timeout: int = Field(default=300, ge=30, description="Circuit breaker timeout in seconds")

class RequestHeaders(BaseModel):
    """HTTP request headers configuration"""
    headers: Dict[str, str] = Field(default_factory=dict, description="Custom headers")
    
    # Common headers
    accept: str = Field(default="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", description="Accept header")
    accept_language: str = Field(default="en-US,en;q=0.5", description="Accept-Language header")
    accept_encoding: str = Field(default="gzip, deflate", description="Accept-Encoding header")
    
    # Browser simulation
    dnt: str = Field(default="1", description="Do Not Track header")
    upgrade_insecure_requests: str = Field(default="1", description="Upgrade-Insecure-Requests header")
    
    # Security headers
    sec_fetch_dest: Optional[str] = Field(default=None, description="Sec-Fetch-Dest header")
    sec_fetch_mode: Optional[str] = Field(default=None, description="Sec-Fetch-Mode header")
    sec_fetch_site: Optional[str] = Field(default=None, description="Sec-Fetch-Site header")
    
    # Custom header rotation
    rotate_headers: bool = Field(default=False, description="Rotate headers between requests")
    header_variations: List[Dict[str, str]] = Field(default_factory=list, description="Header variations for rotation")

class ScrapingSession(BaseModel):
    """Scraping session configuration"""
    session_id: str = Field(..., description="Unique session identifier")
    
    # Session settings
    persistent_cookies: bool = Field(default=True, description="Maintain cookies across requests")
    follow_redirects: bool = Field(default=True, description="Follow HTTP redirects")
    max_redirects: int = Field(default=10, ge=0, le=50, description="Maximum redirects to follow")
    
    # Timeouts
    connect_timeout: float = Field(default=10.0, ge=1.0, le=60.0, description="Connection timeout in seconds")
    read_timeout: float = Field(default=30.0, ge=1.0, le=300.0, description="Read timeout in seconds")
    total_timeout: float = Field(default=60.0, ge=1.0, le=600.0, description="Total request timeout")
    
    # SSL settings
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")
    ssl_context: Optional[Dict[str, Any]] = Field(default=None, description="Custom SSL context")
    
    # Connection pooling
    max_connections: int = Field(default=100, ge=1, le=1000, description="Maximum connections in pool")
    max_connections_per_host: int = Field(default=10, ge=1, le=100, description="Max connections per host")
    connection_keep_alive: bool = Field(default=True, description="Keep connections alive")
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Session creation time")
    last_used: Optional[datetime] = Field(default=None, description="Last usage timestamp")
    total_requests: int = Field(default=0, ge=0, description="Total requests made")
    successful_requests: int = Field(default=0, ge=0, description="Successful requests")

class ResponseData(BaseModel):
    """HTTP response data"""
    status_code: int = Field(..., description="HTTP status code")
    headers: Dict[str, str] = Field(default_factory=dict, description="Response headers")
    content: Optional[bytes] = Field(default=None, description="Response content (bytes)")
    text: Optional[str] = Field(default=None, description="Response text content")
    encoding: Optional[str] = Field(default=None, description="Response encoding")
    
    # Timing information
    response_time: float = Field(..., ge=0.0, description="Response time in seconds")
    dns_time: Optional[float] = Field(default=None, ge=0.0, description="DNS resolution time")
    connect_time: Optional[float] = Field(default=None, ge=0.0, description="Connection time")
    
    # Redirect information
    redirect_count: int = Field(default=0, ge=0, description="Number of redirects followed")
    final_url: Optional[HttpUrl] = Field(default=None, description="Final URL after redirects")
    
    # Response metadata
    content_length: Optional[int] = Field(default=None, ge=0, description="Content length in bytes")
    content_type: Optional[str] = Field(default=None, description="Content type")
    charset: Optional[str] = Field(default=None, description="Character set")
    
    # Proxy information
    proxy_used: Optional[str] = Field(default=None, description="Proxy used for request")
    user_agent_used: Optional[str] = Field(default=None, description="User agent used")

class ScrapingError(BaseModel):
    """Scraping error information"""
    error_type: str = Field(..., description="Type of error")
    error_message: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(default=None, description="Error code")
    
    # Request context
    url: Optional[HttpUrl] = Field(default=None, description="URL that failed")
    method: Optional[RequestMethod] = Field(default=None, description="HTTP method used")
    proxy_used: Optional[str] = Field(default=None, description="Proxy used")
    
    # Retry information
    retry_attempt: int = Field(default=0, ge=0, description="Retry attempt number")
    will_retry: bool = Field(default=False, description="Whether request will be retried")
    
    # Timing
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Error timestamp")
    
    # Additional context
    stack_trace: Optional[str] = Field(default=None, description="Error stack trace")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional error metadata")

class ScrapingMetrics(BaseModel):
    """Scraping performance metrics"""
    session_id: str = Field(..., description="Session identifier")
    
    # Request metrics
    total_requests: int = Field(default=0, ge=0, description="Total requests made")
    successful_requests: int = Field(default=0, ge=0, description="Successful requests")
    failed_requests: int = Field(default=0, ge=0, description="Failed requests")
    retried_requests: int = Field(default=0, ge=0, description="Requests that were retried")
    
    # Performance metrics
    average_response_time: float = Field(default=0.0, ge=0.0, description="Average response time in seconds")
    min_response_time: float = Field(default=0.0, ge=0.0, description="Minimum response time")
    max_response_time: float = Field(default=0.0, ge=0.0, description="Maximum response time")
    total_data_downloaded: int = Field(default=0, ge=0, description="Total data downloaded in bytes")
    
    # Rate limiting metrics
    rate_limited_count: int = Field(default=0, ge=0, description="Number of rate limited requests")
    backoff_time_total: float = Field(default=0.0, ge=0.0, description="Total backoff time in seconds")
    
    # Proxy metrics
    proxies_used: int = Field(default=0, ge=0, description="Number of different proxies used")
    proxy_failures: int = Field(default=0, ge=0, description="Proxy-related failures")
    
    # Error metrics
    error_types: Dict[str, int] = Field(default_factory=dict, description="Error types and counts")
    status_code_distribution: Dict[int, int] = Field(default_factory=dict, description="HTTP status code distribution")
    
    # Session timing
    session_start: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Session start time")
    session_end: Optional[datetime] = Field(default=None, description="Session end time")
    session_duration: Optional[float] = Field(default=None, ge=0.0, description="Session duration in seconds")
    
    # Efficiency metrics
    requests_per_second: Optional[float] = Field(default=None, ge=0.0, description="Requests per second")
    success_rate: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Success rate percentage")
    retry_rate: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Retry rate percentage")

class ScrapingRequest(BaseModel):
    """Scraping request configuration"""
    url: HttpUrl = Field(..., description="URL to scrape")
    method: RequestMethod = Field(default=RequestMethod.GET, description="HTTP method")
    
    # Request data
    headers: Optional[RequestHeaders] = Field(default=None, description="Request headers")
    params: Optional[Dict[str, Any]] = Field(default=None, description="URL parameters")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Request body data")
    json_data: Optional[Dict[str, Any]] = Field(default=None, description="JSON request data")
    
    # Session configuration
    session_id: Optional[str] = Field(default=None, description="Session to use")
    
    # Proxy and rotation settings
    use_proxy: bool = Field(default=True, description="Use proxy for request")
    preferred_proxy: Optional[str] = Field(default=None, description="Preferred proxy ID")
    rotate_user_agent: bool = Field(default=True, description="Rotate user agent")
    preferred_user_agent: Optional[str] = Field(default=None, description="Preferred user agent")
    
    # Rate limiting
    respect_rate_limits: bool = Field(default=True, description="Respect rate limiting")
    priority: int = Field(default=5, ge=1, le=10, description="Request priority (1=highest)")
    
    # Retry configuration
    retry_policy: Optional[RetryPolicy] = Field(default=None, description="Custom retry policy")
    
    # Output configuration
    return_content: bool = Field(default=True, description="Return response content")
    return_headers: bool = Field(default=True, description="Return response headers")
    save_to_file: Optional[str] = Field(default=None, description="Save response to file")
    
    # Metadata
    request_id: Optional[str] = Field(default=None, description="Request identifier")
    tags: List[str] = Field(default_factory=list, description="Request tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

class ScrapingResponse(BaseModel):
    """Scraping response"""
    request_id: str = Field(..., description="Request identifier")
    success: bool = Field(..., description="Whether request was successful")
    
    # Response data
    response_data: Optional[ResponseData] = Field(default=None, description="Response data if successful")
    error: Optional[ScrapingError] = Field(default=None, description="Error information if failed")
    
    # Request information
    original_url: HttpUrl = Field(..., description="Original requested URL")
    final_url: Optional[HttpUrl] = Field(default=None, description="Final URL after redirects")
    method: RequestMethod = Field(..., description="HTTP method used")
    
    # Execution details
    proxy_used: Optional[str] = Field(default=None, description="Proxy used for request")
    user_agent_used: Optional[str] = Field(default=None, description="User agent used")
    session_id: Optional[str] = Field(default=None, description="Session used")
    
    # Timing
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Request start time")
    completed_at: Optional[datetime] = Field(default=None, description="Request completion time")
    duration: Optional[float] = Field(default=None, ge=0.0, description="Request duration in seconds")
    
    # Retry information
    retry_attempts: int = Field(default=0, ge=0, description="Number of retry attempts made")
    final_attempt: bool = Field(default=True, description="Whether this was the final attempt")
    
    # Cache information
    from_cache: bool = Field(default=False, description="Whether response came from cache")
    cache_key: Optional[str] = Field(default=None, description="Cache key used")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional response metadata")

class ScrapingConfig(BaseModel):
    """Main scraping configuration"""
    # Service settings
    max_concurrent_requests: int = Field(default=10, ge=1, le=100, description="Maximum concurrent requests")
    max_sessions: int = Field(default=50, ge=1, le=500, description="Maximum number of sessions")
    
    # Default configurations
    default_rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig, description="Default rate limiting")
    default_retry_policy: RetryPolicy = Field(default_factory=RetryPolicy, description="Default retry policy")
    default_headers: RequestHeaders = Field(default_factory=RequestHeaders, description="Default headers")
    
    # Proxy configuration
    proxy_rotation: ProxyRotation = Field(default_factory=ProxyRotation, description="Proxy rotation settings")
    proxy_configs: List[ProxyConfig] = Field(default_factory=list, description="Available proxy configurations")
    
    # User agent configuration
    user_agent_rotation: UserAgentRotation = Field(default_factory=UserAgentRotation, description="User agent rotation")
    
    # Caching
    enable_caching: bool = Field(default=True, description="Enable response caching")
    cache_ttl_seconds: int = Field(default=3600, ge=60, description="Cache TTL in seconds")
    max_cache_size_mb: int = Field(default=1000, ge=10, description="Maximum cache size in MB")
    
    # Monitoring and logging
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    log_level: str = Field(default="INFO", description="Logging level")
    log_requests: bool = Field(default=False, description="Log individual requests")
    
    # Safety and compliance
    respect_robots_txt: bool = Field(default=True, description="Respect robots.txt")
    default_crawl_delay: float = Field(default=1.0, ge=0.1, description="Default crawl delay in seconds")
    
    # Session management
    session_timeout_seconds: int = Field(default=3600, ge=300, description="Session timeout")
    session_cleanup_interval: int = Field(default=600, ge=60, description="Session cleanup interval")
    
    class Config:
        extra = "allow"