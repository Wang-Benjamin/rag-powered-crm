import asyncio
import aiohttp
import random
import time
import uuid
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
import logging
from urllib.parse import urljoin, urlparse
import hashlib
import json
from copy import deepcopy

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

logger = logging.getLogger(__name__)

class ScrapingUtilsError(Exception):
    """Scraping utils specific errors"""
    pass

@dataclass
class RequestStats:
    """Statistics for individual requests"""
    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    total_response_time: float = 0.0
    last_attempt_time: Optional[datetime] = None

class RateLimiter:
    """Rate limiter for web scraping requests"""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.request_times: List[float] = []
        self.domain_request_times: Dict[str, List[float]] = {}
        self.last_request_time = 0.0
        self.burst_tokens = config.burst_size
        self.last_token_refill = time.time()
    
    async def acquire(self, url: str) -> float:
        """Acquire permission to make a request, returns delay in seconds"""
        domain = urlparse(url).netloc
        current_time = time.time()
        
        # Refill burst tokens
        time_passed = current_time - self.last_token_refill
        self.burst_tokens = min(
            self.config.burst_size,
            self.burst_tokens + time_passed / (1.0 / self.config.requests_per_second)
        )
        self.last_token_refill = current_time
        
        # Check if we have burst tokens available
        if self.burst_tokens >= 1.0:
            self.burst_tokens -= 1.0
            return 0.0
        
        # Calculate delay based on rate limits
        delay = self._calculate_delay(domain, current_time)
        
        if delay > 0:
            await asyncio.sleep(delay)
        
        # Record request time
        self._record_request(domain, current_time + delay)
        
        return delay
    
    def _calculate_delay(self, domain: str, current_time: float) -> float:
        """Calculate required delay based on rate limits"""
        delays = []
        
        # Global rate limit
        if self.last_request_time > 0:
            min_interval = 1.0 / self.config.requests_per_second
            time_since_last = current_time - self.last_request_time
            if time_since_last < min_interval:
                delays.append(min_interval - time_since_last)
        
        # Domain-specific rate limits
        if domain in self.config.domain_limits:
            domain_config = self.config.domain_limits[domain]
            domain_times = self.domain_request_times.get(domain, [])
            
            # Check requests per second for domain
            if 'requests_per_second' in domain_config:
                domain_rps = domain_config['requests_per_second']
                if domain_times:
                    min_interval = 1.0 / domain_rps
                    time_since_last = current_time - domain_times[-1]
                    if time_since_last < min_interval:
                        delays.append(min_interval - time_since_last)
        
        return max(delays) if delays else 0.0
    
    def _record_request(self, domain: str, request_time: float):
        """Record a request time for rate limiting calculations"""
        self.last_request_time = request_time
        
        # Clean up old request times (keep last hour)
        cutoff_time = request_time - 3600
        self.request_times = [t for t in self.request_times if t > cutoff_time]
        self.request_times.append(request_time)
        
        # Domain-specific tracking
        if domain not in self.domain_request_times:
            self.domain_request_times[domain] = []
        
        domain_times = self.domain_request_times[domain]
        domain_times = [t for t in domain_times if t > cutoff_time]
        domain_times.append(request_time)
        self.domain_request_times[domain] = domain_times
    
    def get_current_rate(self, domain: Optional[str] = None) -> float:
        """Get current request rate (requests per second)"""
        current_time = time.time()
        window_start = current_time - 60  # Last minute
        
        if domain:
            recent_requests = [t for t in self.domain_request_times.get(domain, []) if t > window_start]
        else:
            recent_requests = [t for t in self.request_times if t > window_start]
        
        return len(recent_requests) / 60.0

