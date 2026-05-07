"""
Authentication providers for Prelude Lead Generation Service
Includes JWT and OAuth providers extracted from backend_lead
"""

import os
import time
import jwt
import httpx
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any
from urllib.parse import urlencode
from fastapi import HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class SimpleAuthProvider:
    """Google and Microsoft OAuth authentication provider"""

    def __init__(self, google_client_id: str = None, google_client_secret: str = None,
                 microsoft_client_id: str = None, microsoft_client_secret: str = None,
                 microsoft_tenant_id: str = "common"):
        # Google OAuth config
        self.google_client_id = google_client_id
        self.google_client_secret = google_client_secret
        self.google_token_url = "https://oauth2.googleapis.com/token"
        self.google_userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        self.google_auth_url = "https://accounts.google.com/o/oauth2/auth"

        # Microsoft OAuth config
        self.microsoft_client_id = microsoft_client_id
        self.microsoft_client_secret = microsoft_client_secret
        self.microsoft_tenant_id = microsoft_tenant_id
        self.microsoft_token_url = f"https://login.microsoftonline.com/{microsoft_tenant_id}/oauth2/v2.0/token"
        self.microsoft_auth_url = f"https://login.microsoftonline.com/{microsoft_tenant_id}/oauth2/v2.0/authorize"
        self.microsoft_userinfo_url = "https://graph.microsoft.com/v1.0/me"
    
    def generate_secure_state(self) -> str:
        """Generate a cryptographically secure random state parameter for OAuth"""
        return secrets.token_urlsafe(32)
    
    def get_authorization_url(self, redirect_uri: str, service_name: str = "google", state: str = None) -> str:
        """Get OAuth authorization URL for Google or Microsoft"""
        if state is None:
            # Generate state in the format expected by frontend: serviceName_randomString
            random_part = self.generate_secure_state()
            state = f"{service_name}_{random_part}"

        if service_name == "microsoft":
            # Microsoft OAuth with Mail.Send and Mail.ReadWrite scopes for lead_gen
            params = {
                "client_id": self.microsoft_client_id,
                "redirect_uri": redirect_uri,
                "scope": "openid email profile offline_access User.Read Mail.Send Mail.ReadWrite",
                "response_type": "code",
                "response_mode": "query",
                "state": state,
                "prompt": "consent"
            }
            return f"{self.microsoft_auth_url}?{urlencode(params)}"
        else:
            # Google OAuth with Gmail scopes
            params = {
                "client_id": self.google_client_id,
                "redirect_uri": redirect_uri,
                "scope": "openid email profile https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.readonly",
                "response_type": "code",
                "access_type": "offline",
                "prompt": "consent",
                "state": state
            }
            # Use proper URL encoding
            return f"{self.google_auth_url}?{urlencode(params)}"
    
    async def exchange_code_for_tokens(self, code: str, redirect_uri: str, service_name: str = "google") -> Dict[str, Any]:
        """Exchange authorization code for tokens for Google or Microsoft"""
        async with httpx.AsyncClient() as client:
            if service_name == "microsoft":
                response = await client.post(
                    self.microsoft_token_url,
                    data={
                        "client_id": self.microsoft_client_id,
                        "client_secret": self.microsoft_client_secret,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": redirect_uri,
                        "scope": "openid email profile offline_access User.Read Mail.Send Mail.ReadWrite"
                    }
                )
            else:
                # Default to Google
                response = await client.post(
                    self.google_token_url,
                    data={
                        "client_id": self.google_client_id,
                        "client_secret": self.google_client_secret,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": redirect_uri,
                    }
                )

            if response.status_code != 200:
                error_detail = f"Failed to exchange code for tokens ({service_name}): {response.text}"
                logger.error(f"Token exchange failed: {error_detail}")
                raise HTTPException(status_code=400, detail=error_detail)

            tokens = response.json()
            tokens['provider'] = service_name  # Add provider info to response
            return tokens
    
    async def get_user_info(self, access_token: str, service_name: str = "google") -> Dict[str, Any]:
        """Get user information from Google or Microsoft"""
        async with httpx.AsyncClient() as client:
            if service_name == "microsoft":
                response = await client.get(
                    self.microsoft_userinfo_url,
                    headers={"Authorization": f"Bearer {access_token}"}
                )

                if response.status_code != 200:
                    error_detail = f"Failed to get Microsoft user info: {response.text}"
                    raise HTTPException(status_code=400, detail=error_detail)

                # Transform Microsoft user info to match Google format
                ms_user = response.json()
                return {
                    "id": ms_user.get("id"),
                    "email": ms_user.get("mail") or ms_user.get("userPrincipalName"),
                    "name": ms_user.get("displayName"),
                    "given_name": ms_user.get("givenName"),
                    "family_name": ms_user.get("surname"),
                    "picture": None,  # Microsoft Graph doesn't return picture URL directly
                    "provider": "microsoft"
                }
            else:
                # Default to Google
                response = await client.get(
                    self.google_userinfo_url,
                    headers={"Authorization": f"Bearer {access_token}"}
                )

                if response.status_code != 200:
                    error_detail = f"Failed to get Google user info: {response.text}"
                    raise HTTPException(status_code=400, detail=error_detail)

                user_info = response.json()
                user_info['provider'] = 'google'
                return user_info

    async def refresh_token(self, refresh_token: str, service_name: str = "google") -> Dict[str, Any]:
        """
        Refresh OAuth access token using refresh token.

        Args:
            refresh_token: The refresh token
            service_name: 'google' or 'microsoft'

        Returns:
            Dictionary with new access_token, refresh_token (if provided), and expires_in
        """
        async with httpx.AsyncClient() as client:
            if service_name == "microsoft":
                response = await client.post(
                    self.microsoft_token_url,
                    data={
                        "client_id": self.microsoft_client_id,
                        "client_secret": self.microsoft_client_secret,
                        "refresh_token": refresh_token,
                        "grant_type": "refresh_token",
                        "scope": "openid email profile offline_access User.Read Mail.Send Mail.ReadWrite"
                    }
                )
            else:
                # Default to Google
                response = await client.post(
                    self.google_token_url,
                    data={
                        "client_id": self.google_client_id,
                        "client_secret": self.google_client_secret,
                        "refresh_token": refresh_token,
                        "grant_type": "refresh_token"
                    }
                )

            if response.status_code != 200:
                error_detail = f"Failed to refresh {service_name} token: {response.text}"
                logger.error(f"Token refresh failed: {error_detail}")
                raise HTTPException(status_code=400, detail=error_detail)

            tokens = response.json()
            tokens['provider'] = service_name
            logger.info(f"Successfully refreshed {service_name} access token")
            return tokens


