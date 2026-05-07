"""Re-export shim — OAuthTokenManager now lives in service_core.oauth.
This file will be deleted after all consumers are migrated (Phase 4e).
"""
from service_core.oauth import OAuthTokenManager

__all__ = ["OAuthTokenManager"]
