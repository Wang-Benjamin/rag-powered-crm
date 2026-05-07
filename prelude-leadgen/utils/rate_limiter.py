"""Token bucket rate limiter for API calls."""

import asyncio
import time
import logging
from typing import Optional
from asyncio_throttle import Throttler

logger = logging.getLogger(__name__)


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter for controlling API request rates.

    Features:
    - Smooth rate limiting (not hard blocking)
    - Burst handling (allows short bursts within limits)
    - Automatic token refill
    - Async/await support
    """

    def __init__(
        self,
        rate_limit: int,
        time_period: int = 60,
        burst_size: Optional[int] = None
    ):
        """
        Initialize rate limiter.

        Args:
            rate_limit: Maximum requests allowed per time period
            time_period: Time period in seconds (default: 60)
            burst_size: Maximum burst size (default: rate_limit)
        """
        self.rate_limit = rate_limit
        self.time_period = time_period
        self.burst_size = burst_size or rate_limit

        # Token bucket state
        self.tokens = float(self.burst_size)
        self.last_refill = time.time()
        self.lock = asyncio.Lock()

        # Use asyncio-throttle for smooth rate limiting
        self.throttler = Throttler(rate_limit=rate_limit, period=time_period)

        logger.info(
            f"Rate limiter initialized: {rate_limit} requests per {time_period}s "
            f"(burst: {self.burst_size})"
        )

    def _refill_tokens(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill

        # Calculate tokens to add based on elapsed time
        tokens_to_add = (elapsed / self.time_period) * self.rate_limit

        self.tokens = min(self.burst_size, self.tokens + tokens_to_add)
        self.last_refill = now

    async def acquire(self, tokens: int = 1) -> bool:
        """
        Acquire tokens from bucket (async).

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if tokens acquired, False otherwise
        """
        async with self.lock:
            self._refill_tokens()

            if self.tokens >= tokens:
                self.tokens -= tokens
                logger.debug(f"Rate limiter: acquired {tokens} tokens ({self.tokens:.2f} remaining)")
                return True
            else:
                logger.debug(f"Rate limiter: insufficient tokens (need {tokens}, have {self.tokens:.2f})")
                return False

    async def wait_for_token(self, tokens: int = 1):
        """
        Wait until tokens are available (async).

        Args:
            tokens: Number of tokens to acquire
        """
        while not await self.acquire(tokens):
            # Calculate wait time until next token
            wait_time = (tokens - self.tokens) * (self.time_period / self.rate_limit)
            wait_time = max(0.1, min(wait_time, 1.0))  # Wait between 0.1s and 1s

            logger.debug(f"Rate limiter: waiting {wait_time:.2f}s for tokens")
            await asyncio.sleep(wait_time)

    async def execute_with_limit(self, func, *args, **kwargs):
        """
        Execute async function with rate limiting.

        Args:
            func: Async function to execute
            *args, **kwargs: Function arguments

        Returns:
            Function result
        """
        await self.wait_for_token()
        return await func(*args, **kwargs)

    async def execute_with_throttle(self, func, *args, **kwargs):
        """
        Execute async function using throttler (smoother rate limiting).

        Args:
            func: Async function to execute
            *args, **kwargs: Function arguments

        Returns:
            Function result
        """
        async with self.throttler:
            return await func(*args, **kwargs)

    def get_status(self) -> dict:
        """Get current rate limiter status."""
        self._refill_tokens()
        return {
            "rate_limit": self.rate_limit,
            "time_period": self.time_period,
            "burst_size": self.burst_size,
            "available_tokens": round(self.tokens, 2),
            "utilization_percent": round((1 - self.tokens / self.burst_size) * 100, 2)
        }


class ExponentialBackoff:
    """
    Exponential backoff for retry logic.

    Usage:
        backoff = ExponentialBackoff(base_delay=1, max_delay=60)
        for attempt in range(max_retries):
            try:
                result = await api_call()
                break
            except APIError:
                await backoff.sleep(attempt)
    """

    def __init__(
        self,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        """
        Initialize exponential backoff.

        Args:
            base_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            exponential_base: Base for exponential growth (default: 2)
            jitter: Add random jitter to prevent thundering herd
        """
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """
        Calculate delay for given attempt number.

        Args:
            attempt: Attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        delay = min(self.base_delay * (self.exponential_base ** attempt), self.max_delay)

        if self.jitter:
            import random
            # Add jitter: random value between 0 and delay
            delay = random.uniform(0, delay)

        return delay

    async def sleep(self, attempt: int):
        """
        Sleep with exponential backoff.

        Args:
            attempt: Attempt number (0-indexed)
        """
        delay = self.get_delay(attempt)
        logger.debug(f"Exponential backoff: sleeping {delay:.2f}s (attempt {attempt + 1})")
        await asyncio.sleep(delay)


# Global rate limiters for external services
_rate_limiters: dict[str, TokenBucketRateLimiter] = {}


def get_rate_limiter(name: str, rate_limit: int, time_period: int = 60) -> TokenBucketRateLimiter:
    """Get or create a rate limiter instance."""
    if name not in _rate_limiters:
        _rate_limiters[name] = TokenBucketRateLimiter(rate_limit, time_period)
    return _rate_limiters[name]


# Pre-configured rate limiters
apollo_rate_limiter = get_rate_limiter("apollo_api", rate_limit=60, time_period=60)
lemlist_rate_limiter = get_rate_limiter("lemlist_api", rate_limit=20, time_period=2)
google_maps_rate_limiter = get_rate_limiter("google_maps_api", rate_limit=100, time_period=60)
