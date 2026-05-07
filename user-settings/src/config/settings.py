"""
Configuration settings for Team Invitations Service
"""
import os
from typing import List

# CORS settings
def get_allowed_origins() -> List[str]:
    """Get allowed CORS origins from environment or use defaults."""
    env_origins = os.getenv("FRONTEND_CORS_ORIGINS")
    if env_origins:
        return [origin.strip() for origin in env_origins.split(",")]
    return [
        "http://localhost:8000",  # Frontend
        "http://localhost:3000",  # Alternative frontend port
        "https://prelude-frontend-438832142728.us-central1.run.app",  # Production frontend
    ]

ALLOWED_ORIGINS: List[str] = get_allowed_origins()

# OAuth settings for Google and Microsoft
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
JWT_SECRET = os.getenv("JWT_SECRET", "")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is not set")

# Microsoft OAuth settings
MICROSOFT_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID", "")
MICROSOFT_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET", "")
MICROSOFT_TENANT_ID = os.getenv("MICROSOFT_TENANT_ID", "common")