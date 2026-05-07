"""
Authentication Router for Lead Generation Service
OAuth endpoints for Google and Microsoft authentication
"""

import logging
import os
from fastapi import APIRouter, HTTPException
from auth.providers import get_auth_provider, get_jwt_manager, LoginRequest, TokenRequest

logger = logging.getLogger(__name__)

router = APIRouter()

# Get redirect URI from environment
REDIRECT_URI = os.getenv("MICROSOFT_REDIRECT_URI", "http://localhost:9000/auth/callback")


@router.post("/auth/login", summary="Initiate OAuth Flow")
async def initiate_oauth_flow(request: LoginRequest):
    """
    Initiates the OAuth flow for Google or Microsoft.
    Returns the authorization URL the frontend should redirect to.

    Args:
        request: LoginRequest with service name ('google' or 'microsoft')

    Returns:
        Dict with authorization_url
    """
    service = request.service
    logger.info(f"Initiating OAuth flow for service: {service}")

    if service not in ["google", "microsoft"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported authentication service: {service}"
        )

    try:
        auth_provider = get_auth_provider()

        # Get authorization URL with secure random state
        authorization_url = auth_provider.get_authorization_url(
            redirect_uri=REDIRECT_URI,
            service_name=service
            # state is automatically generated securely by the auth provider
        )

        logger.info(f"Successfully generated authorization URL for {service}")
        return {"authorization_url": authorization_url}

    except Exception as e:
        logger.error(f"Failed to initiate OAuth flow: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to initiate authentication flow"
        ) from e


@router.post("/auth/token", summary="Exchange Authorization Code for Tokens")
async def exchange_code_for_tokens(request: TokenRequest):
    """
    Exchanges the authorization code for access and refresh tokens.
    Also gets user info and creates a JWT token for the user.

    Args:
        request: TokenRequest with code, provider, and optional state

    Returns:
        Dict with access_token, refresh_token, user info, and JWT token
    """
    logger.info(f"Exchanging authorization code for {request.provider} tokens")

    try:
        auth_provider = get_auth_provider()
        jwt_manager = get_jwt_manager()

        # Exchange code for tokens
        tokens = await auth_provider.exchange_code_for_tokens(
            code=request.code,
            redirect_uri=REDIRECT_URI,
            service_name=request.provider
        )

        # Get user info
        user_info = await auth_provider.get_user_info(
            access_token=tokens['access_token'],
            service_name=request.provider
        )

        # Create JWT token for the user
        user_data = {
            "id": user_info.get("id"),
            "email": user_info.get("email"),
            "name": user_info.get("name"),
            "provider": request.provider
        }
        jwt_token = jwt_manager.create_token(user_data)

        logger.info(f"Successfully exchanged code and created JWT for {user_info.get('email')}")

        return {
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "expires_in": tokens.get("expires_in", 3600),
            "token_type": tokens.get("token_type", "Bearer"),
            "user": user_info,
            "jwt_token": jwt_token,
            "provider": request.provider
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to exchange code for tokens: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to exchange authorization code: {str(e)}"
        ) from e


@router.get("/auth/callback", summary="OAuth Callback Endpoint")
async def oauth_callback(code: str = None, state: str = None, error: str = None):
    """
    OAuth callback endpoint that receives the authorization code from the OAuth provider.
    This is typically called by the OAuth provider after user consent.

    In a typical flow:
    1. User clicks "Connect Gmail" or "Connect Outlook" in frontend
    2. Frontend calls POST /auth/login to get authorization URL
    3. Frontend redirects user to authorization URL
    4. User consents on Google/Microsoft page
    5. OAuth provider redirects back to this callback endpoint
    6. Frontend should then call POST /auth/token with the code to get tokens

    Args:
        code: Authorization code from OAuth provider
        state: State parameter for CSRF protection
        error: Error message if OAuth failed

    Returns:
        HTML response that closes the popup and sends data to parent window
    """
    if error:
        logger.error(f"OAuth callback received error: {error}")
        return f"""
        <html>
            <body>
                <h2>Authentication Failed</h2>
                <p>Error: {error}</p>
                <script>
                    if (window.opener) {{
                        window.opener.postMessage({{
                            type: 'oauth_error',
                            error: '{error}'
                        }}, '*');
                        window.close();
                    }}
                </script>
            </body>
        </html>
        """

    if not code:
        raise HTTPException(status_code=400, detail="No authorization code received")

    # Extract provider from state (format: "serviceName_randomString")
    provider = "google"  # default
    if state and "_" in state:
        provider = state.split("_")[0]

    logger.info(f"OAuth callback received for provider: {provider}")

    # Return HTML that sends the code and state back to the frontend
    # The frontend will then call POST /auth/token to exchange the code for tokens
    return f"""
    <html>
        <body>
            <h2>Authentication Successful</h2>
            <p>Completing authentication...</p>
            <script>
                if (window.opener) {{
                    window.opener.postMessage({{
                        type: 'oauth_success',
                        code: '{code}',
                        state: '{state}',
                        provider: '{provider}'
                    }}, '*');
                    window.close();
                }} else {{
                    // If not in popup, redirect to frontend with code
                    const frontendUrl = 'http://localhost:8000';
                    window.location.href = `${{frontendUrl}}/auth-callback?code={code}&state={state}&provider={provider}`;
                }}
            </script>
        </body>
    </html>
    """
