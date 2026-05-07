"""
Standalone Lead Generation Backend Server
Runs on port 9000 to avoid conflicts with main backend
"""

import os
import sentry_sdk
from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn
import logging

if os.getenv("SENTRY_DSN"):
    try:
        sentry_sdk.init(
            dsn=os.getenv("SENTRY_DSN"),
            traces_sample_rate=0.1,
            environment=os.getenv("ENVIRONMENT", "development"),
        )
    except Exception:
        logging.getLogger(__name__).warning("Failed to initialize Sentry", exc_info=True)
from dotenv import load_dotenv

# Playwright chromium is pre-installed in the Dockerfile.

# Load environment variables from .env file
load_dotenv()

# Import authentication from local auth module
from auth.providers import init_auth

# Import lead generation components
from routers.leads_router import router as lead_router
from routers.crm_sync_router import router as crm_sync_router

# Import lead info components (read-only: bol-intelligence, email-timeline, email-stats, reply-status)
from routers.lead_info_router import router as lead_info_router

# Import tracking components
from routers.tracking_router import router as tracking_router

# Import auth components
from routers.auth_router import router as auth_router

# Import OAuth token management components
from routers.oauth_token_router import router as oauth_token_router

# Import personnel and workflow components
from routers.personnel_router import router as personnel_router
from routers.workflow_router import router as workflow_router


# Import ImportYeti (BoL pipeline) components
from routers.importyeti_router import router as importyeti_router

# Import translation components
from routers.translation_router import router as translation_router

# Import two-pager report components
from routers.two_pager_router import router as two_pager_router




# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API prefix for route consolidation
API_PREFIX = "/api/leads"

from service_core.pool import TenantPoolManager
from service_core.db import init_pool_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application lifespan events."""
    logger.info("Lead Gen API starting up...")

    # Initialize TenantPoolManager (asyncpg connection pools)
    tenant_pool_manager = TenantPoolManager()
    init_pool_manager(tenant_pool_manager)
    logger.info("TenantPoolManager initialized")

    # Test Redis connection (non-blocking)
    try:
        from utils.redis_cache import get_cache
        cache = get_cache()
        if cache.is_available:
            logger.info("Redis connection verified")
        else:
            logger.warning("Redis not available - caching disabled")
    except Exception as e:
        logger.warning(f"Redis initialization warning: {e}")

    yield

    # Shutdown
    logger.info("Lead Gen API shutting down...")
    await tenant_pool_manager.close_all()
    try:
        from importyeti.clients import internal_bol_client
        await internal_bol_client.close_client()
    except Exception as e:
        logger.warning(f"Internal BoL client close failed: {e}")
    logger.info("All connection pools closed")


# Create FastAPI app
app = FastAPI(
    title="Lead Generation API",
    description="Comprehensive lead generation and management system",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Initialize authentication
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
MICROSOFT_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID", "")
MICROSOFT_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET", "")
MICROSOFT_TENANT_ID = os.getenv("MICROSOFT_TENANT_ID", "common")
JWT_SECRET = os.getenv("JWT_SECRET", "")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is not set")

try:
    init_auth(
        google_client_id=GOOGLE_CLIENT_ID,
        google_client_secret=GOOGLE_CLIENT_SECRET,
        microsoft_client_id=MICROSOFT_CLIENT_ID,
        microsoft_client_secret=MICROSOFT_CLIENT_SECRET,
        microsoft_tenant_id=MICROSOFT_TENANT_ID,
        jwt_secret=JWT_SECRET
    )
    logger.info("Authentication initialized successfully")
    if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
        logger.info("  - Google OAuth configured")
    if MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET:
        logger.info("  - Microsoft OAuth configured")
except Exception as e:
    logger.warning(f"Authentication initialization failed: {e}")
    logger.warning("Some endpoints may not work without proper auth configuration")

# Lead service functionality now distributed across repositories and feature services

# Include the lead routers
app.include_router(lead_router, prefix=API_PREFIX, tags=["leads"])
app.include_router(crm_sync_router, prefix=API_PREFIX, tags=["leads-crm"])

# Include the tracking router
app.include_router(tracking_router, prefix=API_PREFIX, tags=["tracking"])

# Include the lead info router (read-only buyer dashboard endpoints)
app.include_router(lead_info_router, prefix=API_PREFIX, tags=["lead-info"])

# Include the auth router
app.include_router(auth_router, prefix=API_PREFIX, tags=["authentication"])

# Include the OAuth token management router
app.include_router(oauth_token_router, prefix=API_PREFIX, tags=["oauth-tokens"])

# Include the workflow router
app.include_router(workflow_router, prefix=API_PREFIX, tags=["workflow"])

# Include the personnel router
app.include_router(personnel_router, prefix=API_PREFIX, tags=["personnel"])

# Include the ImportYeti (BoL pipeline) router
app.include_router(importyeti_router, prefix=API_PREFIX, tags=["importyeti"])

# Include the translation router
app.include_router(translation_router, prefix=API_PREFIX, tags=["translation"])

# Include the two-pager report router
app.include_router(two_pager_router, prefix=API_PREFIX, tags=["two-pager"])


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint for the Lead Generation API"""
    return {
        "message": "Lead Generation API is running!",
        "docs": "/docs",
        "version": "1.0.0"
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "lead-generation-api",
        "version": "1.0.0"
    }

# Test endpoint for API
@app.get("/test-api")
async def test_api():
    """Simple test endpoint to verify API is working"""
    return {
        "message": "API is working!",
        "auth_status": "not required for this endpoint",
        "available_endpoints": {
            "docs": "/docs",
            "health": "/health",
            "api_health": "/api/leads/health",
            "leads": "/api/leads (requires auth)",
        }
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 9000))
    logger.info(f"Starting Lead Generation API server on port {port}...")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=os.getenv("ENV") != "production"
    )
