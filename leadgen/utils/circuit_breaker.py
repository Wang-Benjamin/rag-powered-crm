"""Circuit breaker implementation for external API protection."""

import logging
from typing import Callable, Optional, Any
from functools import wraps
from datetime import datetime, timedelta, timezone
import asyncio
from circuitbreaker import circuit as base_circuit
from config.settings import config

logger = logging.getLogger(__name__)


class APICircuitBreaker:
    """
    Circuit breaker for external API calls.

    Prevents cascading failures by:
    - Tracking failure rates
    - Opening circuit after threshold failures
    - Allowing periodic test requests
    - Auto-recovering when service is healthy
    """

    def __init__(
        self,
        name: str,
        fail_max: int = None,
        timeout_duration: int = None
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Circuit breaker identifier
            fail_max: Number of failures before opening circuit
            timeout_duration: Time to wait before retry (seconds)
        """
        self.name = name
        self.fail_max = fail_max or config.CIRCUIT_BREAKER_FAIL_THRESHOLD
        self.timeout_duration = timeout_duration or config.CIRCUIT_BREAKER_TIMEOUT

        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "closed"  # closed, open, half_open

        logger.info(
            f"Circuit breaker '{name}' initialized "
            f"(fail_max={self.fail_max}, timeout={self.timeout_duration}s)"
        )

    def _should_allow_request(self) -> bool:
        """Determine if request should be allowed based on circuit state."""
        if self.state == "closed":
            return True

        if self.state == "open":
            # Check if timeout has elapsed
            if self.last_failure_time:
                elapsed = (datetime.now(timezone.utc) - self.last_failure_time).total_seconds()
                if elapsed >= self.timeout_duration:
                    logger.info(f"Circuit breaker '{self.name}' entering half-open state")
                    self.state = "half_open"
                    return True
            return False

        if self.state == "half_open":
            # Allow one test request
            return True

        return False

    def _record_success(self):
        """Record successful API call."""
        if self.state == "half_open":
            logger.info(f"Circuit breaker '{self.name}' closed (service recovered)")
            self.state = "closed"
            self.failure_count = 0
            self.last_failure_time = None
        elif self.state == "closed":
            # Reset failure count on success
            self.failure_count = 0

    def _record_failure(self, error: Exception):
        """Record failed API call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)

        if self.state == "half_open":
            logger.warning(f"Circuit breaker '{self.name}' re-opened (test request failed)")
            self.state = "open"
        elif self.failure_count >= self.fail_max:
            logger.error(
                f"Circuit breaker '{self.name}' opened "
                f"({self.failure_count} failures, threshold={self.fail_max})"
            )
            self.state = "open"

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        if not self._should_allow_request():
            raise CircuitBreakerError(
                f"Circuit breaker '{self.name}' is open. "
                f"Service unavailable (will retry in {self.timeout_duration}s)"
            )

        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure(e)
            raise

    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """Execute async function with circuit breaker protection."""
        if not self._should_allow_request():
            raise CircuitBreakerError(
                f"Circuit breaker '{self.name}' is open. "
                f"Service unavailable (will retry in {self.timeout_duration}s)"
            )

        try:
            result = await func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure(e)
            raise

    def get_status(self) -> dict:
        """Get current circuit breaker status."""
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self.failure_count,
            "fail_threshold": self.fail_max,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "timeout_duration": self.timeout_duration
        }


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open."""
    pass


# Global circuit breakers for external services
_circuit_breakers: dict[str, APICircuitBreaker] = {}


def get_circuit_breaker(name: str, **kwargs) -> APICircuitBreaker:
    """Get or create a circuit breaker instance."""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = APICircuitBreaker(name, **kwargs)
    return _circuit_breakers[name]


def with_circuit_breaker(breaker_name: str, fail_max: int = None, timeout_duration: int = None):
    """
    Decorator to protect async functions with circuit breaker.

    Usage:
        @with_circuit_breaker("apollo_api", fail_max=5, timeout_duration=60)
        async def call_apollo_api():
            ...
    """
    def decorator(func: Callable) -> Callable:
        breaker = get_circuit_breaker(breaker_name, fail_max=fail_max, timeout_duration=timeout_duration)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await breaker.call_async(func, *args, **kwargs)

        return wrapper
    return decorator


def get_all_circuit_breaker_status() -> list[dict]:
    """Get status of all circuit breakers."""
    return [breaker.get_status() for breaker in _circuit_breakers.values()]


# Pre-configured circuit breakers for lead gen services
apollo_breaker = get_circuit_breaker("apollo_api", fail_max=5, timeout_duration=60)
lemlist_breaker = get_circuit_breaker("lemlist_api", fail_max=5, timeout_duration=60)
google_maps_breaker = get_circuit_breaker("google_maps_api", fail_max=5, timeout_duration=60)
firecrawl_breaker = get_circuit_breaker("firecrawl_api", fail_max=5, timeout_duration=60)
perplexity_breaker = get_circuit_breaker("perplexity_api", fail_max=5, timeout_duration=60)
