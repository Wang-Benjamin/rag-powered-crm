"""Main FastAPI application for CRM Service."""

import os
import sys
import logging
import sentry_sdk
from dotenv import load_dotenv

load_dotenv()
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
from service_core.pool import TenantPoolManager
from service_core.db import init_pool_manager
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Configure UTF-8 stdio on Windows
if os.name == 'nt':
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Setup logging
logging.basicConfig(
    level=logging.INFO,  # Changed from WARNING to INFO to see debug logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
# Disable verbose httpx logging
logging.getLogger("httpx").setLevel(logging.WARNING)

# Suppress email sync INFO logs - only show warnings and errors
logging.getLogger("email_service.sync.gmail_sync").setLevel(logging.WARNING)
logging.getLogger("routers.gmail_sync_router").setLevel(logging.WARNING)
logging.getLogger("routers.outlook_sync_router").setLevel(logging.WARNING)
logging.getLogger("email_service.sync.outlook_sync").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Import configuration
from config.settings import settings
from config.constants import API_PREFIX

# Import routers
from routers.email_router import router as email_router
from routers.email_mass_router import router as email_mass_router
from routers.analytics_router import router as analytics_router
from routers.crm_data_router import router as data_router
from routers.crm_contacts_router import router as contacts_router
from routers.deals_router import router as deals_router
from routers.deal_activities_router import router as deal_activities_router
from routers.interaction_router import router as interaction_router
from routers.gmail_sync_router import router as gmail_router
from routers.outlook_sync_router import router as outlook_router
from routers.upload_router import router as upload_router
from routers.notes_router import router as notes_router
from routers.meetings_router import router as meetings_router
from routers.calendar_sync_router import router as calendar_sync_router
from routers.oauth_token_router import router as oauth_token_router
from routers.scheduled_jobs_router import router as scheduled_jobs_router
from routers.call_summary_router import router as call_summary_router
from routers.tracking_router import router as tracking_router
from routers.feedback_router import router as feedback_router
from routers.temporal_router import router as temporal_router
from routers.rag_admin_router import router as rag_admin_router
from routers.translation_router import router as translation_router
from routers.deal_room_router import router as deal_room_router
from routers.public_deal_room_router import router as public_deal_room_router
from routers.public_storefront_router import router as public_storefront_router
from routers.campaign_router import router as campaign_router
from routers.outreach_router import router as outreach_router

# Initialize auth
from auth.providers import init_auth

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown."""
    # Startup
    logger.info(f"Starting {settings.APP_NAME}...")

    # Initialize TenantPoolManager (asyncpg)
    tenant_pool = TenantPoolManager()
    init_pool_manager(tenant_pool)
    logger.info("TenantPoolManager initialized")

    # Initialize authentication
    try:
        init_auth(
            settings.GOOGLE_CLIENT_ID,
            settings.GOOGLE_CLIENT_SECRET,
            settings.JWT_SECRET,
            microsoft_client_id=settings.MICROSOFT_CLIENT_ID,
            microsoft_client_secret=settings.MICROSOFT_CLIENT_SECRET,
            microsoft_tenant_id=settings.MICROSOFT_TENANT_ID
        )
        logger.info("Authentication system initialized (Google + Microsoft)")
    except Exception as e:
        logger.error(f"Failed to initialize auth: {e}")

    # Start Temporal workers only when explicitly enabled.
    #
    # Topology contract:
    # - one shared Temporal namespace;
    # - env-prefixed queues/schedules;
    # - APP_ENV=main is the only recurring scheduler owner for the shared DB;
    # - local workers are disabled by default.
    from temporal_workflows.topology import get_temporal_topology

    temporal_topology = get_temporal_topology()
    if temporal_topology.any_worker_enabled:
        try:
            temporal_topology.validate_worker_startup()
            from temporal_workflows.worker import start_worker_in_background
            start_worker_in_background()
            logger.info("✅ Temporal worker thread started")
            logger.info(f"   App env: {temporal_topology.app_env}")
            logger.info(f"   Shared namespace: {temporal_topology.namespace or '(not configured)'}")
            logger.info(f"   Scheduler owner: {temporal_topology.scheduler_owner}")
            logger.info(f"   Scheduler worker enabled: {temporal_topology.scheduler_worker_enabled}")
            logger.info(f"   Mass email worker enabled: {temporal_topology.mass_email_worker_enabled}")
            logger.info(f"   Scheduler queue: {temporal_topology.scheduler_task_queue}")
            logger.info(f"   Mass email queue: {temporal_topology.mass_email_task_queue}")
        except Exception as e:
            logger.error(f"❌ Failed to start Temporal worker: {e}")
            logger.warning("   Temporal workers will not run")
    else:
        logger.info("⏸  Temporal workers disabled")
        logger.info(f"   App env: {temporal_topology.app_env}")
        logger.info("   Enable with ENABLE_TEMPORAL_MASS_EMAIL_WORKER=true and/or ENABLE_TEMPORAL_SCHEDULER_WORKER=true")

    yield

    # Shutdown
    logger.info(f"Shutting down {settings.APP_NAME}...")
    await tenant_pool.close_all()
    logger.info("TenantPoolManager shut down")

# Create FastAPI app with lifespan management
app = FastAPI(
    title=settings.APP_NAME,
    description="Customer Relationship Management service with AI-powered features and automated summary generation",
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.cors_allow_methods_list,
    allow_headers=settings.cors_allow_headers_list,
)

# Authentication is now handled in lifespan function

# Include routers
app.include_router(email_router, prefix=API_PREFIX, tags=["Emails"])
app.include_router(email_mass_router, prefix=API_PREFIX, tags=["Mass Email"])
app.include_router(analytics_router, prefix=API_PREFIX, tags=["Analytics"])
app.include_router(data_router, prefix=API_PREFIX, tags=["CRM Data"])
app.include_router(contacts_router, prefix=API_PREFIX, tags=["Contacts"])
app.include_router(deals_router, prefix=API_PREFIX, tags=["Deals"])
app.include_router(deal_activities_router, prefix=API_PREFIX, tags=["Deal Activities"])
app.include_router(interaction_router, prefix=API_PREFIX, tags=["Interactions"])
app.include_router(gmail_router, prefix=API_PREFIX, tags=["Gmail Sync"])
app.include_router(outlook_router, prefix=API_PREFIX, tags=["Outlook Sync"])
app.include_router(upload_router, prefix=API_PREFIX + "/upload", tags=["Customer Upload"])
app.include_router(notes_router, prefix=API_PREFIX, tags=["Notes"])
app.include_router(meetings_router, prefix=API_PREFIX, tags=["Meetings & Calendar"])
app.include_router(calendar_sync_router, prefix=API_PREFIX, tags=["Calendar Sync"])
app.include_router(oauth_token_router, prefix=API_PREFIX, tags=["OAuth Tokens"])
app.include_router(scheduled_jobs_router, prefix=API_PREFIX, tags=["Scheduled Jobs"])
app.include_router(call_summary_router, prefix=API_PREFIX, tags=["Call Summaries"])
app.include_router(tracking_router, tags=["Email Tracking"])
app.include_router(feedback_router, prefix=API_PREFIX, tags=["Feedback"])
app.include_router(temporal_router, prefix=API_PREFIX, tags=["Temporal Workflows"])
app.include_router(rag_admin_router, prefix=API_PREFIX, tags=["RAG Admin"])
app.include_router(translation_router, prefix=API_PREFIX, tags=["Translation"])
app.include_router(deal_room_router, prefix=API_PREFIX, tags=["Deal Rooms"])
app.include_router(public_deal_room_router, prefix=API_PREFIX, tags=["Public Deal Room"])
app.include_router(public_storefront_router, prefix=API_PREFIX, tags=["Public Storefront"])
app.include_router(campaign_router, prefix=API_PREFIX + "/campaigns", tags=["campaigns"])
app.include_router(outreach_router, prefix=API_PREFIX, tags=["Outreach"])


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "message": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "endpoints": {
            "customers": f"{API_PREFIX}/customers",
            "analytics": f"{API_PREFIX}/generate-analytics-insights",
            "emails": f"{API_PREFIX}/generate-email",
            "interactions": f"{API_PREFIX}/interaction-summaries",
        }
    }


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "prelude-crm"}


if __name__ == "__main__":
    logger.info(f"Starting {settings.APP_NAME}...")
    logger.info(f"API Documentation: http://localhost:{settings.PORT}/docs")
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=os.getenv("ENV") != "production")
