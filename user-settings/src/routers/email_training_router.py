"""
Email Training Router
=====================
Handles email personality training for AI-powered email generation.
Stores user email samples in employee_info.training_emails JSONB column.
Also analyzes and updates writing style based on training emails.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import logging
import json

from services.writing_style_service import analyze_writing_style_with_ai

from service_core.db import get_tenant_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/email-training")

class EmailTrainingRequest(BaseModel):
    subject1: str = Field(..., min_length=1, description="First email subject")
    body1: str = Field(..., min_length=1, description="First email body")
    subject2: str = Field(..., min_length=1, description="Second email subject")
    body2: str = Field(..., min_length=1, description="Second email body")
    subject3: str = Field(..., min_length=1, description="Third email subject")
    body3: str = Field(..., min_length=1, description="Third email body")

class EmailTrainingResponse(BaseModel):
    user_email: str
    subject1: str
    body1: str
    subject2: str
    body2: str
    subject3: str
    body3: str
    created_at: datetime
    updated_at: datetime

class SuccessResponse(BaseModel):
    success: bool
    message: str


@router.post("", response_model=EmailTrainingResponse)
async def save_email_training(
    request: EmailTrainingRequest,
    tenant=Depends(get_tenant_connection)
):
    """Save email samples to employee_info.training_emails JSONB column and analyze writing style."""
    conn, user = tenant
    user_email = user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    training_data = [
        {"subject": request.subject1, "body": request.body1},
        {"subject": request.subject2, "body": request.body2},
        {"subject": request.subject3, "body": request.body3}
    ]

    result = await conn.fetchrow(
        """
        UPDATE employee_info
        SET training_emails = $1, updated_at = CURRENT_TIMESTAMP
        WHERE email = $2
        RETURNING email, training_emails, created_at, updated_at, employee_id
        """,
        training_data, user_email
    )

    if not result:
        raise HTTPException(status_code=404, detail="Employee not found")

    emails = result['training_emails'] if result['training_emails'] else []
    if isinstance(emails, str):
        emails = json.loads(emails)
    employee_id = result['employee_id']

    # Analyze and update writing style based on training emails
    try:
        logger.info(f"Analyzing writing style for {user_email} from training emails")
        writing_style = await analyze_writing_style_with_ai(training_data)

        await conn.execute(
            "UPDATE employee_info SET writing_style = $1 WHERE employee_id = $2",
            writing_style, employee_id
        )
        logger.info(f"Writing style updated for {user_email}")
    except Exception as style_error:
        logger.error(f"Failed to update writing style for {user_email}: {style_error}")

    return EmailTrainingResponse(
        user_email=result['email'],
        subject1=emails[0]['subject'] if len(emails) > 0 else "",
        body1=emails[0]['body'] if len(emails) > 0 else "",
        subject2=emails[1]['subject'] if len(emails) > 1 else "",
        body2=emails[1]['body'] if len(emails) > 1 else "",
        subject3=emails[2]['subject'] if len(emails) > 2 else "",
        body3=emails[2]['body'] if len(emails) > 2 else "",
        created_at=result['created_at'],
        updated_at=result['updated_at']
    )


@router.get("", response_model=EmailTrainingResponse)
async def get_email_training(
    tenant=Depends(get_tenant_connection)
):
    """Get email training data from employee_info.training_emails."""
    conn, user = tenant
    user_email = user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    result = await conn.fetchrow(
        "SELECT email, training_emails, created_at, updated_at FROM employee_info WHERE email = $1",
        user_email
    )

    if result and result['training_emails']:
        emails = result['training_emails']
        if isinstance(emails, str):
            emails = json.loads(emails)
        return EmailTrainingResponse(
            user_email=result['email'],
            subject1=emails[0]['subject'] if len(emails) > 0 else "",
            body1=emails[0]['body'] if len(emails) > 0 else "",
            subject2=emails[1]['subject'] if len(emails) > 1 else "",
            body2=emails[1]['body'] if len(emails) > 1 else "",
            subject3=emails[2]['subject'] if len(emails) > 2 else "",
            body3=emails[2]['body'] if len(emails) > 2 else "",
            created_at=result['created_at'],
            updated_at=result['updated_at']
        )
    else:
        return EmailTrainingResponse(
            user_email=user_email,
            subject1="", body1="",
            subject2="", body2="",
            subject3="", body3="",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )


@router.delete("/", response_model=SuccessResponse)
async def delete_email_training(
    tenant=Depends(get_tenant_connection)
):
    """Clear training_emails from employee_info."""
    conn, user = tenant
    user_email = user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    await conn.execute(
        "UPDATE employee_info SET training_emails = '[]'::jsonb WHERE email = $1",
        user_email
    )

    return SuccessResponse(success=True, message="Email training deleted successfully")
