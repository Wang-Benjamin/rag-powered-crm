"""Configuration management for Lead Generation Service."""

import os
import sys
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration settings for the lead generation service."""

    # Authentication Configuration
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "default_client_id")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "default_client_secret")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRE_HOURS: int = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

    # Service Configuration
    SERVICE_HOST: str = os.getenv("SERVICE_HOST", "0.0.0.0")
    SERVICE_PORT: int = int(os.getenv("PORT", os.getenv("SERVICE_PORT", "9000")))

    # API Keys Configuration
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    GOOGLE_SEARCH_API_KEY: Optional[str] = os.getenv("GOOGLE_SEARCH_API_KEY")
    GOOGLE_CUSTOM_SEARCH_ENGINE_ID: Optional[str] = os.getenv("GOOGLE_CUSTOM_SEARCH_ENGINE_ID")
    GOOGLE_MAPS_API_KEY: Optional[str] = os.getenv("GOOGLE_MAPS_API_KEY")
    PERPLEXITY_API_KEY: Optional[str] = os.getenv("PERPLEXITY_API_KEY")

    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Database Connection Pool
    DB_POOL_MIN_CONN: int = int(os.getenv("DB_POOL_MIN_CONN", "2"))
    DB_POOL_MAX_CONN: int = int(os.getenv("DB_POOL_MAX_CONN", "10"))

    # LinkedIn Integration Configuration
    LINKEDIN_CLIENT_ID: Optional[str] = os.getenv("LINKEDIN_CLIENT_ID")
    LINKEDIN_CLIENT_SECRET: Optional[str] = os.getenv("LINKEDIN_CLIENT_SECRET")

    # Email Configuration (for email lead generation)
    SMTP_HOST: Optional[str] = os.getenv("SMTP_HOST")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: Optional[str] = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")
    EMAIL_FROM: Optional[str] = os.getenv("EMAIL_FROM")

    # Rate Limiting Configuration
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "100"))
    
    # Search Configuration
    MAX_SEARCH_RESULTS: int = int(os.getenv("MAX_SEARCH_RESULTS", "100"))
    SEARCH_TIMEOUT: int = int(os.getenv("SEARCH_TIMEOUT", "30"))

    # Market Density Configuration
    MARKET_DENSITY_RADIUS_KM: float = float(os.getenv("MARKET_DENSITY_RADIUS_KM", "10.0"))
    
    # Development Configuration
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    RELOAD: bool = os.getenv("RELOAD", "False").lower() == "true"

    # Playwright Configuration (for web scraping)
    PLAYWRIGHT_HEADLESS: bool = os.getenv("PLAYWRIGHT_HEADLESS", "True").lower() == "true"
    PLAYWRIGHT_TIMEOUT: int = int(os.getenv("PLAYWRIGHT_TIMEOUT", "30000"))

    # Redis Configuration (for caching and task queue)
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost") or "localhost"
    REDIS_PORT: int = int(os.getenv("REDIS_PORT") or "6379")
    REDIS_DB: int = int(os.getenv("REDIS_DB") or "0")
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD") or None
    REDIS_SSL: bool = (os.getenv("REDIS_SSL") or "False").lower() == "true"
    REDIS_CACHE_TTL: int = int(os.getenv("REDIS_CACHE_TTL") or "600")  # 10 minutes default

    # Circuit Breaker Configuration
    CIRCUIT_BREAKER_FAIL_THRESHOLD: int = int(os.getenv("CIRCUIT_BREAKER_FAIL_THRESHOLD", "5"))
    CIRCUIT_BREAKER_TIMEOUT: int = int(os.getenv("CIRCUIT_BREAKER_TIMEOUT", "60"))  # seconds

    # Apollo API Configuration
    APOLLO_CACHE_ENABLED: bool = os.getenv("APOLLO_CACHE_ENABLED", "True").lower() == "true"
    APOLLO_CACHE_TTL: int = int(os.getenv("APOLLO_CACHE_TTL", "900"))  # 15 minutes
    APOLLO_DEDUP_ENABLED: bool = os.getenv("APOLLO_DEDUP_ENABLED", "True").lower() == "true"

    @classmethod
    def validate_required_config(cls) -> None:
        """Validate that required configuration is present."""
        required_configs = []
        
        if not cls.GOOGLE_CLIENT_ID or cls.GOOGLE_CLIENT_ID == "default_client_id":
            required_configs.append("GOOGLE_CLIENT_ID")
        
        if not cls.GOOGLE_CLIENT_SECRET or cls.GOOGLE_CLIENT_SECRET == "default_client_secret":
            required_configs.append("GOOGLE_CLIENT_SECRET")
        
        if not cls.JWT_SECRET:
            required_configs.append("JWT_SECRET")
        
        if required_configs:
            raise ValueError(f"Missing required configuration: {', '.join(required_configs)}")

    @classmethod
    def is_development(cls) -> bool:
        """Check if running in development mode."""
        return cls.DEBUG or cls.RELOAD

    @classmethod
    def get_service_info(cls) -> dict:
        """Get service connection information."""
        return {
            "host": cls.SERVICE_HOST,
            "port": cls.SERVICE_PORT,
            "debug": cls.DEBUG,
            "reload": cls.RELOAD
        }

# Global config instance
config = Config()

# Validate configuration on import (only in production)
if not config.is_development():
    try:
        config.validate_required_config()
    except ValueError as e:
        import logging
        logging.warning(f"Configuration validation warning: {e}")