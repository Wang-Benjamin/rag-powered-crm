"""FastAPI authentication dependencies."""

import logging
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Import from the parent auth module
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from auth.providers import verify_auth_token, auth_provider

logger = logging.getLogger(__name__)

# Security scheme for Bearer tokens
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Dependency to get the current authenticated user.
    
    Args:
        credentials: HTTP Bearer token credentials
        
    Returns:
        User information from the token
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authentication credentials provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    user_info = verify_auth_token(token)
    
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user_info


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """
    Optional authentication dependency.
    Returns user info if authenticated, None otherwise.
    """
    if not credentials:
        return None
    
    try:
        token = credentials.credentials
        return verify_auth_token(token)
    except Exception as e:
        logger.warning(f"Optional auth failed: {e}")
        return None


def require_role(required_role: str):
    """
    Dependency factory to require a specific role.
    
    Args:
        required_role: The role required to access the endpoint
        
    Returns:
        Dependency function that validates the user's role
    """
    async def role_validator(user: dict = Depends(get_current_user)) -> dict:
        user_role = user.get("role", "viewer")
        
        # Role hierarchy: admin > manager > user > viewer
        role_hierarchy = {
            "viewer": 0,
            "user": 1,
            "manager": 2,
            "admin": 3
        }
        
        user_level = role_hierarchy.get(user_role, 0)
        required_level = role_hierarchy.get(required_role, 0)
        
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role}"
            )
        
        return user
    
    return role_validator


# Convenient role-specific dependencies
require_admin = require_role("admin")
require_manager = require_role("manager")
require_user = require_role("user")