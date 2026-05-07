"""
Simple authentication module compatible with backend_lead
"""

import jwt
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# JWT configuration
JWT_SECRET = os.getenv("JWT_SECRET", "")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is not set")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Security scheme
security = HTTPBearer()

class JWTManager:
    """JWT token management"""
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.algorithm = JWT_ALGORITHM
    
    def create_token(self, user_data: Dict[str, Any]) -> str:
        """Create JWT token for user"""
        payload = {
            **user_data,
            "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
            "iat": datetime.now(timezone.utc)
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")

# Global JWT manager instance
jwt_manager: Optional[JWTManager] = None

def init_auth(google_client_id: str, google_client_secret: str, jwt_secret: str):
    """Initialize authentication system"""
    global jwt_manager
    jwt_manager = JWTManager(jwt_secret)
    print(f"Authentication initialized with JWT secret")

def verify_auth_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Dependency to verify authentication token"""
    # Import from providers module
    from auth.providers import get_jwt_manager
    import logging
    logger = logging.getLogger(__name__)

    try:
        jwt_mgr = get_jwt_manager()
        token = credentials.credentials
        payload = jwt_mgr.verify_token(token)
        logger.info(f"Token verified successfully for user: {payload.get('email', 'unknown')}")
        return payload
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication failed: {e}", exc_info=True)
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")

def get_user_email(user_claims: Dict[str, Any] = Depends(verify_auth_token)) -> str:
    """Get user email from authentication claims"""
    return user_claims.get("email", "unknown")