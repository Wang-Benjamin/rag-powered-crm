"""Standard response models for CRM Service."""

from typing import Any, Optional, List, Dict
from pydantic import BaseModel


class StandardResponse(BaseModel):
    """Standard API response model."""
    
    success: bool
    message: str
    data: Optional[Any] = None
    error: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "data": {"id": 1, "name": "Example"},
                "error": None
            }
        }


class PaginatedResponse(BaseModel):
    """Paginated API response model."""
    
    success: bool
    message: str
    data: List[Any]
    total: int
    page: int = 1
    page_size: int = 20
    total_pages: int = 1
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Data retrieved successfully",
                "data": [{"id": 1, "name": "Example"}],
                "total": 100,
                "page": 1,
                "page_size": 20,
                "total_pages": 5
            }
        }


class ErrorResponse(BaseModel):
    """Error response model."""
    
    success: bool = False
    message: str
    error: str
    details: Optional[Dict[str, Any]] = None
    
    class Config:
        schema_extra = {
            "example": {
                "success": False,
                "message": "An error occurred",
                "error": "ValidationError",
                "details": {"field": "email", "reason": "Invalid email format"}
            }
        }


def success_response(message: str = "Success", data: Any = None) -> StandardResponse:
    """Create a success response."""
    return StandardResponse(success=True, message=message, data=data)


def error_response(message: str = "Error", error: str = None, details: Any = None) -> ErrorResponse:
    """Create an error response."""
    return ErrorResponse(
        success=False,
        message=message,
        error=error or "UnknownError",
        details=details
    )


def paginated_response(
    data: List[Any],
    total: int,
    page: int = 1,
    page_size: int = 20,
    message: str = "Data retrieved successfully"
) -> PaginatedResponse:
    """Create a paginated response."""
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 1
    
    return PaginatedResponse(
        success=True,
        message=message,
        data=data,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )