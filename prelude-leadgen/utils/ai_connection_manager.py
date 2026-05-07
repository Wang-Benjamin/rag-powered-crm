"""
AI Connection Manager for the lead generation service.

This module manages connections to various AI services including
Perplexity, OpenAI, and other AI providers with connection pooling,
rate limiting, and error handling.
"""

import os
import asyncio
import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timezone, timedelta
from abc import ABC, abstractmethod
import aiohttp
from aiohttp import ClientTimeout, ClientSession

from .exceptions import AIServiceError, RateLimitError, ConfigurationError, OperationTimeoutError
from config.settings import Config, config

logger = logging.getLogger(__name__)


class AIProvider(ABC):
    """Abstract base class for AI service providers."""
    
    @abstractmethod
    async def make_request(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Make a request to the AI service."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the AI service is healthy."""
        pass


class PerplexityProvider(AIProvider):
    """Perplexity AI service provider."""
    
    def __init__(self, api_key: str, model: str = "sonar-pro"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.perplexity.ai"
        self.timeout = ClientTimeout(total=45, connect=10)
        
        # Rate limiting
        self._last_request_time = 0
        self._min_request_interval = 1.2  # seconds between requests
        self._request_count = 0
        self._rate_limit_window_start = datetime.now(timezone.utc)
        self._requests_per_minute = 60
    
    async def _rate_limit(self) -> None:
        """Implement rate limiting."""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self._last_request_time
        
        if time_since_last < self._min_request_interval:
            await asyncio.sleep(self._min_request_interval - time_since_last)
        
        # Check requests per minute limit
        now = datetime.now(timezone.utc)
        if (now - self._rate_limit_window_start).total_seconds() > 60:
            self._request_count = 0
            self._rate_limit_window_start = now
        
        if self._request_count >= self._requests_per_minute:
            sleep_time = 60 - (now - self._rate_limit_window_start).total_seconds()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
                self._request_count = 0
                self._rate_limit_window_start = datetime.now(timezone.utc)
        
        self._last_request_time = asyncio.get_event_loop().time()
        self._request_count += 1
    
    async def make_request(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Make a request to Perplexity API."""
        await self._rate_limit()
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            **kwargs
        }
        
        async with ClientSession(timeout=self.timeout) as session:
            try:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=data
                ) as response:
                    if response.status == 429:
                        retry_after = int(response.headers.get("Retry-After", 60))
                        raise RateLimitError(
                            f"Perplexity rate limit exceeded",
                            service="perplexity",
                            retry_after=retry_after
                        )
                    
                    if response.status != 200:
                        error_text = await response.text()
                        raise AIServiceError(
                            f"Perplexity API error: {error_text}",
                            provider="perplexity"
                        )
                    
                    return await response.json()
                    
            except asyncio.TimeoutError:
                raise OperationTimeoutError(
                    "Perplexity API request timed out",
                    operation="ai_request",
                    timeout_seconds=45
                )
    
    async def health_check(self) -> bool:
        """Check Perplexity API health."""
        try:
            await self.make_request("Health check", max_tokens=10)
            return True
        except Exception as e:
            logger.warning(f"Perplexity health check failed: {e}")
            return False


class OpenAIProvider(AIProvider):
    """OpenAI service provider."""
    
    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.openai.com/v1"
        self.timeout = ClientTimeout(total=30, connect=10)
    
    async def make_request(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Make a request to OpenAI API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": kwargs.get("max_tokens", 1000),
            **{k: v for k, v in kwargs.items() if k != "max_tokens"}
        }
        
        async with ClientSession(timeout=self.timeout) as session:
            try:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=data
                ) as response:
                    if response.status == 429:
                        retry_after = int(response.headers.get("Retry-After", 60))
                        raise RateLimitError(
                            f"OpenAI rate limit exceeded",
                            service="openai",
                            retry_after=retry_after
                        )
                    
                    if response.status != 200:
                        error_text = await response.text()
                        raise AIServiceError(
                            f"OpenAI API error: {error_text}",
                            provider="openai"
                        )
                    
                    return await response.json()
                    
            except asyncio.TimeoutError:
                raise OperationTimeoutError(
                    "OpenAI API request timed out",
                    operation="ai_request",
                    timeout_seconds=30
                )
    
    async def health_check(self) -> bool:
        """Check OpenAI API health."""
        try:
            await self.make_request("Health check", max_tokens=10)
            return True
        except Exception as e:
            logger.warning(f"OpenAI health check failed: {e}")
            return False


class AIConnectionManager:
    """
    Manages connections to multiple AI service providers.
    
    Provides connection pooling, failover, load balancing, and monitoring
    for AI service requests.
    """
    
    def __init__(self, app_config: Optional[Config] = None):
        self.config = app_config or config
        self.providers: Dict[str, AIProvider] = {}
        self.provider_health: Dict[str, bool] = {}
        self.provider_usage_stats: Dict[str, Dict[str, Any]] = {}
        
        # Initialize providers based on configuration
        self._initialize_providers()
    
    def _initialize_providers(self) -> None:
        """Initialize AI service providers based on configuration."""
        # Initialize Perplexity if API key is available
        if self.config.PERPLEXITY_API_KEY:
            try:
                self.providers["perplexity"] = PerplexityProvider(
                    api_key=self.config.PERPLEXITY_API_KEY,
                    model="sonar-pro"
                )
                self.provider_health["perplexity"] = True
                self.provider_usage_stats["perplexity"] = {
                    "requests": 0,
                    "errors": 0,
                    "last_used": None
                }
                logger.info("Initialized Perplexity provider")
            except Exception as e:
                logger.error(f"Failed to initialize Perplexity provider: {e}")
        
        # Initialize OpenAI if API key is available
        if self.config.OPENAI_API_KEY:
            try:
                self.providers["openai"] = OpenAIProvider(
                    api_key=self.config.OPENAI_API_KEY,
                    model="gpt-3.5-turbo"
                )
                self.provider_health["openai"] = True
                self.provider_usage_stats["openai"] = {
                    "requests": 0,
                    "errors": 0,
                    "last_used": None
                }
                logger.info("Initialized OpenAI provider")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI provider: {e}")
        
        if not self.providers:
            raise ConfigurationError("No AI providers configured. Please set API keys.")
    
    async def get_available_providers(self) -> List[str]:
        """Get list of available (healthy) providers."""
        available = []
        for name, provider in self.providers.items():
            if self.provider_health.get(name, False):
                available.append(name)
        return available
    
    async def select_provider(self, preferred_provider: Optional[str] = None) -> str:
        """
        Select the best available provider.
        
        Args:
            preferred_provider: Preferred provider name
            
        Returns:
            Selected provider name
            
        Raises:
            AIServiceError: If no providers are available
        """
        available_providers = await self.get_available_providers()
        
        if not available_providers:
            raise AIServiceError("No AI providers are currently available", provider="none")
        
        # Use preferred provider if available and healthy
        if preferred_provider and preferred_provider in available_providers:
            return preferred_provider
        
        # Select provider with least recent usage for load balancing
        best_provider = min(
            available_providers,
            key=lambda p: self.provider_usage_stats[p].get("last_used") or datetime.min.replace(tzinfo=timezone.utc)
        )
        
        return best_provider
    
    async def make_request(
        self, 
        prompt: str, 
        preferred_provider: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make an AI request with automatic provider selection and failover.
        
        Args:
            prompt: The prompt to send to the AI service
            preferred_provider: Preferred provider name
            **kwargs: Additional parameters for the AI request
            
        Returns:
            AI response
            
        Raises:
            AIServiceError: If the request fails
        """
        selected_provider = await self.select_provider(preferred_provider)
        provider = self.providers[selected_provider]
        
        try:
            # Update usage stats
            self.provider_usage_stats[selected_provider]["requests"] += 1
            self.provider_usage_stats[selected_provider]["last_used"] = datetime.now(timezone.utc)
            
            # Make the request
            response = await provider.make_request(prompt, **kwargs)
            
            logger.info(f"AI request successful using provider: {selected_provider}")
            return response
            
        except (RateLimitError, AIServiceError, OperationTimeoutError) as e:
            # Update error stats
            self.provider_usage_stats[selected_provider]["errors"] += 1
            
            # Mark provider as unhealthy if too many errors
            error_rate = (
                self.provider_usage_stats[selected_provider]["errors"] / 
                max(self.provider_usage_stats[selected_provider]["requests"], 1)
            )
            
            if error_rate > 0.5:  # More than 50% error rate
                self.provider_health[selected_provider] = False
                logger.warning(f"Marking provider {selected_provider} as unhealthy due to high error rate")
            
            # Try failover to another provider
            available_providers = await self.get_available_providers()
            if len(available_providers) > 1:
                # Remove the failed provider from options
                available_providers.remove(selected_provider)
                failover_provider = available_providers[0]
                
                logger.warning(f"Failing over from {selected_provider} to {failover_provider}")
                return await self.make_request(prompt, failover_provider, **kwargs)
            
            # No failover available, re-raise the exception
            raise e
    
    async def health_check_all_providers(self) -> Dict[str, bool]:
        """Run health checks on all providers."""
        results = {}
        
        for name, provider in self.providers.items():
            try:
                is_healthy = await provider.health_check()
                results[name] = is_healthy
                self.provider_health[name] = is_healthy
            except Exception as e:
                logger.error(f"Health check failed for provider {name}: {e}")
                results[name] = False
                self.provider_health[name] = False
        
        return results
    
    async def get_provider_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get usage statistics for all providers."""
        stats = {}
        
        for name in self.providers.keys():
            provider_stats = self.provider_usage_stats.get(name, {})
            stats[name] = {
                "healthy": self.provider_health.get(name, False),
                "requests": provider_stats.get("requests", 0),
                "errors": provider_stats.get("errors", 0),
                "error_rate": (
                    provider_stats.get("errors", 0) / max(provider_stats.get("requests", 1), 1)
                ),
                "last_used": provider_stats.get("last_used")
            }
        
        return stats
    
    async def reset_provider_health(self, provider_name: str) -> None:
        """Reset provider health status (mark as healthy)."""
        if provider_name in self.providers:
            self.provider_health[provider_name] = True
            logger.info(f"Reset health status for provider: {provider_name}")


# Global connection manager instance
_connection_manager: Optional[AIConnectionManager] = None


def get_ai_connection_manager() -> AIConnectionManager:
    """Get the global AI connection manager instance."""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = AIConnectionManager()
    return _connection_manager


async def initialize_ai_services() -> None:
    """Initialize AI services and run health checks."""
    manager = get_ai_connection_manager()
    health_results = await manager.health_check_all_providers()
    
    healthy_count = sum(1 for is_healthy in health_results.values() if is_healthy)
    total_count = len(health_results)
    
    logger.info(f"AI services initialized: {healthy_count}/{total_count} providers healthy")
    
    for provider, is_healthy in health_results.items():
        status = "healthy" if is_healthy else "unhealthy"
        logger.info(f"Provider {provider}: {status}")


async def make_ai_request(
    prompt: str,
    preferred_provider: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Convenience function to make AI requests.
    
    Args:
        prompt: The prompt to send to the AI service
        preferred_provider: Preferred provider name
        **kwargs: Additional parameters for the AI request
        
    Returns:
        AI response
    """
    manager = get_ai_connection_manager()
    return await manager.make_request(prompt, preferred_provider, **kwargs)