class ProxyManager:
    """Manages proxy rotation and health monitoring"""
    
    def __init__(self, proxy_configs: List[ProxyConfig], rotation_config: ProxyRotation):
        self.proxies = {proxy.proxy_id: proxy for proxy in proxy_configs}
        self.rotation_config = rotation_config
        self.current_proxy_index = 0
        self.proxy_usage_count: Dict[str, int] = {}
        self.proxy_last_used: Dict[str, datetime] = {}
        self.failed_proxies: Dict[str, datetime] = {}
    
    def get_next_proxy(self) -> Optional[ProxyConfig]:
        """Get the next proxy to use based on rotation strategy"""
        if not self.rotation_config.enabled:
            return None
        
        active_proxies = self._get_active_proxies()
        if not active_proxies:
            return None
        
        if self.rotation_config.rotation_strategy == "round_robin":
            return self._round_robin_selection(active_proxies)
        elif self.rotation_config.rotation_strategy == "random":
            return random.choice(active_proxies)
        elif self.rotation_config.rotation_strategy == "performance_based":
            return self._performance_based_selection(active_proxies)
        else:
            return self._round_robin_selection(active_proxies)
    
    def _get_active_proxies(self) -> List[ProxyConfig]:
        """Get list of currently active proxies"""
        active_proxies = []
        current_time = datetime.now(timezone.utc)
        
        for proxy in self.proxies.values():
            # Skip if proxy is disabled
            if proxy.status != ProxyStatus.ACTIVE:
                continue
            
            # Skip if proxy is in failure recovery period
            if proxy.proxy_id in self.failed_proxies:
                failure_time = self.failed_proxies[proxy.proxy_id]
                recovery_time = failure_time + timedelta(seconds=self.rotation_config.failure_recovery_time)
                if current_time < recovery_time:
                    continue
                else:
                    # Remove from failed list as recovery period has passed
                    del self.failed_proxies[proxy.proxy_id]
            
            # Check if proxy meets quality thresholds
            if (proxy.success_rate < self.rotation_config.min_success_rate or
                proxy.average_response_time > self.rotation_config.max_response_time):
                continue
            
            active_proxies.append(proxy)
        
        return active_proxies
    
    def _round_robin_selection(self, proxies: List[ProxyConfig]) -> ProxyConfig:
        """Select proxy using round-robin strategy"""
        if self.current_proxy_index >= len(proxies):
            self.current_proxy_index = 0
        
        proxy = proxies[self.current_proxy_index]
        self.current_proxy_index += 1
        
        return proxy
    
    def _performance_based_selection(self, proxies: List[ProxyConfig]) -> ProxyConfig:
        """Select proxy based on performance metrics"""
        if not proxies:
            return None
        
        # Calculate weights based on success rate and response time
        weights = []
        for proxy in proxies:
            # Higher weight for higher success rate and lower response time
            success_weight = proxy.success_rate / 100.0
            time_weight = 1.0 / (proxy.average_response_time + 0.1)  # Avoid division by zero
            combined_weight = success_weight * time_weight
            weights.append(combined_weight)
        
        # Weighted random selection
        total_weight = sum(weights)
        if total_weight == 0:
            return random.choice(proxies)
        
        random_value = random.uniform(0, total_weight)
        cumulative_weight = 0
        
        for i, weight in enumerate(weights):
            cumulative_weight += weight
            if random_value <= cumulative_weight:
                return proxies[i]
        
        return proxies[-1]  # Fallback
    
    def record_proxy_usage(self, proxy_id: str, success: bool, response_time: float):
        """Record proxy usage statistics"""
        if proxy_id not in self.proxies:
            return
        
        proxy = self.proxies[proxy_id]
        proxy.last_used = datetime.now(timezone.utc)
        proxy.total_requests += 1
        
        if success:
            proxy.successful_requests += 1
            proxy.consecutive_failures = 0
            
            # Remove from failed list if it was there
            if proxy_id in self.failed_proxies:
                del self.failed_proxies[proxy_id]
        else:
            proxy.consecutive_failures += 1
            
            # Mark as failed if too many consecutive failures
            if proxy.consecutive_failures >= self.rotation_config.max_consecutive_failures:
                proxy.status = ProxyStatus.FAILED
                self.failed_proxies[proxy_id] = datetime.now(timezone.utc)
        
        # Update success rate
        proxy.success_rate = (proxy.successful_requests / proxy.total_requests) * 100
        
        # Update average response time (exponential moving average)
        if proxy.average_response_time == 0:
            proxy.average_response_time = response_time
        else:
            alpha = 0.1  # Smoothing factor
            proxy.average_response_time = (alpha * response_time + 
                                          (1 - alpha) * proxy.average_response_time)
    
    async def health_check_proxy(self, proxy: ProxyConfig) -> bool:
        """Perform health check on a proxy"""
        try:
            # Simple health check by making a request to a reliable endpoint
            health_check_url = "http://httpbin.org/ip"
            
            proxy_url = proxy.proxy_url
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.rotation_config.health_check_timeout)
            ) as session:
                async with session.get(health_check_url, proxy=proxy_url) as response:
                    if response.status == 200:
                        proxy.status = ProxyStatus.ACTIVE
                        return True
                    else:
                        proxy.status = ProxyStatus.FAILED
                        return False
        
        except Exception as e:
            logger.debug(f"Health check failed for proxy {proxy.proxy_id}: {e}")
            proxy.status = ProxyStatus.FAILED
            return False
    
    async def run_health_checks(self):
        """Run health checks on all proxies"""
        if not self.rotation_config.health_check_enabled:
            return
        
        health_check_tasks = []
        for proxy in self.proxies.values():
            task = asyncio.create_task(self.health_check_proxy(proxy))
            health_check_tasks.append(task)
        
        if health_check_tasks:
            await asyncio.gather(*health_check_tasks, return_exceptions=True)

