"""
OAuth Token Router for Lead Generation
Endpoints for managing OAuth tokens (Google and Microsoft)
Stores tokens in database for auto-refresh functionality

Uses get_tenant_connection for DB access — OAuthTokenManager
reads conn from contextvars via get_current_conn().
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from services.oauth_token_manager import OAuthTokenManager
from service_core.db import get_tenant_connection
from auth.providers import get_auth_provider

logger = logging.getLogger(__name__)

router = APIRouter()


class SaveTokenRequest(BaseModel):
    """Request to save OAuth tokens"""
    provider: str  # 'google' or 'microsoft'
    access_token: str
    refresh_token: str
    expires_in: int  # Token expiry in seconds (usually 3600)
    scope: Optional[str] = None
    employee_id: Optional[int] = None


class TokenStatusResponse(BaseModel):
    """Response with token status"""
    has_token: bool
    provider: str
    user_email: str
    expires_at: Optional[str] = None
    scope: Optional[str] = None


@router.post("/oauth/save-tokens")
async def save_oauth_tokens(
    request: SaveTokenRequest,
    tenant=Depends(get_tenant_connection)
):
    """
    Save OAuth tokens to database for auto-refresh.
    Called by frontend after user authenticates with Google/Microsoft.
    """
    try:
        conn, user = tenant
        user_email = user.get('email')
        if not user_email:
            raise HTTPException(status_code=400, detail="User email not found in token")

        # Validate provider
        if request.provider not in ['google', 'microsoft']:
            raise HTTPException(status_code=400, detail="Provider must be 'google' or 'microsoft'")

        # Get auth provider for refresh capability
        auth_provider = get_auth_provider()

        # Create token manager (reads conn from contextvars)
        token_manager = OAuthTokenManager(auth_provider)

        # Store tokens
        success = await token_manager.store_tokens(
            user_email=user_email,
            provider=request.provider,
            access_token=request.access_token,
            refresh_token=request.refresh_token,
            expires_in=request.expires_in,
            scope=request.scope,
            employee_id=request.employee_id
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to save tokens")

        logger.info(f"Saved {request.provider} tokens for {user_email}")

        return {
            "success": True,
            "message": f"Successfully saved {request.provider} tokens",
            "user_email": user_email,
            "provider": request.provider
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving OAuth tokens: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/oauth/token-status/{provider}")
async def get_token_status(
    provider: str,
    tenant=Depends(get_tenant_connection)
) -> TokenStatusResponse:
    """Check if user has stored OAuth tokens for a provider."""
    try:
        conn, user = tenant
        user_email = user.get('email')
        if not user_email:
            raise HTTPException(status_code=400, detail="User email not found in token")

        if provider not in ['google', 'microsoft']:
            raise HTTPException(status_code=400, detail="Provider must be 'google' or 'microsoft'")

        auth_provider = get_auth_provider()
        token_manager = OAuthTokenManager(auth_provider)

        token_info = await token_manager.get_token_info(user_email, provider)

        if token_info:
            return TokenStatusResponse(
                has_token=True,
                provider=provider,
                user_email=user_email,
                expires_at=token_info['token_expiry'].isoformat(),
                scope=token_info.get('scope')
            )
        else:
            return TokenStatusResponse(
                has_token=False,
                provider=provider,
                user_email=user_email
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking token status: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/oauth/delete-tokens/{provider}")
async def delete_oauth_tokens(
    provider: str,
    tenant=Depends(get_tenant_connection)
):
    """Delete stored OAuth tokens for a provider."""
    try:
        conn, user = tenant
        user_email = user.get('email')
        if not user_email:
            raise HTTPException(status_code=400, detail="User email not found in token")

        if provider not in ['google', 'microsoft']:
            raise HTTPException(status_code=400, detail="Provider must be 'google' or 'microsoft'")

        auth_provider = get_auth_provider()
        token_manager = OAuthTokenManager(auth_provider)

        success = await token_manager.delete_tokens(user_email, provider)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete tokens")

        logger.info(f"Deleted {provider} tokens for {user_email}")

        return {
            "success": True,
            "message": f"Successfully deleted {provider} tokens",
            "user_email": user_email,
            "provider": provider
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting OAuth tokens: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/oauth/refresh-token/{provider}")
async def refresh_token(
    provider: str,
    tenant=Depends(get_tenant_connection)
):
    """Refresh and get a valid access token. Auto-refreshes the token if expired."""
    try:
        conn, user = tenant
        user_email = user.get('email')
        if not user_email:
            raise HTTPException(status_code=400, detail="User email not found in token")

        if provider not in ['google', 'microsoft']:
            raise HTTPException(status_code=400, detail="Provider must be 'google' or 'microsoft'")

        auth_provider = get_auth_provider()
        token_manager = OAuthTokenManager(auth_provider)

        access_token = await token_manager.get_valid_access_token(user_email, provider)

        if not access_token:
            raise HTTPException(
                status_code=404,
                detail=f"No valid {provider} token found. Please re-authenticate."
            )

        return {
            "success": True,
            "access_token": access_token,
            "provider": provider,
            "user_email": user_email
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting valid token: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
