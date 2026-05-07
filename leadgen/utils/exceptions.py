"""
Custom exceptions for the lead generation service.

This module defines all custom exceptions used throughout the lead generation
system, providing clear error handling and consistent error responses.
"""

from typing import Optional, Dict, Any


class LeadGenBaseException(Exception):
    """Base exception class for all lead generation service exceptions."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}


class LeadGenSafetyError(LeadGenBaseException):
    """Raised when an operation would affect non-lead-gen tables."""
    
    def __init__(self, message: str, table_name: Optional[str] = None):
        super().__init__(message, error_code="SAFETY_VIOLATION")
        self.table_name = table_name


class ValidationError(LeadGenBaseException):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, field: Optional[str] = None, value: Optional[Any] = None):
        super().__init__(message, error_code="VALIDATION_ERROR")
        self.field = field
        self.value = value


class DatabaseError(LeadGenBaseException):
    """Raised when database operations fail."""
    
    def __init__(self, message: str, operation: Optional[str] = None, table: Optional[str] = None):
        super().__init__(message, error_code="DATABASE_ERROR")
        self.operation = operation
        self.table = table


class ConnectionPoolError(DatabaseError):
    """Raised when database connection pool issues occur."""
    
    def __init__(self, message: str):
        super().__init__(message, error_code="CONNECTION_POOL_ERROR")


class AuthenticationError(LeadGenBaseException):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, error_code="AUTH_ERROR")


class AuthorizationError(LeadGenBaseException):
    """Raised when authorization fails."""
    
    def __init__(self, message: str = "Access denied", required_role: Optional[str] = None):
        super().__init__(message, error_code="AUTHORIZATION_ERROR")
        self.required_role = required_role


class TokenError(AuthenticationError):
    """Raised when JWT token issues occur."""
    
    def __init__(self, message: str, token_type: Optional[str] = None):
        super().__init__(message)
        self.error_code = "TOKEN_ERROR"
        self.token_type = token_type


class LeadNotFoundError(LeadGenBaseException):
    """Raised when a requested lead is not found."""
    
    def __init__(self, lead_id: str):
        super().__init__(f"Lead with ID '{lead_id}' not found", error_code="LEAD_NOT_FOUND")
        self.lead_id = lead_id


class PersonnelNotFoundError(LeadGenBaseException):
    """Raised when requested personnel is not found."""
    
    def __init__(self, personnel_id: str):
        super().__init__(f"Personnel with ID '{personnel_id}' not found", error_code="PERSONNEL_NOT_FOUND")
        self.personnel_id = personnel_id


class DuplicateResourceError(LeadGenBaseException):
    """Raised when attempting to create a resource that already exists."""
    
    def __init__(self, resource_type: str, identifier: str):
        super().__init__(
            f"{resource_type} with identifier '{identifier}' already exists",
            error_code="DUPLICATE_RESOURCE"
        )
        self.resource_type = resource_type
        self.identifier = identifier


class BusinessLogicError(LeadGenBaseException):
    """Raised when business logic validation fails."""
    
    def __init__(self, message: str, rule: Optional[str] = None):
        super().__init__(message, error_code="BUSINESS_LOGIC_ERROR")
        self.rule = rule


class ExternalServiceError(LeadGenBaseException):
    """Raised when external service calls fail."""
    
    def __init__(self, message: str, service: str, status_code: Optional[int] = None):
        super().__init__(message, error_code="EXTERNAL_SERVICE_ERROR")
        self.service = service
        self.status_code = status_code


class AIServiceError(ExternalServiceError):
    """Raised when AI service operations fail."""
    
    def __init__(self, message: str, provider: str, model: Optional[str] = None):
        super().__init__(message, service=provider, error_code="AI_SERVICE_ERROR")
        self.provider = provider
        self.model = model


class RateLimitError(ExternalServiceError):
    """Raised when rate limits are exceeded."""
    
    def __init__(self, message: str, service: str, retry_after: Optional[int] = None):
        super().__init__(message, service=service, error_code="RATE_LIMIT_ERROR")
        self.retry_after = retry_after


class ConfigurationError(LeadGenBaseException):
    """Raised when configuration is invalid or missing."""
    
    def __init__(self, message: str, config_key: Optional[str] = None):
        super().__init__(message, error_code="CONFIGURATION_ERROR")
        self.config_key = config_key


class DataQualityError(LeadGenBaseException):
    """Raised when data quality checks fail."""
    
    def __init__(self, message: str, data_type: str, quality_score: Optional[float] = None):
        super().__init__(message, error_code="DATA_QUALITY_ERROR")
        self.data_type = data_type
        self.quality_score = quality_score


class OperationTimeoutError(LeadGenBaseException):
    """Raised when operations exceed timeout limits."""
    
    def __init__(self, message: str, operation: str, timeout_seconds: Optional[int] = None):
        super().__init__(message, error_code="OPERATION_TIMEOUT")
        self.operation = operation
        self.timeout_seconds = timeout_seconds


class ResourceLimitError(LeadGenBaseException):
    """Raised when resource limits are exceeded."""
    
    def __init__(self, message: str, resource_type: str, limit: Optional[int] = None, current: Optional[int] = None):
        super().__init__(message, error_code="RESOURCE_LIMIT_ERROR")
        self.resource_type = resource_type
        self.limit = limit
        self.current = current


# Utility function to convert exceptions to HTTP error details
def exception_to_http_detail(exc: Exception) -> Dict[str, Any]:
    """Convert an exception to HTTP error detail format."""
    if isinstance(exc, LeadGenBaseException):
        return {
            "error": exc.error_code or "UNKNOWN_ERROR",
            "message": exc.message,
            "details": exc.details
        }
    else:
        return {
            "error": "INTERNAL_SERVER_ERROR",
            "message": str(exc),
            "details": {}
        }


# HTTP status code mapping for exceptions
EXCEPTION_STATUS_CODES = {
    LeadNotFoundError: 404,
    PersonnelNotFoundError: 404,
    ValidationError: 400,
    AuthenticationError: 401,
    TokenError: 401,
    AuthorizationError: 403,
    DuplicateResourceError: 409,
    BusinessLogicError: 422,
    DataQualityError: 422,
    ExternalServiceError: 502,
    AIServiceError: 502,
    RateLimitError: 429,
    ConfigurationError: 500,
    DatabaseError: 500,
    ConnectionPoolError: 503,
    OperationTimeoutError: 504,
    ResourceLimitError: 429,
    LeadGenSafetyError: 403
}


def get_http_status_code(exc: Exception) -> int:
    """Get the appropriate HTTP status code for an exception."""
    return EXCEPTION_STATUS_CODES.get(type(exc), 500)