class JWTManager:
    """JWT token management provider"""
    
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
    
    def create_token(self, user_data: Dict[str, Any], expires_delta: timedelta = None) -> str:
        """Create JWT token"""
        if expires_delta is None:
            expires_delta = timedelta(hours=24)
        
        expire = datetime.now(timezone.utc) + expires_delta
        to_encode = user_data.copy()
        to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
        
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")


# Global provider instances
auth_provider: Optional[SimpleAuthProvider] = None
jwt_manager: Optional[JWTManager] = None


def init_auth(google_client_id: str = None, google_client_secret: str = None,
              microsoft_client_id: str = None, microsoft_client_secret: str = None,
              microsoft_tenant_id: str = "common", jwt_secret: str = None) -> None:
    """Initialize authentication providers for Google and/or Microsoft"""
    global auth_provider, jwt_manager

    if not jwt_secret:
        raise ValueError("JWT secret is required")

    # At least one provider must be configured
    if not (google_client_id and google_client_secret) and not (microsoft_client_id and microsoft_client_secret):
        raise ValueError("At least one OAuth provider (Google or Microsoft) must be configured")

    auth_provider = SimpleAuthProvider(
        google_client_id=google_client_id,
        google_client_secret=google_client_secret,
        microsoft_client_id=microsoft_client_id,
        microsoft_client_secret=microsoft_client_secret,
        microsoft_tenant_id=microsoft_tenant_id
    )
    jwt_manager = JWTManager(jwt_secret)


def get_auth_provider() -> SimpleAuthProvider:
    """Get the initialized auth provider"""
    if not auth_provider:
        raise HTTPException(status_code=500, detail="Authentication not initialized")
    return auth_provider


def get_jwt_manager() -> JWTManager:
    """Get the initialized JWT manager"""
    if not jwt_manager:
        raise HTTPException(status_code=500, detail="JWT manager not initialized")
    return jwt_manager


# Pydantic models for API requests
class LoginRequest(BaseModel):
    service: str


class TokenRequest(BaseModel):
    code: str
    state: Optional[str] = None
    provider: Optional[str] = "google"  # Support provider in token request