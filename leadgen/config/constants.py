"""Application constants for Lead Generation Service."""

from enum import Enum
from typing import Dict, List

# Service Information
SERVICE_NAME = "Prelude Lead Generation Service"
SERVICE_VERSION = "1.0.0"
SERVICE_DESCRIPTION = "Comprehensive lead generation and management system"

# API Route Prefixes
API_V1_PREFIX = "/api/v1"
HEALTH_ENDPOINT = "/health"
DOCS_ENDPOINT = "/docs"
REDOC_ENDPOINT = "/redoc"

# Lead Management Endpoints
LEADS_PREFIX = "/leads"
LEAD_ANALYTICS_PREFIX = "/leads/analytics"
LEAD_EXPORT_PREFIX = "/leads/export"
LEAD_IMPORT_PREFIX = "/leads/import"

# Data Management Endpoints
DATA_PREFIX = "/data"
DATA_UPLOAD_ENDPOINT = "/data/upload"
DATA_TABLES_ENDPOINT = "/data/tables"
DATA_EXPORT_ENDPOINT = "/data/export"

# Search and Query Endpoints
SEARCH_PREFIX = "/search"
QUERY_ENDPOINT = "/sales/query"
MARKET_DENSITY_PREFIX = "/market-density"

# Email Endpoints
EMAIL_PREFIX = "/email"
EMAIL_GENERATE_ENDPOINT = "/email/generate"
EMAIL_SEND_ENDPOINT = "/email/send"

# Authentication Endpoints
AUTH_PREFIX = "/auth"
AUTH_LOGIN_ENDPOINT = "/auth/login"
AUTH_CALLBACK_ENDPOINT = "/auth/callback"
AUTH_LOGOUT_ENDPOINT = "/auth/logout"

# Lead Status Values
class LeadStatus(str, Enum):
    """Lead status enumeration."""
    NEW = "new"
    SYNCED_TO_CRM = "synced_to_crm"
    QUALIFIED = "qualified"
    NOT_INTERESTED = "not_interested"

# Lead Source Values  
class LeadSource(str, Enum):
    """Lead source enumeration."""
    CSV_UPLOAD = "csv_upload"
    WEB_SCRAPING = "web_scraping"
    MANUAL_ENTRY = "manual_entry"
    API_IMPORT = "api_import"
    YELLOWPAGES = "yellowpages"
    LINKEDIN = "linkedin"
    PERPLEXITY = "perplexity"
    GOOGLE_SEARCH = "google_search"
    GOOGLE_MAPS = "google_maps"
    IMPORTYETI = "importyeti"

# Response Status Codes
HTTP_200_OK = 200
HTTP_201_CREATED = 201
HTTP_400_BAD_REQUEST = 400
HTTP_401_UNAUTHORIZED = 401
HTTP_403_FORBIDDEN = 403
HTTP_404_NOT_FOUND = 404
HTTP_422_UNPROCESSABLE_ENTITY = 422
HTTP_500_INTERNAL_SERVER_ERROR = 500

# Standard Response Messages
MESSAGES = {
    "success": "Operation completed successfully",
    "created": "Resource created successfully", 
    "updated": "Resource updated successfully",
    "deleted": "Resource deleted successfully",
    "not_found": "Resource not found",
    "unauthorized": "Authentication required",
    "forbidden": "Access denied",
    "validation_error": "Validation failed",
    "internal_error": "Internal server error",
    "rate_limited": "Rate limit exceeded"
}

# Default Configuration Values
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
DEFAULT_TIMEOUT = 30
MAX_TIMEOUT = 300

# Search Configuration
MAX_SEARCH_RESULTS_PER_REQUEST = 20
MAX_TOTAL_SEARCH_RESULTS = 100
MAX_SEARCH_PAGES = 10
SEARCH_TIMEOUT_SECONDS = 10

# Rate Limiting
RATE_LIMIT_DEFAULT = 100  # requests per minute
RATE_LIMIT_BURST = 200    # burst limit
RATE_LIMIT_WINDOW = 60    # window in seconds

# Database Configuration
DB_CONNECTION_TIMEOUT = 30
DB_QUERY_TIMEOUT = 60
DB_POOL_OVERFLOW = 20
DB_POOL_RECYCLE = 3600

# File Upload Configuration
MAX_FILE_SIZE_MB = 50
ALLOWED_FILE_EXTENSIONS = [".csv", ".xlsx", ".json"]
UPLOAD_CHUNK_SIZE = 8192

# Email Configuration
EMAIL_TIMEOUT = 30
MAX_EMAIL_RECIPIENTS = 100
EMAIL_RETRY_ATTEMPTS = 3
EMAIL_RETRY_DELAY = 5

# LinkedIn Integration
LINKEDIN_RATE_LIMIT = 200  # requests per hour
LINKEDIN_TIMEOUT = 30
LINKEDIN_MAX_RESULTS = 100

# Google Services Configuration
GOOGLE_MAPS_DEFAULT_RADIUS_KM = 10.0
GOOGLE_MAPS_MAX_RADIUS_KM = 50.0
GOOGLE_SEARCH_RATE_LIMIT = 100  # requests per day
GOOGLE_SEARCH_TIMEOUT = 10

# Perplexity API Configuration
PERPLEXITY_RATE_LIMIT = 200  # requests per hour
PERPLEXITY_TIMEOUT = 30
PERPLEXITY_MAX_TOKENS = 4000

# Playwright Web Scraping
PLAYWRIGHT_DEFAULT_TIMEOUT = 30000  # milliseconds
PLAYWRIGHT_NAVIGATION_TIMEOUT = 60000  # milliseconds
PLAYWRIGHT_MAX_PAGES = 10

# Market Density Analysis
MARKET_DENSITY_LEVELS = {
    "very_low": 0.0,
    "low": 0.2,
    "medium": 0.5,
    "high": 0.8,
    "very_high": 1.0
}

# Industry Categories (commonly used in lead generation)
INDUSTRY_CATEGORIES = [
    "Technology",
    "Software Development",
    "Finance",
    "Banking", 
    "Healthcare",
    "Manufacturing",
    "Retail",
    "E-commerce",
    "Real Estate",
    "Construction",
    "Education",
    "Consulting",
    "Marketing",
    "Advertising",
    "Media",
    "Entertainment",
    "Transportation",
    "Logistics",
    "Energy",
    "Utilities",
    "Telecommunications",
    "Automotive",
    "Aerospace",
    "Biotechnology",
    "Pharmaceuticals",
    "Food & Beverage",
    "Agriculture",
    "Mining",
    "Government",
    "Non-profit",
    "Insurance",
    "Legal Services",
    "Professional Services",
    "Hospitality",
    "Travel",
    "Sports",
    "Gaming"
]

# Company Size Categories
COMPANY_SIZE_CATEGORIES = [
    "1-10 employees",
    "11-50 employees", 
    "51-200 employees",
    "201-500 employees",
    "501-1000 employees",
    "1001-5000 employees",
    "5000+ employees"
]

# Revenue Categories
REVENUE_CATEGORIES = [
    "Less than $1M",
    "$1M - $10M",
    "$10M - $50M",
    "$50M - $100M",
    "$100M - $500M",
    "$500M - $1B",
    "$1B+"
]

# Lead Quality Scores
LEAD_QUALITY_SCORES = {
    "excellent": 5,
    "good": 4,
    "average": 3,
    "poor": 2,
    "very_poor": 1
}

# Cache Configuration
CACHE_TTL_SHORT = 300      # 5 minutes
CACHE_TTL_MEDIUM = 3600    # 1 hour
CACHE_TTL_LONG = 86400     # 24 hours

# Export Formats
EXPORT_FORMATS = ["csv", "xlsx", "json", "pdf"]

# Data Validation Rules
MIN_COMPANY_NAME_LENGTH = 2
MAX_COMPANY_NAME_LENGTH = 200
MIN_LEAD_NAME_LENGTH = 2
MAX_LEAD_NAME_LENGTH = 100

# API Client User Agents
USER_AGENT = f"{SERVICE_NAME}/{SERVICE_VERSION}"
BROWSER_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# Logging Configuration
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Error Codes (for internal tracking)
ERROR_CODES = {
    "AUTH_FAILED": "E001",
    "VALIDATION_ERROR": "E002", 
    "DATABASE_ERROR": "E003",
    "API_ERROR": "E004",
    "RATE_LIMIT_ERROR": "E005",
    "TIMEOUT_ERROR": "E006",
    "FILE_ERROR": "E007",
    "NETWORK_ERROR": "E008"
}

def get_lead_status_options() -> List[str]:
    """Get all available lead status options."""
    return [status.value for status in LeadStatus]

def get_lead_source_options() -> List[str]:
    """Get all available lead source options.""" 
    return [source.value for source in LeadSource]

def is_valid_lead_status(status: str) -> bool:
    """Check if a status is valid."""
    return status in get_lead_status_options()

def is_valid_lead_source(source: str) -> bool:
    """Check if a source is valid."""
    return source in get_lead_source_options()

def get_message(key: str, default: str = "Unknown message") -> str:
    """Get a standard message by key."""
    return MESSAGES.get(key, default)