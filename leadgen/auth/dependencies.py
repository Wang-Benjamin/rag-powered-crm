"""
FastAPI authentication dependencies for Prelude Lead Generation Service
Contains only FastAPI Depends() wrappers for authentication
"""

import jwt
import logging
from typing import Dict, Any
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .providers import get_jwt_manager

logger = logging.getLogger(__name__)

# HTTP Bearer security scheme
security = HTTPBearer()


async def verify_auth_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    FastAPI dependency to verify authentication token
    
    Args:
        credentials: HTTP Bearer credentials from request header
        
    Returns:
        Dict containing user claims from JWT token
        
    Raises:
        HTTPException: If token is invalid, expired, or missing
    """
    try:
        jwt_manager = get_jwt_manager()
        
        if not credentials:
            raise HTTPException(status_code=401, detail="No credentials provided")
        
        if not credentials.credentials:
            raise HTTPException(status_code=401, detail="No token provided")
        
        user_claims = jwt_manager.verify_token(credentials.credentials)
        
        # Optional: Add user activity tracking here if needed
        # This would require importing user tracking service
        
        return user_claims
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error verifying token: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def get_current_user(token_data: Dict[str, Any] = Depends(verify_auth_token)) -> Dict[str, Any]:
    """
    FastAPI dependency to get current authenticated user
    
    Args:
        token_data: JWT token claims from verify_auth_token dependency
        
    Returns:
        Dict containing current user information
    """
    return token_data


async def get_user_email(token_data: Dict[str, Any] = Depends(verify_auth_token)) -> str:
    """
    FastAPI dependency to get current user's email
    
    Args:
        token_data: JWT token claims from verify_auth_token dependency
        
    Returns:
        User's email address
        
    Raises:
        HTTPException: If email is not found in token
    """
    email = token_data.get('email')
    if not email:
        raise HTTPException(status_code=401, detail="Email not found in token")
    return email


async def get_user_id(token_data: Dict[str, Any] = Depends(verify_auth_token)) -> str:
    """
    FastAPI dependency to get current user's ID
    
    Args:
        token_data: JWT token claims from verify_auth_token dependency
        
    Returns:
        User's ID
        
    Raises:
        HTTPException: If user ID is not found in token
    """
    user_id = token_data.get('sub') or token_data.get('id')
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found in token")
    return user_id


# Optional: Admin role dependency
async def require_admin_role(token_data: Dict[str, Any] = Depends(verify_auth_token)) -> Dict[str, Any]:
    """
    FastAPI dependency to require admin role
    
    Args:
        token_data: JWT token claims from verify_auth_token dependency
        
    Returns:
        Dict containing user claims if user is admin
        
    Raises:
        HTTPException: If user is not admin
    """
    user_roles = token_data.get('roles', [])
    if 'admin' not in user_roles:
        raise HTTPException(status_code=403, detail="Admin access required")
    return token_data