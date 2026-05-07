"""
OAuth Token Manager — shared across all services.

Handles storing, retrieving, and auto-refreshing OAuth tokens for Google and Microsoft.
Solves the 1-hour token expiration problem by using refresh tokens.

conn=None falls back to get_current_conn() (contextvars) for backward compatibility
with CRM calendar/sync code. Pass conn explicitly where available.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any

from service_core.db import get_current_conn

logger = logging.getLogger(__name__)


class OAuthTokenManager:
    """Manages OAuth tokens for Google and Microsoft with auto-refresh capability."""

    def __init__(self, auth_provider=None):
        self.auth_provider = auth_provider

    async def store_tokens(
        self,
        user_email: str,
        provider: str,
        access_token: str,
        refresh_token: str,
        expires_in: int,
        scope: str = None,
        employee_id: int = None,
        conn=None,
    ) -> bool:
        """Store or update OAuth tokens in database."""
        try:
            c = conn or get_current_conn()
            token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            await c.execute("""
            INSERT INTO oauth_tokens (
                user_email, provider, access_token, refresh_token,
                token_expiry, scope, employee_id
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (user_email, provider)
            DO UPDATE SET
                access_token = EXCLUDED.access_token,
                refresh_token = EXCLUDED.refresh_token,
                token_expiry = EXCLUDED.token_expiry,
                scope = EXCLUDED.scope,
                employee_id = EXCLUDED.employee_id,
                updated_at = CURRENT_TIMESTAMP
            """, user_email, provider, access_token, refresh_token,
                token_expiry, scope, employee_id)

            logger.info(f"Stored {provider} tokens for {user_email} (expires: {token_expiry})")
            return True
        except Exception as e:
            logger.error(f"Error storing OAuth tokens: {e}")
            return False

    async def get_valid_access_token(
        self,
        user_email: str,
        provider: str,
        conn=None,
    ) -> Optional[str]:
        """Get a valid access token, auto-refreshing if expired."""
        try:
            c = conn or get_current_conn()

            row = await c.fetchrow("""
            SELECT access_token, refresh_token, token_expiry, scope, employee_id
            FROM oauth_tokens
            WHERE user_email = $1 AND provider = $2
            """, user_email, provider)

            if not row:
                logger.warning(f"No {provider} tokens found for {user_email}")
                return None

            now = datetime.now(timezone.utc)
            token_expiry = row['token_expiry']
            if token_expiry.tzinfo is None:
                token_expiry = token_expiry.replace(tzinfo=timezone.utc)

            if now + timedelta(minutes=5) >= token_expiry:
                logger.info(f"Access token expired/expiring soon for {user_email}, refreshing...")
                return await self._refresh_access_token(
                    user_email, provider, row['refresh_token'], row['scope'], row['employee_id']
                )
            else:
                remaining = (token_expiry - now).total_seconds() / 60
                logger.info(f"Access token valid for {user_email} ({remaining:.1f} min remaining)")
                return row['access_token']

        except Exception as e:
            logger.error(f"Error getting valid access token: {e}")
            return None

    async def _refresh_access_token(
        self,
        user_email: str,
        provider: str,
        refresh_token: str,
        scope: str,
        employee_id: int,
    ) -> Optional[str]:
        """Refresh the access token using refresh token."""
        try:
            if not self.auth_provider:
                logger.error("Auth provider not configured, cannot refresh token")
                return None

            logger.info(f"Calling {provider} token refresh API...")
            token_response = await self.auth_provider.refresh_token(
                refresh_token=refresh_token,
                service_name=provider
            )

            new_access_token = token_response.get('access_token')
            new_refresh_token = token_response.get('refresh_token', refresh_token)
            expires_in = token_response.get('expires_in', 3600)

            if not new_access_token:
                logger.error(f"No access token in refresh response for {provider}")
                return None

            await self.store_tokens(
                user_email=user_email,
                provider=provider,
                access_token=new_access_token,
                refresh_token=new_refresh_token,
                expires_in=expires_in,
                scope=scope,
                employee_id=employee_id,
            )

            logger.info(f"Successfully refreshed {provider} token for {user_email}")
            return new_access_token

        except Exception as e:
            logger.error(f"Error refreshing {provider} token for {user_email}: {type(e).__name__}: {e}")
            return None

    async def delete_tokens(self, user_email: str, provider: str, conn=None) -> bool:
        """Delete stored tokens for a user and provider."""
        try:
            c = conn or get_current_conn()
            await c.execute("""
            DELETE FROM oauth_tokens
            WHERE user_email = $1 AND provider = $2
            """, user_email, provider)
            logger.info(f"Deleted {provider} tokens for {user_email}")
            return True
        except Exception as e:
            logger.error(f"Error deleting tokens: {e}")
            return False

    async def get_token_info(self, user_email: str, provider: str, conn=None) -> Optional[Dict[str, Any]]:
        """Get token information without refreshing."""
        try:
            c = conn or get_current_conn()
            row = await c.fetchrow("""
            SELECT id, user_email, provider, token_expiry, scope,
                   employee_id, created_at, updated_at
            FROM oauth_tokens
            WHERE user_email = $1 AND provider = $2
            """, user_email, provider)
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting token info: {e}")
            return None
