"""Cache service for CRM - handles in-memory caching"""

import logging
from datetime import datetime, timezone
from functools import wraps

logger = logging.getLogger(__name__)

# Simple in-memory cache for CRM data
_cache = {}
CACHE_TIMEOUT = 300  # 5 minutes in seconds


def cache_key(func_name: str, **kwargs) -> str:
    """Generate a cache key from function name and parameters"""
    # Sort kwargs to ensure consistent key generation
    sorted_kwargs = sorted(kwargs.items())
    key_parts = [func_name] + [f"{k}={v}" for k, v in sorted_kwargs]
    return ":".join(str(part) for part in key_parts)


def cached(timeout: int = CACHE_TIMEOUT):
    """Decorator to cache function results"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key = cache_key(func.__name__, **kwargs)

            # Check if we have cached data
            if key in _cache:
                cached_data, timestamp = _cache[key]
                if datetime.now(timezone.utc).timestamp() - timestamp < timeout:
                    logger.debug(f"Using cached CRM data for: {func.__name__}")
                    return cached_data
                else:
                    # Remove expired cache entry
                    del _cache[key]

            # Execute function and cache result
            logger.debug(f"Fetching fresh CRM data for: {func.__name__}")
            result = await func(*args, **kwargs)

            # Cache the result
            _cache[key] = (result, datetime.now(timezone.utc).timestamp())

            # Limit cache size to prevent memory issues
            if len(_cache) > 100:
                # Remove oldest entries
                oldest_key = min(_cache.keys(), key=lambda k: _cache[k][1])
                del _cache[oldest_key]

            return result
        return wrapper
    return decorator


def clear_cache(pattern: str = None):
    """Clear cache entries. If pattern is provided, only clear matching keys."""
    global _cache
    if pattern:
        keys_to_delete = [key for key in _cache.keys() if pattern in key]
        for key in keys_to_delete:
            del _cache[key]
        logger.debug(f"Cleared {len(keys_to_delete)} CRM cache entries matching '{pattern}'")
    else:
        _cache.clear()
        logger.debug("Cleared all CRM cache entries")