class UserAgentManager:
    """Manages user agent rotation"""
    
    def __init__(self, config: UserAgentRotation):
        self.config = config
        self.request_count = 0
        self.current_user_agent = None
        
        # Default user agents if none provided
        if not self.config.desktop_agents:
            self.config.desktop_agents = self._get_default_desktop_agents()
        if not self.config.mobile_agents:
            self.config.mobile_agents = self._get_default_mobile_agents()
    
    def get_user_agent(self) -> str:
        """Get a user agent based on rotation configuration"""
        if not self.config.enabled:
            return self._get_default_user_agent()
        
        # Rotate user agent based on frequency
        if (self.current_user_agent is None or 
            self.request_count % self.config.rotation_frequency == 0):
            self.current_user_agent = self._select_user_agent()
        
        self.request_count += 1
        return self.current_user_agent
    
    def _select_user_agent(self) -> str:
        """Select a user agent based on device weights"""
        # Normalize weights
        total_weight = (self.config.desktop_weight + 
                       self.config.mobile_weight + 
                       self.config.tablet_weight)
        
        if total_weight == 0:
            return self._get_default_user_agent()
        
        # Random selection based on weights
        random_value = random.uniform(0, total_weight)
        
        if random_value <= self.config.desktop_weight:
            return random.choice(self.config.desktop_agents)
        elif random_value <= self.config.desktop_weight + self.config.mobile_weight:
            return random.choice(self.config.mobile_agents)
        else:
            return random.choice(self.config.tablet_agents)
    
    def _get_default_user_agent(self) -> str:
        """Get default user agent"""
        return ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    def _get_default_desktop_agents(self) -> List[str]:
        """Get default desktop user agents"""
        return [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        ]
    
    def _get_default_mobile_agents(self) -> List[str]:
        """Get default mobile user agents"""
        return [
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Android 11; Mobile; rv:89.0) Gecko/89.0 Firefox/89.0",
            "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36"
        ]

