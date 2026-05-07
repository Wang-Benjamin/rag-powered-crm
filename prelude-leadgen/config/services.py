"""Centralized configuration for all external services and APIs."""

import os
from typing import Optional


class ExternalServices:
    """Configuration for external service URLs and parameters."""

    # ===== Internal Prelude Services =====
    USER_SETTINGS_URL: str = os.getenv("USER_SETTINGS_URL", "http://localhost:8005")
    CRM_SERVICE_URL: str = os.getenv("CRM_SERVICE_URL", "http://localhost:8003")
    CHAT_SERVICE_URL: str = os.getenv("CHAT_SERVICE_URL", "http://localhost:8001")

    # ===== External API URLs =====
    APOLLO_BASE_URL: str = os.getenv("APOLLO_BASE_URL", "https://api.apollo.io")
    GOOGLE_MAPS_API_URL: str = "https://maps.googleapis.com/maps/api"
    FIRECRAWL_API_URL: str = os.getenv("FIRECRAWL_API_URL", "https://api.firecrawl.dev")
    PERPLEXITY_API_URL: str = os.getenv("PERPLEXITY_API_URL", "https://api.perplexity.ai")

    # ===== API Timeouts (seconds) =====
    APOLLO_TIMEOUT: int = int(os.getenv("APOLLO_TIMEOUT", "30"))
    GOOGLE_MAPS_TIMEOUT: int = int(os.getenv("GOOGLE_MAPS_TIMEOUT", "10"))
    FIRECRAWL_TIMEOUT: int = int(os.getenv("FIRECRAWL_TIMEOUT", "30"))
    DEFAULT_API_TIMEOUT: int = int(os.getenv("DEFAULT_API_TIMEOUT", "30"))

    # ===== Email Configuration =====
    MASS_EMAIL_MIN_DELAY: int = int(os.getenv("MASS_EMAIL_MIN_DELAY", "10"))
    MASS_EMAIL_MAX_DELAY: int = int(os.getenv("MASS_EMAIL_MAX_DELAY", "30"))
    MAX_CONCURRENT_EMAIL_GENERATIONS: int = int(os.getenv("MAX_CONCURRENT_EMAIL_GENERATIONS", "50"))

    # ===== Apollo API Configuration =====
    APOLLO_API_KEY: Optional[str] = os.getenv("APOLLO_API_KEY")
    APOLLO_RATE_LIMIT: int = int(os.getenv("APOLLO_RATE_LIMIT", "60"))  # requests per minute
    APOLLO_MAX_RETRIES: int = int(os.getenv("APOLLO_MAX_RETRIES", "1"))
    APOLLO_MIN_SCORE: int = int(os.getenv("APOLLO_MIN_SCORE", "30"))
    APOLLO_REQUIRE_EMAIL: bool = os.getenv("APOLLO_REQUIRE_EMAIL", "true").lower() == "true"
    APOLLO_REQUIRE_WEBSITE: bool = os.getenv("APOLLO_REQUIRE_WEBSITE", "false").lower() == "true"

    # ===== ImportYeti Configuration =====
    IMPORTYETI_API_KEY: Optional[str] = os.getenv("IMPORTYETI_API_KEY")
    IMPORTYETI_TIMEOUT: int = int(os.getenv("IMPORTYETI_TIMEOUT", "30"))
    IMPORTYETI_RATE_LIMIT: int = int(os.getenv("IMPORTYETI_RATE_LIMIT", "30"))  # requests per minute

    # ===== Google Maps Configuration =====
    GOOGLE_MAPS_API_KEY: Optional[str] = os.getenv("GOOGLE_MAPS_API_KEY")
    MARKET_DENSITY_RADIUS_KM: float = float(os.getenv("MARKET_DENSITY_RADIUS_KM", "10.0"))

    # ===== Lead Scoring Configuration =====
    TOKENS_LIMIT: int = int(os.getenv("TOKENS_LIMIT", "300"))

    # ===== Workflow Configuration =====
    DEFAULT_MAX_SEARCH_RESULTS: int = int(os.getenv("DEFAULT_MAX_SEARCH_RESULTS", "50"))
    WORKFLOW_TIMEOUT: int = int(os.getenv("WORKFLOW_TIMEOUT", "300"))  # 5 minutes

    @classmethod
    def get_service_url(cls, service: str) -> str:
        """
        Get URL for internal service.

        Args:
            service: Service name (user_settings, crm, chat)

        Returns:
            Service URL
        """
        service_map = {
            "user_settings": cls.USER_SETTINGS_URL,
            "crm": cls.CRM_SERVICE_URL,
            "chat": cls.CHAT_SERVICE_URL,
        }
        return service_map.get(service.lower(), "")

    @classmethod
    def get_api_config(cls, api: str) -> dict:
        """
        Get configuration for external API.

        Args:
            api: API name (apollo, google_maps, firecrawl)

        Returns:
            Dict with API configuration
        """
        if api.lower() == "apollo":
            return {
                "base_url": cls.APOLLO_BASE_URL,
                "api_key": cls.APOLLO_API_KEY,
                "timeout": cls.APOLLO_TIMEOUT,
                "rate_limit": cls.APOLLO_RATE_LIMIT,
                "max_retries": cls.APOLLO_MAX_RETRIES,
                "min_score": cls.APOLLO_MIN_SCORE,
                "require_email": cls.APOLLO_REQUIRE_EMAIL,
                "require_website": cls.APOLLO_REQUIRE_WEBSITE
            }
        elif api.lower() == "importyeti":
            return {
                "base_url": "https://data.importyeti.com/v1.0",
                "api_key": cls.IMPORTYETI_API_KEY,
                "timeout": cls.IMPORTYETI_TIMEOUT,
                "rate_limit": cls.IMPORTYETI_RATE_LIMIT,
            }
        elif api.lower() == "google_maps":
            return {
                "base_url": cls.GOOGLE_MAPS_API_URL,
                "api_key": cls.GOOGLE_MAPS_API_KEY,
                "timeout": cls.GOOGLE_MAPS_TIMEOUT,
                "density_radius_km": cls.MARKET_DENSITY_RADIUS_KM
            }
        elif api.lower() == "firecrawl":
            return {
                "base_url": cls.FIRECRAWL_API_URL,
                "timeout": cls.FIRECRAWL_TIMEOUT
            }
        else:
            return {
                "timeout": cls.DEFAULT_API_TIMEOUT
            }

    @classmethod
    def validate_required_keys(cls) -> list:
        """
        Validate that required API keys are present.

        Returns:
            List of missing required keys
        """
        missing = []

        if not cls.APOLLO_API_KEY:
            missing.append("APOLLO_API_KEY")

        # Google Maps is optional for some features
        # if not cls.GOOGLE_MAPS_API_KEY:
        #     missing.append("GOOGLE_MAPS_API_KEY")

        return missing


def get_user_repositories(user_email: str = None, auth_token: str = None):
    """Get repository instances.

    Shared across lead-related routers.
    Uses lazy imports to avoid circular dependencies.

    Repos are now stateless — conn is passed to each method call.
    user_email/auth_token kept for services that need them (export).
    """
    from data.repositories import LeadRepository, PersonnelRepository
    from export.services import get_export_service

    return {
        'lead_repo': LeadRepository(),
        'personnel_repo': PersonnelRepository(),
        'export': get_export_service(user_email)
    }


# Global instance
services = ExternalServices()
