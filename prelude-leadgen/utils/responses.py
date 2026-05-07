"""
Standard response models and utilities for the lead generation service.

This module provides consistent response formats, pagination models,
and utility functions for API responses across all endpoints.
"""

from typing import Optional, Any, Dict, List, Generic, TypeVar
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from enum import Enum

T = TypeVar('T')


class ResponseStatus(str, Enum):
    """Standard response status codes."""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    PARTIAL = "partial"


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""
    page: int = Field(ge=1, description="Current page number")
    page_size: int = Field(ge=1, le=1000, description="Number of items per page")
    total_items: int = Field(ge=0, description="Total number of items")
    total_pages: int = Field(ge=0, description="Total number of pages")
    has_next: bool = Field(description="Whether there is a next page")
    has_previous: bool = Field(description="Whether there is a previous page")


class BaseResponse(BaseModel, Generic[T]):
    """Base response model for all API responses."""
    status: ResponseStatus = ResponseStatus.SUCCESS
    message: Optional[str] = None
    data: Optional[T] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    request_id: Optional[str] = None


class SuccessResponse(BaseResponse[T]):
    """Standard success response."""
    status: ResponseStatus = ResponseStatus.SUCCESS


class ErrorResponse(BaseResponse[None]):
    """Standard error response."""
    status: ResponseStatus = ResponseStatus.ERROR
    error_code: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    data: None = None


class PaginatedResponse(BaseResponse[List[T]]):
    """Paginated response for list endpoints."""
    pagination: PaginationMeta


class CountResponse(BaseResponse[int]):
    """Response for count/statistics endpoints."""
    pass


class BulkOperationResponse(BaseModel):
    """Response for bulk operations."""
    total_processed: int = Field(ge=0, description="Total number of items processed")
    successful: int = Field(ge=0, description="Number of successful operations")
    failed: int = Field(ge=0, description="Number of failed operations")
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="List of errors")
    warnings: List[Dict[str, Any]] = Field(default_factory=list, description="List of warnings")


class ValidationErrorResponse(ErrorResponse):
    """Response for validation errors."""
    field_errors: Optional[Dict[str, List[str]]] = None


class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    service: str
    version: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    uptime: Optional[str] = None
    dependencies: Optional[Dict[str, str]] = None


class MetricsResponse(BaseModel):
    """Metrics and statistics response."""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metrics: Dict[str, Any]
    period: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None


class SearchResponse(PaginatedResponse[T]):
    """Search results response."""
    query: str
    filters: Optional[Dict[str, Any]] = None
    sort_by: Optional[str] = None
    sort_order: Optional[str] = None
    search_time_ms: Optional[float] = None


class ExportResponse(BaseModel):
    """Export operation response."""
    export_id: str
    status: str = "initiated"
    file_url: Optional[str] = None
    file_size: Optional[int] = None
    expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Utility functions for creating responses
def success_response(
    data: Any = None,
    message: Optional[str] = None,
    request_id: Optional[str] = None
) -> SuccessResponse:
    """Create a success response."""
    return SuccessResponse(
        data=data,
        message=message,
        request_id=request_id
    )


def error_response(
    message: str,
    error_code: Optional[str] = None,
    error_details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> ErrorResponse:
    """Create an error response."""
    return ErrorResponse(
        message=message,
        error_code=error_code,
        error_details=error_details,
        request_id=request_id
    )


def paginated_response(
    data: List[T],
    page: int,
    page_size: int,
    total_items: int,
    message: Optional[str] = None,
    request_id: Optional[str] = None
) -> PaginatedResponse[T]:
    """Create a paginated response."""
    total_pages = (total_items + page_size - 1) // page_size
    
    pagination = PaginationMeta(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1
    )
    
    return PaginatedResponse(
        data=data,
        pagination=pagination,
        message=message,
        request_id=request_id
    )


def search_response(
    data: List[T],
    query: str,
    page: int,
    page_size: int,
    total_items: int,
    filters: Optional[Dict[str, Any]] = None,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = None,
    search_time_ms: Optional[float] = None,
    request_id: Optional[str] = None
) -> SearchResponse[T]:
    """Create a search response."""
    total_pages = (total_items + page_size - 1) // page_size
    
    pagination = PaginationMeta(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1
    )
    
    return SearchResponse(
        data=data,
        pagination=pagination,
        query=query,
        filters=filters,
        sort_by=sort_by,
        sort_order=sort_order,
        search_time_ms=search_time_ms,
        request_id=request_id
    )


def bulk_operation_response(
    total_processed: int,
    successful: int,
    failed: int,
    errors: Optional[List[Dict[str, Any]]] = None,
    warnings: Optional[List[Dict[str, Any]]] = None
) -> BulkOperationResponse:
    """Create a bulk operation response."""
    return BulkOperationResponse(
        total_processed=total_processed,
        successful=successful,
        failed=failed,
        errors=errors or [],
        warnings=warnings or []
    )


def validation_error_response(
    message: str,
    field_errors: Optional[Dict[str, List[str]]] = None,
    request_id: Optional[str] = None
) -> ValidationErrorResponse:
    """Create a validation error response."""
    return ValidationErrorResponse(
        message=message,
        error_code="VALIDATION_ERROR",
        field_errors=field_errors,
        request_id=request_id
    )


def health_check_response(
    service: str,
    version: str,
    status: str = "healthy",
    uptime: Optional[str] = None,
    dependencies: Optional[Dict[str, str]] = None
) -> HealthCheckResponse:
    """Create a health check response."""
    return HealthCheckResponse(
        status=status,
        service=service,
        version=version,
        uptime=uptime,
        dependencies=dependencies
    )


def metrics_response(
    metrics: Dict[str, Any],
    period: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None
) -> MetricsResponse:
    """Create a metrics response."""
    return MetricsResponse(
        metrics=metrics,
        period=period,
        filters=filters
    )