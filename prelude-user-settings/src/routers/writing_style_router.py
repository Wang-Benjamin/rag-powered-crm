"""
Writing Style Router
Handles writing style initialization and management for employee onboarding
"""

import logging
import json
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Optional

from services.writing_style_service import analyze_writing_style_with_ai
from service_core.db import get_tenant_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/writing-style")


# Request/Response Models
class EmailSample(BaseModel):
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=10, max_length=5000)


class InitializeWritingStyleRequest(BaseModel):
    email_samples: List[EmailSample] = Field(..., min_items=3, max_items=20)


class WritingStyleResponse(BaseModel):
    success: bool
    writing_style: Optional[Dict] = None
    message: Optional[str] = None


async def _analyze_and_save(conn, user_email: str, email_samples: list, action: str) -> WritingStyleResponse:
    """Shared logic for initialize and refresh endpoints."""
    employee = await conn.fetchrow(
        "SELECT employee_id FROM employee_info WHERE email = $1", user_email
    )
    if not employee:
        raise HTTPException(status_code=404, detail=f"Employee not found for email: {user_email}")

    employee_id = employee['employee_id']
    samples = [{'subject': s.subject, 'body': s.body} for s in email_samples]

    logger.info(f"{action} writing style with {len(samples)} samples for employee {employee_id}")
    writing_style = await analyze_writing_style_with_ai(samples)

    await conn.execute(
        "UPDATE employee_info SET writing_style = $1 WHERE employee_id = $2",
        writing_style, employee_id
    )

    logger.info(f"Successfully {action.lower()} writing style for employee {employee_id}")
    return WritingStyleResponse(success=True, writing_style=writing_style, message=f"Writing style {action.lower()} successfully")


@router.post("/initialize", response_model=WritingStyleResponse)
async def initialize_writing_style(
    request: InitializeWritingStyleRequest,
    tenant=Depends(get_tenant_connection)
):
    """Initialize writing style for a new employee. Requires 3-20 email samples."""
    conn, user = tenant
    user_email = user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")
    return await _analyze_and_save(conn, user_email, request.email_samples, "Initialized")


@router.get("", response_model=WritingStyleResponse)
async def get_writing_style(
    tenant=Depends(get_tenant_connection)
):
    """Get current writing style for authenticated employee"""
    conn, user = tenant
    user_email = user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    employee = await conn.fetchrow(
        "SELECT employee_id FROM employee_info WHERE email = $1", user_email
    )
    if not employee:
        raise HTTPException(status_code=404, detail=f"Employee not found for email: {user_email}")

    result = await conn.fetchrow(
        "SELECT writing_style FROM employee_info WHERE employee_id = $1", employee['employee_id']
    )

    if not result or not result['writing_style']:
        return WritingStyleResponse(success=True, writing_style=None, message="No writing style set for this employee")

    writing_style = result['writing_style']
    if isinstance(writing_style, str):
        writing_style = json.loads(writing_style)

    return WritingStyleResponse(success=True, writing_style=writing_style)


@router.post("/refresh", response_model=WritingStyleResponse)
async def refresh_writing_style(
    request: InitializeWritingStyleRequest,
    tenant=Depends(get_tenant_connection)
):
    """Manually refresh writing style with new email samples"""
    conn, user = tenant
    user_email = user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")
    return await _analyze_and_save(conn, user_email, request.email_samples, "Refreshed")


