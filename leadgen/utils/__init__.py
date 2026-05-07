"""
Utilities module for the lead generation service.

This module provides cross-cutting concerns including exception handling,
response formatting, validation, helper functions, and AI service management.
"""

# Import key utilities for easy access
from .exceptions import (
    LeadGenBaseException,
    LeadGenSafetyError,
    ValidationError,
    DatabaseError,
    ConnectionPoolError,
    AuthenticationError,
    AuthorizationError,
    TokenError,
    LeadNotFoundError,
    PersonnelNotFoundError,
    DuplicateResourceError,
    BusinessLogicError,
    ExternalServiceError,
    AIServiceError,
    RateLimitError,
    ConfigurationError,
    DataQualityError,
    OperationTimeoutError,
    ResourceLimitError,
    exception_to_http_detail,
    get_http_status_code
)

from .responses import (
    ResponseStatus,
    PaginationMeta,
    BaseResponse,
    SuccessResponse,
    ErrorResponse,
    PaginatedResponse,
    CountResponse,
    BulkOperationResponse,
    ValidationErrorResponse,
    HealthCheckResponse,
    MetricsResponse,
    SearchResponse,
    ExportResponse,
    success_response,
    error_response,
    paginated_response,
    search_response,
    bulk_operation_response,
    validation_error_response,
    health_check_response,
    metrics_response
)

from .helpers import (
    setup_logging,
    clean_text,
    clean_phone,
    clean_email,
    clean_website,
    extract_domain_from_email,
    extract_domain_from_website,
    generate_unique_id,
    generate_hash,
    random_delay,
    get_current_timestamp,
    format_timestamp,
    parse_timestamp,
    truncate_text,
    safe_get_nested,
    chunk_list,
    flatten_dict
)

from .validators import (
    validate_email,
    validate_phone,
    validate_website,
    validate_company_name,
    validate_lead_status,
    validate_pagination_params,
    validate_date_range,
    validate_search_query,
    validate_sort_params,
    validate_table_operation,
    validate_json_field,
    validate_id_format,
    validate_lead_create_data,
    validate_personnel_create_data
)

from .ai_connection_manager import (
    AIProvider,
    PerplexityProvider,
    OpenAIProvider,
    AIConnectionManager,
    get_ai_connection_manager,
    initialize_ai_services,
    make_ai_request
)

__all__ = [
    # Exceptions
    "LeadGenBaseException",
    "LeadGenSafetyError",
    "ValidationError",
    "DatabaseError",
    "ConnectionPoolError",
    "AuthenticationError",
    "AuthorizationError",
    "TokenError",
    "LeadNotFoundError",
    "PersonnelNotFoundError",
    "DuplicateResourceError",
    "BusinessLogicError",
    "ExternalServiceError",
    "AIServiceError",
    "RateLimitError",
    "ConfigurationError",
    "DataQualityError",
    "OperationTimeoutError",
    "ResourceLimitError",
    "exception_to_http_detail",
    "get_http_status_code",
    
    # Response utilities
    "ResponseStatus",
    "PaginationMeta",
    "BaseResponse",
    "SuccessResponse",
    "ErrorResponse",
    "PaginatedResponse",
    "CountResponse",
    "BulkOperationResponse",
    "ValidationErrorResponse",
    "HealthCheckResponse",
    "MetricsResponse",
    "SearchResponse",
    "ExportResponse",
    "success_response",
    "error_response",
    "paginated_response",
    "search_response",
    "bulk_operation_response",
    "validation_error_response",
    "health_check_response",
    "metrics_response",
    
    # Helper functions
    "setup_logging",
    "clean_text",
    "clean_phone",
    "clean_email",
    "clean_website",
    "extract_domain_from_email",
    "extract_domain_from_website",
    "generate_unique_id",
    "generate_hash",
    "random_delay",
    "get_current_timestamp",
    "format_timestamp",
    "parse_timestamp",
    "truncate_text",
    "safe_get_nested",
    "chunk_list",
    "flatten_dict",

    # Validators
    "validate_email",
    "validate_phone",
    "validate_website",
    "validate_company_name",
    "validate_lead_status",
    "validate_pagination_params",
    "validate_date_range",
    "validate_search_query",
    "validate_sort_params",
    "validate_table_operation",
    "validate_json_field",
    "validate_id_format",
    "validate_lead_create_data",
    "validate_personnel_create_data",
    
    # AI Connection Management
    "AIProvider",
    "PerplexityProvider", 
    "OpenAIProvider",
    "AIConnectionManager",
    "get_ai_connection_manager",
    "initialize_ai_services",
    "make_ai_request"
]