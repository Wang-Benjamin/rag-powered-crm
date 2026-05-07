"""
Shared JWT authentication for Prelude Platform services.

Replaces the duplicated verify_auth_token in each service.
Extracts db_name from JWT when available, falls back to DB lookup.
"""

import os
import logging
from typing import Dict, Any

import jwt
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)
security = HTTPBearer()

_jwt_secret: str = ""


def _get_secret() -> str:
    global _jwt_secret
    if not _jwt_secret:
        _jwt_secret = os.getenv("JWT_SECRET", "")
        if not _jwt_secret:
            raise RuntimeError("JWT_SECRET environment variable is not set")
    return _jwt_secret


async def verify_auth_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """
    FastAPI dependency that verifies a JWT and returns the decoded claims.

    Returns dict with: email, db_name, sub, name, picture, provider, etc.
    If db_name is missing from the JWT (old token), it will be None.
    The caller or get_tenant_connection dependency handles the fallback lookup.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="No credentials provided")

    secret = _get_secret()

    try:
        payload = jwt.decode(
            credentials.credentials,
            secret,
            algorithms=["HS256"],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
