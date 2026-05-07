"""Translation endpoint for email content (user-facing, latency-sensitive).

Mirrors the CRM translation router interface so the leadgen frontend
can call its own service instead of proxying through CRM.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from service_core.auth import verify_auth_token
from email_core.translation import translate_email_batch

logger = logging.getLogger(__name__)

router = APIRouter()


class TranslateRequest(BaseModel):
    subject: str = Field(..., max_length=500)
    body: str = Field(..., max_length=50000)


@router.post("/translate")
async def translate_email(
    request: TranslateRequest,
    user: dict = Depends(verify_auth_token),
):
    try:
        result = await translate_email_batch(request.subject, request.body)
        subject_zh = result.get("subject", "")
        body_zh = result.get("body", "")
        if not subject_zh and not body_zh:
            raise HTTPException(status_code=502, detail="Translation returned empty content")
        return {"subject_zh": subject_zh, "body_zh": body_zh}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        raise HTTPException(status_code=502, detail="Translation service unavailable")
