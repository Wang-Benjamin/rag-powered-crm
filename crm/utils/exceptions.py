"""Custom exceptions for CRM Service."""

from typing import Any, Optional


class CRMException(Exception):
    """Base exception for CRM Service."""
    
    def __init__(self, message: str, status_code: int = 500, details: Optional[Any] = None):
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)


class NotFoundException(CRMException):
    """Exception raised when a resource is not found."""
    
    def __init__(self, message: str = "Resource not found", details: Optional[Any] = None):
        super().__init__(message, status_code=404, details=details)


class ValidationException(CRMException):
    """Exception raised for validation errors."""
    
    def __init__(self, message: str = "Validation error", details: Optional[Any] = None):
        super().__init__(message, status_code=400, details=details)


class UnauthorizedException(CRMException):
    """Exception raised for unauthorized access."""
    
    def __init__(self, message: str = "Unauthorized", details: Optional[Any] = None):
        super().__init__(message, status_code=401, details=details)


class ForbiddenException(CRMException):
    """Exception raised for forbidden access."""
    
    def __init__(self, message: str = "Forbidden", details: Optional[Any] = None):
        super().__init__(message, status_code=403, details=details)


class ConflictException(CRMException):
    """Exception raised for conflict errors."""
    
    def __init__(self, message: str = "Conflict", details: Optional[Any] = None):
        super().__init__(message, status_code=409, details=details)


class DatabaseException(CRMException):
    """Exception raised for database errors."""
    
    def __init__(self, message: str = "Database error", details: Optional[Any] = None):
        super().__init__(message, status_code=500, details=details)


class AIServiceException(CRMException):
    """Exception raised for AI service errors."""
    
    def __init__(self, message: str = "AI service error", details: Optional[Any] = None):
        super().__init__(message, status_code=503, details=details)


class EmailServiceException(CRMException):
    """Exception raised for email service errors."""
    
    def __init__(self, message: str = "Email service error", details: Optional[Any] = None):
        super().__init__(message, status_code=503, details=details)