class RetryManager:
    """Manages request retry logic"""
    
    def __init__(self, default_policy: RetryPolicy):
        self.default_policy = default_policy
    
    async def execute_with_retry(self, request_func, *args, retry_policy: Optional[RetryPolicy] = None, **kwargs) -> Any:
        """Execute a function with retry logic"""
        policy = retry_policy or self.default_policy
        last_exception = None
        
        for attempt in range(policy.max_retries + 1):
            try:
                result = await request_func(*args, **kwargs)
                return result
                
            except Exception as e:
                last_exception = e
                
                # Check if we should retry this exception
                if not self._should_retry_exception(e, policy):
                    raise e
                
                # Don't retry if this is the last attempt
                if attempt >= policy.max_retries:
                    break
                
                # Calculate delay
                delay = self._calculate_delay(attempt, policy)
                logger.debug(f"Request failed (attempt {attempt + 1}/{policy.max_retries + 1}), retrying in {delay:.2f}s: {e}")
                
                await asyncio.sleep(delay)
        
        # All retries exhausted
        if last_exception:
            raise last_exception
    
    def _should_retry_exception(self, exception: Exception, policy: RetryPolicy) -> bool:
        """Check if an exception should trigger a retry"""
        exception_type = type(exception).__name__
        
        # Check against retry exception list
        return exception_type in policy.retry_on_exceptions
    
    def _should_retry_status_code(self, status_code: int, policy: RetryPolicy) -> bool:
        """Check if a status code should trigger a retry"""
        return status_code in policy.retry_on_status_codes
    
    def _calculate_delay(self, attempt: int, policy: RetryPolicy) -> float:
        """Calculate retry delay"""
        if policy.exponential_backoff:
            delay = policy.initial_delay * (2 ** attempt)
        else:
            delay = policy.initial_delay
        
        # Apply maximum delay cap
        delay = min(delay, policy.max_delay)
        
        # Add jitter if enabled
        if policy.jitter:
            jitter_amount = delay * policy.jitter_factor * random.uniform(-1, 1)
            delay += jitter_amount
        
        return max(0, delay)

