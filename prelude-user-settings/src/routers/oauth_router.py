"""
OAuth Authentication Router
============================
Handles Google and Microsoft OAuth authentication flows.
"""

import os
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone

# Local auth module for JWT creation and OAuth providers
import auth.oauth_providers as auth_module
from auth import verify_auth_token, LoginRequest, TokenRequest

from service_core.db import get_pool_manager
from services.employee_sync import sync_user_to_employee_info

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth")

FRONTEND_REDIRECT_URI = os.environ.get("FRONTEND_REDIRECT_URI", "http://localhost:8000/auth/callback")


async def ensure_user_profile_exists(user_info: Dict[str, Any], provider: str) -> str:
    """Ensure user profile exists in user_profiles table. Returns db_name."""
    email = user_info.get("email")
    if not email:
        return "prelude_visitor"

    try:
        pm = get_pool_manager()
        pool = await pm.get_analytics_pool()
        async with pool.acquire() as conn:
            existing = await conn.fetchval(
                "SELECT email FROM user_profiles WHERE email = $1", email
            )

            if not existing:
                name = user_info.get("name", email.split('@')[0])
                await conn.execute(
                    """
                    INSERT INTO user_profiles (email, username, name, company, role, db_name, has_real_email, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                    """,
                    email, email, name,
                    email.split('@')[1] if '@' in email else 'unknown',
                    'user', 'prelude_visitor', True
                )
                logger.info(f"Created user profile for {email} with prelude_visitor (via {provider})")

                user_data = await conn.fetchrow(
                    "SELECT email, username, name, company, role, db_name FROM user_profiles WHERE email = $1",
                    email
                )
                if user_data:
                    await sync_user_to_employee_info(dict(user_data))

            # Look up db_name
            row = await conn.fetchrow(
                "SELECT db_name FROM user_profiles WHERE email = $1 LIMIT 1", email
            )
            if row and row.get('db_name'):
                return row['db_name']

    except Exception as e:
        logger.error(f"Failed to ensure user profile exists: {e}")

    return "prelude_visitor"


@router.post("/login", summary="Initiate OAuth Authentication Flow")
async def post_authorization_url_endpoint(request_body: LoginRequest):
    """Initiate the authentication flow for Google or Microsoft OAuth."""
    service = request_body.service

    if service not in ["google", "microsoft"]:
        raise HTTPException(status_code=400, detail=f"Unsupported authentication service: {service}")

    try:
        authorization_url = auth_module.auth_provider.get_authorization_url(
            redirect_uri=FRONTEND_REDIRECT_URI,
            service_name=service
        )
        return {"authorization_url": authorization_url}
    except Exception as e:
        logger.error(f"Failed to initiate auth flow: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to initiate authentication flow")


@router.post("/token", summary="Exchange Authorization Code for Tokens")
async def exchange_code_for_tokens_endpoint(request_body: TokenRequest):
    """Exchange the authorization code for tokens with Google or Microsoft."""
    try:
        provider = request_body.provider

        if request_body.refresh_token:
            token_data = await auth_module.auth_provider.refresh_token(
                refresh_token=request_body.refresh_token,
                service_name=provider
            )
        else:
            token_data = await auth_module.auth_provider.exchange_code_for_tokens(
                code=request_body.code,
                redirect_uri=FRONTEND_REDIRECT_URI,
                service_name=provider
            )

        user_info = await auth_module.auth_provider.get_user_info(
            token_data["access_token"],
            service_name=provider
        )

        db_name = await ensure_user_profile_exists(user_info, provider)

        jwt_token = auth_module.jwt_manager.create_token({
            "sub": user_info["id"],
            "email": user_info["email"],
            "name": user_info.get("name", ""),
            "picture": user_info.get("picture", ""),
            "provider": provider,
            "db_name": db_name,
        })

        return {
            "access_token": jwt_token,
            "id_token": jwt_token,
            "token_type": "bearer",
            "user_info": user_info,
            "oauth_access_token": token_data["access_token"],
            "oauth_refresh_token": token_data.get("refresh_token"),
            "oauth_expires_in": token_data.get("expires_in"),
            "provider": provider
        }

    except Exception as e:
        logger.error(f"Token exchange failed: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Failed to exchange code for tokens")


@router.options("/protected", summary="Protected Endpoint Options")
async def protected_endpoint_options():
    return {"message": "OK"}


@router.get("/protected", summary="Protected Endpoint")
async def protected_endpoint(authenticated_user: dict = Depends(verify_auth_token)):
    """Verify JWT token validity."""
    return {"message": "You are authenticated", "user": authenticated_user}


