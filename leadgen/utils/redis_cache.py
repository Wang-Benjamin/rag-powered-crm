"""Redis caching utilities for lead generation service."""

import json
import hashlib
import logging
from typing import Optional, Any, Callable
from functools import wraps
import redis
from config.settings import config

logger = logging.getLogger(__name__)


class RedisCache:
    """Redis cache manager for Apollo API responses and request deduplication."""

    def __init__(self):
        """Initialize Redis connection."""
        self._client: Optional[redis.Redis] = None
        self._initialize_client()

    def _initialize_client(self):
        """Create Redis client connection."""
        try:
            redis_config = {
                'host': config.REDIS_HOST,
                'port': config.REDIS_PORT,
                'db': config.REDIS_DB,
                'decode_responses': True,
                'socket_connect_timeout': 5,
                'socket_timeout': 5,
            }

            if config.REDIS_PASSWORD:
                redis_config['password'] = config.REDIS_PASSWORD

            if config.REDIS_SSL:
                redis_config['ssl'] = True
                redis_config['ssl_cert_reqs'] = None

            self._client = redis.Redis(**redis_config)

            # Test connection - removed blocking ping during initialization
            # Connection will be tested lazily via is_available property
            # self._client.ping()
            logger.info(f"Redis client created: {config.REDIS_HOST}:{config.REDIS_PORT}")

        except redis.RedisError as e:
            logger.warning(f"Redis connection failed: {e}. Caching will be disabled.")
            self._client = None
        except Exception as e:
            logger.error(f"Unexpected error initializing Redis: {e}")
            self._client = None

    @property
    def is_available(self) -> bool:
        """Check if Redis is available."""
        if self._client is None:
            # Try to reconnect if client was never initialized
            logger.debug("Redis client is None, attempting to reconnect...")
            self._initialize_client()
            if self._client is None:
                return False
        try:
            self._client.ping()
            return True
        except redis.RedisError as e:
            logger.warning(f"Redis ping failed: {e}, attempting to reconnect...")
            # Try to reconnect on failure
            self._initialize_client()
            if self._client is not None:
                try:
                    self._client.ping()
                    logger.info("Redis reconnection successful")
                    return True
                except redis.RedisError:
                    pass
            return False

    def _generate_cache_key(self, prefix: str, **kwargs) -> str:
        """Generate a cache key from prefix and parameters."""
        # Sort kwargs for consistent key generation
        sorted_params = sorted(kwargs.items())
        param_str = json.dumps(sorted_params, sort_keys=True)
        hash_value = hashlib.md5(param_str.encode()).hexdigest()
        return f"{prefix}:{hash_value}"

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.is_available:
            return None

        try:
            value = self._client.get(key)
            if value:
                logger.debug(f"Cache HIT: {key}")
                return json.loads(value)
            logger.debug(f"Cache MISS: {key}")
            return None
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.warning(f"Cache get error for key {key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL."""
        if not self.is_available:
            return False

        try:
            ttl = ttl or config.REDIS_CACHE_TTL
            serialized_value = json.dumps(value)
            self._client.setex(key, ttl, serialized_value)
            logger.debug(f"Cache SET: {key} (TTL: {ttl}s)")
            return True
        except (redis.RedisError, TypeError) as e:
            logger.warning(f"Cache set error for key {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self.is_available:
            return False

        try:
            self._client.delete(key)
            logger.debug(f"Cache DELETE: {key}")
            return True
        except redis.RedisError as e:
            logger.warning(f"Cache delete error for key {key}: {e}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern."""
        if not self.is_available:
            return 0

        try:
            keys = self._client.keys(pattern)
            if keys:
                deleted = self._client.delete(*keys)
                logger.debug(f"Cache DELETE PATTERN: {pattern} ({deleted} keys)")
                return deleted
            return 0
        except redis.RedisError as e:
            logger.warning(f"Cache delete pattern error for {pattern}: {e}")
            return 0

    def acquire_lock(self, lock_key: str, timeout: int = 10) -> bool:
        """
        Acquire a distributed lock for request deduplication.

        Args:
            lock_key: Unique identifier for the lock
            timeout: Lock timeout in seconds

        Returns:
            True if lock acquired, False otherwise
        """
        logger.info(f"🔒 acquire_lock called: key={lock_key}, timeout={timeout}s")

        if not self.is_available:
            logger.warning(f"🔴 Redis NOT AVAILABLE - lock bypassed for {lock_key}")
            return True  # If Redis unavailable, allow request through

        try:
            # Use SET NX (set if not exists) with expiration
            full_key = f"lock:{lock_key}"

            # Check if lock already exists (for debugging)
            existing = self._client.get(full_key)
            if existing:
                logger.warning(f"🔒 Lock {full_key} already exists with value: {existing}")

            acquired = self._client.set(full_key, "1", nx=True, ex=timeout)
            logger.info(f"🔒 SET NX result for {full_key}: {acquired}")

            if acquired:
                logger.info(f"🔴 Lock ACQUIRED: {full_key}")
            else:
                logger.warning(f"🔴 Lock BLOCKED: {full_key} (already held)")
            return bool(acquired)
        except redis.RedisError as e:
            logger.warning(f"🔴 Lock acquire error for {lock_key}: {e}")
            return True  # On error, allow request through

    def release_lock(self, lock_key: str) -> bool:
        """Release a distributed lock."""
        if not self.is_available:
            return False

        try:
            self._client.delete(f"lock:{lock_key}")
            logger.debug(f"Lock RELEASED: {lock_key}")
            return True
        except redis.RedisError as e:
            logger.warning(f"Lock release error for {lock_key}: {e}")
            return False

    def cache_apollo_search(
        self,
        location: str,
        industry: str,
        max_results: int,
        **filters
    ) -> Optional[dict]:
        """Get cached Apollo search results."""
        if not config.APOLLO_CACHE_ENABLED:
            return None

        cache_key = self._generate_cache_key(
            "apollo:search",
            location=location,
            industry=industry,
            max_results=max_results,
            **filters
        )
        return self.get(cache_key)

    def store_apollo_search(
        self,
        location: str,
        industry: str,
        max_results: int,
        results: dict,
        **filters
    ) -> bool:
        """Store Apollo search results in cache."""
        if not config.APOLLO_CACHE_ENABLED:
            return False

        cache_key = self._generate_cache_key(
            "apollo:search",
            location=location,
            industry=industry,
            max_results=max_results,
            **filters
        )
        return self.set(cache_key, results, ttl=config.APOLLO_CACHE_TTL)

    def cache_apollo_enrichment(self, company_ids: list, **filters) -> Optional[dict]:
        """Get cached Apollo enrichment results."""
        if not config.APOLLO_CACHE_ENABLED:
            return None

        cache_key = self._generate_cache_key(
            "apollo:enrich",
            company_ids=sorted(company_ids),
            **filters
        )
        return self.get(cache_key)

    def store_apollo_enrichment(
        self,
        company_ids: list,
        results: dict,
        **filters
    ) -> bool:
        """Store Apollo enrichment results in cache."""
        if not config.APOLLO_CACHE_ENABLED:
            return False

        cache_key = self._generate_cache_key(
            "apollo:enrich",
            company_ids=sorted(company_ids),
            **filters
        )
        return self.set(cache_key, results, ttl=config.APOLLO_CACHE_TTL)


# Global cache instance
_cache_instance: Optional[RedisCache] = None


def get_cache() -> RedisCache:
    """Get or create global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RedisCache()
    return _cache_instance


def cached(ttl: Optional[int] = None, key_prefix: str = "cached"):
    """
    Decorator for caching function results.

    Usage:
        @cached(ttl=600, key_prefix="my_function")
        async def my_function(arg1, arg2):
            return expensive_operation(arg1, arg2)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_cache()

            # Generate cache key from function name and arguments
            cache_key = cache._generate_cache_key(
                f"{key_prefix}:{func.__name__}",
                args=args,
                kwargs=kwargs
            )

            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Returning cached result for {func.__name__}")
                return cached_result

            # Execute function
            result = await func(*args, **kwargs)

            # Store in cache
            cache.set(cache_key, result, ttl=ttl)

            return result
        return wrapper
    return decorator