class SessionManager:
    """Manages HTTP sessions for web scraping"""
    
    def __init__(self, config: ScrapingConfig):
        self.config = config
        self.sessions: Dict[str, aiohttp.ClientSession] = {}
        self.session_configs: Dict[str, ScrapingSession] = {}
        self.session_metrics: Dict[str, ScrapingMetrics] = {}
    
    async def get_session(self, session_config: Optional[ScrapingSession] = None) -> aiohttp.ClientSession:
        """Get or create a session"""
        if session_config is None:
            # Create a default session
            session_id = str(uuid.uuid4())
            session_config = ScrapingSession(
                session_id=session_id,
                connect_timeout=10.0,
                read_timeout=30.0,
                total_timeout=60.0
            )
        
        session_id = session_config.session_id
        
        # Check if session already exists
        if session_id in self.sessions:
            session = self.sessions[session_id]
            if not session.closed:
                return session
            else:
                # Session is closed, remove it
                del self.sessions[session_id]
        
        # Create new session
        timeout = aiohttp.ClientTimeout(
            connect=session_config.connect_timeout,
            sock_read=session_config.read_timeout,
            total=session_config.total_timeout
        )
        
        connector = aiohttp.TCPConnector(
            limit=session_config.max_connections,
            limit_per_host=session_config.max_connections_per_host,
            keepalive_timeout=30 if session_config.connection_keep_alive else 0,
            enable_cleanup_closed=True
        )
        
        session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector
        )
        
        self.sessions[session_id] = session
        self.session_configs[session_id] = session_config
        
        # Initialize metrics
        if session_id not in self.session_metrics:
            self.session_metrics[session_id] = ScrapingMetrics(session_id=session_id)
        
        return session
    
    async def close_session(self, session_id: str):
        """Close a specific session"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            if not session.closed:
                await session.close()
            del self.sessions[session_id]
        
        if session_id in self.session_configs:
            del self.session_configs[session_id]
    
    async def close_all_sessions(self):
        """Close all sessions"""
        for session in self.sessions.values():
            if not session.closed:
                await session.close()
        
        self.sessions.clear()
        self.session_configs.clear()
    
    def update_session_metrics(self, session_id: str, success: bool, response_time: float, status_code: Optional[int] = None):
        """Update metrics for a session"""
        if session_id not in self.session_metrics:
            return
        
        metrics = self.session_metrics[session_id]
        
        metrics.total_requests += 1
        
        if success:
            metrics.successful_requests += 1
        else:
            metrics.failed_requests += 1
        
        # Update response time metrics
        if metrics.total_requests == 1:
            metrics.min_response_time = response_time
            metrics.max_response_time = response_time
            metrics.average_response_time = response_time
        else:
            metrics.min_response_time = min(metrics.min_response_time, response_time)
            metrics.max_response_time = max(metrics.max_response_time, response_time)
            
            # Update average (exponential moving average)
            alpha = 0.1
            metrics.average_response_time = (alpha * response_time + 
                                           (1 - alpha) * metrics.average_response_time)
        
        # Update status code distribution
        if status_code:
            if status_code not in metrics.status_code_distribution:
                metrics.status_code_distribution[status_code] = 0
            metrics.status_code_distribution[status_code] += 1
        
        # Calculate derived metrics
        if metrics.total_requests > 0:
            metrics.success_rate = (metrics.successful_requests / metrics.total_requests) * 100
            
            if metrics.failed_requests > 0:
                metrics.retry_rate = (metrics.retried_requests / metrics.failed_requests) * 100
    
    def get_session_metrics(self, session_id: str) -> Optional[ScrapingMetrics]:
        """Get metrics for a session"""
        return self.session_metrics.get(session_id)

class ScrapingUtilsService:
    """Main scraping utilities service"""
    
    def __init__(self, config: ScrapingConfig):
        self.config = config
        self.rate_limiter = RateLimiter(config.default_rate_limit)
        self.proxy_manager = ProxyManager(config.proxy_configs, config.proxy_rotation) if config.proxy_configs else None
        self.user_agent_manager = UserAgentManager(config.user_agent_rotation)
        self.retry_manager = RetryManager(config.default_retry_policy)
        self.session_manager = SessionManager(config)
        
        # Request cache
        self.response_cache: Dict[str, Dict[str, Any]] = {}
        
        # Statistics
        self.global_stats = RequestStats()
    
    async def make_request(self, request: ScrapingRequest) -> ScrapingResponse:
        """Make a web scraping request with all utilities applied"""
        request_id = request.request_id or str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)
        
        try:
            # Check cache first
            if self.config.enable_caching:
                cached_response = self._get_cached_response(request)
                if cached_response:
                    return self._create_response_from_cache(request_id, request, cached_response)
            
            # Apply rate limiting
            if request.respect_rate_limits:
                delay = await self.rate_limiter.acquire(str(request.url))
                if delay > 0:
                    logger.debug(f"Rate limited request to {request.url}, delayed {delay:.2f}s")
            
            # Get session
            session_config = None
            if request.session_id:
                session_config = self.session_manager.session_configs.get(request.session_id)
            
            session = await self.session_manager.get_session(session_config)
            
            # Execute request with retry logic
            response_data = await self.retry_manager.execute_with_retry(
                self._execute_request,
                session,
                request,
                retry_policy=request.retry_policy
            )
            
            # Create successful response
            completed_at = datetime.now(timezone.utc)
            duration = (completed_at - start_time).total_seconds()
            
            response = ScrapingResponse(
                request_id=request_id,
                success=True,
                response_data=response_data,
                original_url=request.url,
                final_url=response_data.final_url or request.url,
                method=request.method,
                proxy_used=response_data.proxy_used,
                user_agent_used=response_data.user_agent_used,
                session_id=request.session_id,
                started_at=start_time,
                completed_at=completed_at,
                duration=duration,
                metadata=request.metadata
            )
            
            # Cache response if enabled
            if self.config.enable_caching:
                self._cache_response(request, response_data)
            
            # Update statistics
            self._update_stats(True, duration, response_data.status_code)
            
            return response
            
        except Exception as e:
            completed_at = datetime.now(timezone.utc)
            duration = (completed_at - start_time).total_seconds()
            
            # Create error response
            error = ScrapingError(
                error_type=type(e).__name__,
                error_message=str(e),
                url=request.url,
                method=request.method,
                occurred_at=completed_at
            )
            
            response = ScrapingResponse(
                request_id=request_id,
                success=False,
                error=error,
                original_url=request.url,
                method=request.method,
                session_id=request.session_id,
                started_at=start_time,
                completed_at=completed_at,
                duration=duration,
                metadata=request.metadata
            )
            
            # Update statistics
            self._update_stats(False, duration)
            
            logger.error(f"Request failed for {request.url}: {e}")
            return response
    
    async def _execute_request(self, session: aiohttp.ClientSession, request: ScrapingRequest) -> ResponseData:
        """Execute the actual HTTP request"""
        # Prepare headers
        headers = self._prepare_headers(request)
        
        # Get proxy
        proxy = None
        proxy_used = None
        if request.use_proxy and self.proxy_manager:
            proxy_config = self.proxy_manager.get_next_proxy()
            if proxy_config:
                proxy = proxy_config.proxy_url
                proxy_used = proxy_config.proxy_id
        
        # Prepare request parameters
        request_kwargs = {
            'method': request.method.value,
            'url': str(request.url),
            'headers': headers,
            'proxy': proxy
        }
        
        if request.params:
            request_kwargs['params'] = request.params
        
        if request.data:
            request_kwargs['data'] = request.data
        
        if request.json_data:
            request_kwargs['json'] = request.json_data
        
        # Make request
        start_time = time.time()
        
        try:
            async with session.request(**request_kwargs) as response:
                response_time = time.time() - start_time
                
                # Read content if requested
                content = None
                text = None
                
                if request.return_content:
                    content = await response.read()
                    if content:
                        text = content.decode(response.charset or 'utf-8', errors='ignore')
                
                # Get headers if requested
                response_headers = dict(response.headers) if request.return_headers else {}
                
                # Create response data
                response_data = ResponseData(
                    status_code=response.status,
                    headers=response_headers,
                    content=content,
                    text=text,
                    encoding=response.charset,
                    response_time=response_time,
                    content_length=len(content) if content else 0,
                    content_type=response.headers.get('content-type'),
                    proxy_used=proxy_used,
                    user_agent_used=headers.get('User-Agent')
                )
                
                # Update proxy statistics
                if proxy_used and self.proxy_manager:
                    success = 200 <= response.status < 400
                    self.proxy_manager.record_proxy_usage(proxy_used, success, response_time)
                
                # Update session metrics
                if request.session_id:
                    success = 200 <= response.status < 400
                    self.session_manager.update_session_metrics(
                        request.session_id, success, response_time, response.status
                    )
                
                return response_data
                
        except Exception as e:
            response_time = time.time() - start_time
            
            # Update proxy statistics for failure
            if proxy_used and self.proxy_manager:
                self.proxy_manager.record_proxy_usage(proxy_used, False, response_time)
            
            # Update session metrics for failure
            if request.session_id:
                self.session_manager.update_session_metrics(
                    request.session_id, False, response_time
                )
            
            raise e
    
    def _prepare_headers(self, request: ScrapingRequest) -> Dict[str, str]:
        """Prepare headers for the request"""
        headers = {}
        
        # Start with default headers
        default_headers = self.config.default_headers
        headers.update({
            'Accept': default_headers.accept,
            'Accept-Language': default_headers.accept_language,
            'Accept-Encoding': default_headers.accept_encoding,
            'DNT': default_headers.dnt,
            'Upgrade-Insecure-Requests': default_headers.upgrade_insecure_requests
        })
        
        # Add security headers if configured
        if default_headers.sec_fetch_dest:
            headers['Sec-Fetch-Dest'] = default_headers.sec_fetch_dest
        if default_headers.sec_fetch_mode:
            headers['Sec-Fetch-Mode'] = default_headers.sec_fetch_mode
        if default_headers.sec_fetch_site:
            headers['Sec-Fetch-Site'] = default_headers.sec_fetch_site
        
        # Add request-specific headers
        if request.headers:
            headers.update(request.headers.headers)
        
        # Set user agent
        if request.rotate_user_agent:
            headers['User-Agent'] = self.user_agent_manager.get_user_agent()
        elif request.preferred_user_agent:
            headers['User-Agent'] = request.preferred_user_agent
        
        return headers
    
    def _get_cache_key(self, request: ScrapingRequest) -> str:
        """Generate cache key for request"""
        key_data = {
            'url': str(request.url),
            'method': request.method.value,
            'params': request.params,
            'data': request.data,
            'json_data': request.json_data
        }
        
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _get_cached_response(self, request: ScrapingRequest) -> Optional[Dict[str, Any]]:
        """Get cached response if available and valid"""
        cache_key = self._get_cache_key(request)
        
        if cache_key in self.response_cache:
            cached_data = self.response_cache[cache_key]
            
            # Check if cache is still valid
            cache_time = cached_data.get('timestamp', 0)
            current_time = time.time()
            
            if current_time - cache_time < self.config.cache_ttl_seconds:
                return cached_data
            else:
                # Cache expired, remove it
                del self.response_cache[cache_key]
        
        return None
    
    def _cache_response(self, request: ScrapingRequest, response_data: ResponseData):
        """Cache response data"""
        cache_key = self._get_cache_key(request)
        
        cached_data = {
            'timestamp': time.time(),
            'response_data': response_data.dict()
        }
        
        self.response_cache[cache_key] = cached_data
        
        # Simple cache size management
        if len(self.response_cache) > 10000:  # Arbitrary limit
            # Remove oldest entries
            sorted_cache = sorted(self.response_cache.items(), 
                                key=lambda x: x[1]['timestamp'])
            
            # Remove oldest 10%
            remove_count = len(sorted_cache) // 10
            for i in range(remove_count):
                del self.response_cache[sorted_cache[i][0]]
    
    def _create_response_from_cache(self, request_id: str, request: ScrapingRequest, 
                                  cached_data: Dict[str, Any]) -> ScrapingResponse:
        """Create response from cached data"""
        response_data = ResponseData(**cached_data['response_data'])
        
        return ScrapingResponse(
            request_id=request_id,
            success=True,
            response_data=response_data,
            original_url=request.url,
            final_url=response_data.final_url or request.url,
            method=request.method,
            proxy_used=response_data.proxy_used,
            user_agent_used=response_data.user_agent_used,
            session_id=request.session_id,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            duration=0.0,
            retry_attempts=0,
            from_cache=True,
            cache_key=self._get_cache_key(request),
            metadata=request.metadata
        )
    
    def _update_stats(self, success: bool, duration: float, status_code: Optional[int] = None):
        """Update global statistics"""
        self.global_stats.total_attempts += 1
        self.global_stats.total_response_time += duration
        self.global_stats.last_attempt_time = datetime.now(timezone.utc)
        
        if success:
            self.global_stats.successful_attempts += 1
        else:
            self.global_stats.failed_attempts += 1
    
    def get_stats(self) -> RequestStats:
        """Get global statistics"""
        return self.global_stats
    
    async def cleanup(self):
        """Clean up resources"""
        await self.session_manager.close_all_sessions()
        self.response_cache.clear()

# Service factory function
async def get_scraping_utils_service(config: ScrapingConfig) -> ScrapingUtilsService:
    """Factory function to create scraping utils service instance"""
    return ScrapingUtilsService(config)