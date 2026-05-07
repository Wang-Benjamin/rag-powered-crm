"""
Activity Logging Router
======================
API endpoints for logging user activities across the platform.
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import logging

from service_core.activity import ActivityLogger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/activity")


class PageViewRequest(BaseModel):
    user_email: str = Field(..., description="User's email address")
    page_url: str = Field(..., description="URL/route of the page")
    session_id: Optional[str] = Field(None, description="Browser session ID")
    duration_ms: Optional[int] = Field(None, description="Time spent on page in milliseconds")
    referrer: Optional[str] = Field(None, description="Previous page URL")


class ActivityLogRequest(BaseModel):
    user_email: str = Field(..., description="User's email address")
    action_type: str = Field(..., description="Activity type (e.g., 'navigation', 'crm')")
    action_name: str = Field(..., description="Specific action (e.g., 'page_view', 'customer_view')")
    session_id: Optional[str] = Field(None, description="Browser/WebSocket session ID")
    action_category: Optional[str] = Field(None, description="Optional sub-category")
    page_url: Optional[str] = Field(None, description="Frontend page/route")
    service_name: Optional[str] = Field(None, description="Backend service name")
    action_data: Optional[Dict[str, Any]] = Field(None, description="Additional data as JSON")
    result_status: str = Field("success", description="Status: 'success', 'error', 'pending'")
    result_data: Optional[Dict[str, Any]] = Field(None, description="Results or error info")
    duration_ms: Optional[int] = Field(None, description="Duration in milliseconds")
    tags: Optional[List[str]] = Field(None, description="Searchable tags")


class ActivityLogResponse(BaseModel):
    success: bool
    message: str


@router.post("/page-view", response_model=ActivityLogResponse)
async def log_page_view(request: PageViewRequest, req: Request):
    """Log a page view activity."""
    try:
        user_agent = req.headers.get("user-agent")
        ip_address = req.client.host if req.client else None

        # Derive module from page_url (e.g., "/crm/deals" -> "crm", "/leads" -> "leads")
        module = None
        if request.page_url:
            parts = request.page_url.strip("/").split("/")
            if parts and parts[0]:
                module = parts[0]

        details = {
            "page_url": request.page_url,
            "service_name": "frontend",
        }
        if module:
            details["module"] = module
        if request.session_id:
            details["session_id"] = request.session_id
        if request.duration_ms is not None:
            details["duration_ms"] = request.duration_ms
        if user_agent:
            details["user_agent"] = user_agent
        if ip_address:
            details["ip_address"] = ip_address
        if request.referrer:
            details["referrer"] = request.referrer

        await ActivityLogger.track(
            action="page_view",
            resource_type="page",
            details=details,
            user_id=request.user_email,
        )

        return ActivityLogResponse(
            success=True,
            message="Page view logged successfully",
        )
    except Exception as e:
        logger.error(f"Error logging page view: {e}")
        raise HTTPException(status_code=500, detail=f"Error logging page view: {str(e)}")


@router.post("/log", response_model=ActivityLogResponse)
async def log_activity(request: ActivityLogRequest, req: Request):
    """Log a generic user activity."""
    try:
        user_agent = req.headers.get("user-agent")
        ip_address = req.client.host if req.client else None

        details: Dict[str, Any] = {}
        if request.session_id:
            details["session_id"] = request.session_id
        if request.action_category:
            details["action_category"] = request.action_category
        if request.page_url:
            details["page_url"] = request.page_url
        if request.service_name:
            details["service_name"] = request.service_name
        if user_agent:
            details["user_agent"] = user_agent
        if ip_address:
            details["ip_address"] = ip_address
        if request.action_data:
            details["action_data"] = request.action_data
        if request.result_status != "success":
            details["result_status"] = request.result_status
        if request.result_data:
            details["result_data"] = request.result_data
        if request.duration_ms is not None:
            details["duration_ms"] = request.duration_ms
        if request.tags:
            details["tags"] = request.tags

        await ActivityLogger.track(
            action=request.action_type,
            resource_type=request.action_name,
            details=details or None,
            user_id=request.user_email,
        )

        return ActivityLogResponse(
            success=True,
            message="Activity logged successfully",
        )
    except Exception as e:
        logger.error(f"Error logging activity: {e}")
        raise HTTPException(status_code=500, detail=f"Error logging activity: {str(e)}")


