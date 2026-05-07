"""Application constants for CRM Service."""

# API Prefixes
API_PREFIX = "/api/crm"
INVITATIONS_PREFIX = "/api/invitations"

# Database constants
DEFAULT_DATABASE_NAME = "prelude_backend"
USER_PROFILES_TABLE = "user_profiles"
CUSTOMERS_TABLE = "customers"
INTERACTIONS_TABLE = "interactions"

# Response messages
SUCCESS_MESSAGE = "Operation completed successfully"
ERROR_MESSAGE = "An error occurred"
NOT_FOUND_MESSAGE = "Resource not found"
UNAUTHORIZED_MESSAGE = "Unauthorized access"

# Email templates
EMAIL_TEMPLATE_PATHS = {
    "welcome": "templates/welcome_email.html",
    "follow_up": "templates/follow_up_email.html",
    "meeting": "templates/meeting_email.html"
}

# AI Model configurations
DEFAULT_AI_MODEL = "gpt-4"
AI_TEMPERATURE = 0.7
AI_MAX_TOKENS = 1000

# Pagination defaults
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# Cache settings
CACHE_TTL = 3600  # 1 hour in seconds

# Date formats
DEFAULT_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"