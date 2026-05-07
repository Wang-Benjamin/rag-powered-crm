import sys
import os
from dotenv import load_dotenv

# Load environment variables FIRST before any imports that use them
load_dotenv()

# Add src directory to path for imports
src_path = os.path.join(os.path.dirname(__file__), 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

import logging
import sentry_sdk
from contextlib import asynccontextmanager
from fastapi import FastAPI

if os.getenv("SENTRY_DSN"):
    try:
        sentry_sdk.init(
            dsn=os.getenv("SENTRY_DSN"),
            traces_sample_rate=0.1,
            environment=os.getenv("ENVIRONMENT", "development"),
        )
    except Exception:
        logging.getLogger(__name__).warning("Failed to initialize Sentry", exc_info=True)
from fastapi.middleware.cors import CORSMiddleware
from service_core.pool import TenantPoolManager
from service_core.db import init_pool_manager
from routers.invitations_router import router as invitations_router
from routers.activity_router import router as activity_router
from routers.password_auth_router import router as password_auth_router
from routers.email_training_router import router as email_training_router
from routers.signature_router import router as signature_router
from routers.template_router import router as template_router
from routers.oauth_router import router as oauth_router
from routers.writing_style_router import router as writing_style_router
from routers.ai_preferences_router import router as ai_preferences_router
from routers.preload_router import router as preload_router
from routers.locale_router import router as locale_router
from routers.factory_profile_router import router as factory_profile_router
from routers.certification_router import router as certification_router
from routers.hs_codes_router import router as hs_codes_router
from routers.ingestion_router import router as ingestion_router
from routers.product_catalog_router import router as product_catalog_router
from routers.outreach_router import router as outreach_router
from routers.smtp_router import router as smtp_router
from routers.wechat_router import router as wechat_router
from config.settings import ALLOWED_ORIGINS
from config import settings
from config.constants import API_PREFIX
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize auth
from auth import init_auth

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application lifespan events."""
    # Startup
    logging.info("User Settings Service starting up...")

    # Initialize TenantPoolManager (asyncpg connection pools)
    tenant_pool_manager = TenantPoolManager()
    init_pool_manager(tenant_pool_manager)
    logger.info("TenantPoolManager initialized")

    # Initialize authentication (OAuth providers + JWT)
    try:
        init_auth(
            google_client_id=settings.GOOGLE_CLIENT_ID,
            google_client_secret=settings.GOOGLE_CLIENT_SECRET,
            microsoft_client_id=settings.MICROSOFT_CLIENT_ID,
            microsoft_client_secret=settings.MICROSOFT_CLIENT_SECRET,
            microsoft_tenant_id=settings.MICROSOFT_TENANT_ID,
            jwt_secret=settings.JWT_SECRET
        )
        logger.info("Authentication system initialized (Google + Microsoft)")
    except Exception as e:
        logger.error(f"Failed to initialize auth: {e}")

    yield

    # Shutdown
    logging.info("User Settings Service shutting down...")
    await tenant_pool_manager.close_all()
    logger.info("All connection pools closed")

app = FastAPI(
    title="User Settings & Activity Service",
    description="Service for managing team invitations, user profiles, and activity logging",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

# CORS configuration - using ALLOWED_ORIGINS from settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(invitations_router, prefix=API_PREFIX, tags=["Team Invitations"])
app.include_router(activity_router, prefix=API_PREFIX, tags=["Activity Logging"])
app.include_router(password_auth_router, prefix=API_PREFIX, tags=["Password Authentication"])
app.include_router(oauth_router, prefix=API_PREFIX, tags=["OAuth Authentication"])
app.include_router(email_training_router, prefix=API_PREFIX, tags=["Email Training"])
app.include_router(signature_router, prefix=API_PREFIX, tags=["Email Signature"])
app.include_router(template_router, prefix=API_PREFIX, tags=["Email Templates"])
app.include_router(writing_style_router, prefix=API_PREFIX, tags=["Writing Style"])
app.include_router(ai_preferences_router, prefix=API_PREFIX, tags=["AI Preferences"])
app.include_router(preload_router, prefix=API_PREFIX, tags=["Data Preload"])
app.include_router(locale_router, prefix=API_PREFIX, tags=["User Locale"])
app.include_router(factory_profile_router, prefix=API_PREFIX, tags=["Factory Profile"])
app.include_router(certification_router, prefix=API_PREFIX, tags=["Certifications"])
app.include_router(hs_codes_router, prefix=API_PREFIX, tags=["HS Codes"])
app.include_router(ingestion_router, prefix=API_PREFIX, tags=["Document Ingestion"])
app.include_router(product_catalog_router, prefix=API_PREFIX, tags=["Product Catalog"])
app.include_router(outreach_router, prefix=API_PREFIX, tags=["Outreach Email"])
app.include_router(smtp_router, prefix=API_PREFIX, tags=["SMTP Email Config"])
app.include_router(wechat_router, prefix=API_PREFIX, tags=["WeChat Login"])

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "user-settings",
        "port": 8005,
        "features": {
            "team_invitations": True,
            "activity_logging": True,
            "database_routing": True,
            "email_training": True,
            "email_signature": True,
            "email_templates": True,
            "oauth_authentication": True,
            "password_authentication": True,
            "writing_style": True,
            "document_ingestion": True
        }
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8005))
    host = os.environ.get("HOST", "0.0.0.0")
    
    logger.info(f"Starting Team Invitations Service on {host}:{port}")
    logger.info(f"Available endpoints:")
    logger.info(f"   - Health: http://localhost:{port}/health")
    logger.info(f"   - API Docs: http://localhost:{port}/docs")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_level="info",
        reload=os.getenv("ENV") != "production"
    )
