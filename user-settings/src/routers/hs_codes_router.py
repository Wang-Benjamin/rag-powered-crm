"""
HS Codes Router
===============
Suggests HS codes from product descriptions via LLM,
and persists confirmed codes to user_preferences.
"""

import os
import json
import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from openai import OpenAI

from service_core.db import get_tenant_connection
from service_core.auth import verify_auth_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hs-codes")

_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
        _client = OpenAI(api_key=api_key)
    return _client


# --- Models ---

class HsCodeItem(BaseModel):
    code: str
    description: str
    confidence: Optional[float] = None

class SuggestRequest(BaseModel):
    product_description: str

class SuggestResponse(BaseModel):
    success: bool
    hs_codes: List[HsCodeItem]

class ConfirmRequest(BaseModel):
    hs_codes: List[HsCodeItem]

class ConfirmResponse(BaseModel):
    success: bool
    hs_codes: List[HsCodeItem]


# --- Endpoints ---

@router.get("", response_model=SuggestResponse)
async def get_hs_codes(tenant=Depends(get_tenant_connection)):
    """Return the company's saved HS codes from tenant_subscription."""
    conn, user = tenant
    user_email = user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    row = await conn.fetchrow(
        "SELECT hs_codes FROM tenant_subscription LIMIT 1",
    )
    if not row or not row.get('hs_codes'):
        return SuggestResponse(success=True, hs_codes=[])

    codes = row['hs_codes']
    if isinstance(codes, str):
        codes = json.loads(codes)

    return SuggestResponse(
        success=True,
        hs_codes=[HsCodeItem(code=c.get('code', ''), description=c.get('description', ''), confidence=c.get('confidence')) for c in codes],
    )


@router.post("/suggest", response_model=SuggestResponse)
async def suggest_hs_codes(
    request: SuggestRequest,
    _user: dict = Depends(verify_auth_token)
):
    """Suggest HS codes from a product description using LLM."""
    if not request.product_description.strip():
        raise HTTPException(status_code=400, detail="Product description is required")

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="gpt-5.4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a trade classification expert. Given a product description, "
                        "return the most likely Harmonized System (HS) codes at the 6-digit level. "
                        "Return 2-5 codes ranked by relevance. For each code provide:\n"
                        "- code: the HS code (e.g. '9405.42')\n"
                        "- description: what this code covers\n"
                        "- confidence: 0-100 indicating how likely this code applies\n\n"
                        "Respond with ONLY a JSON array, no markdown, no explanation:\n"
                        '[{"code":"9405.42","description":"LED lamps and lighting fittings","confidence":92}]'
                    )
                },
                {
                    "role": "user",
                    "content": f"Product description: {request.product_description}"
                }
            ],
            max_completion_tokens=500,
        )

        raw = response.choices[0].message.content.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            raw = raw.rsplit("```", 1)[0].strip()

        codes = json.loads(raw)
        hs_codes = [
            HsCodeItem(
                code=str(c.get("code", "")),
                description=str(c.get("description", "")),
                confidence=float(c.get("confidence", 50))
            )
            for c in codes
            if c.get("code")
        ]

        return SuggestResponse(success=True, hs_codes=hs_codes)

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response for HS codes: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse HS code suggestions")
    except Exception as e:
        logger.error(f"Error suggesting HS codes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to suggest HS codes: {str(e)}")


@router.post("/confirm", response_model=ConfirmResponse)
async def confirm_hs_codes(
    request: ConfirmRequest,
    tenant=Depends(get_tenant_connection)
):
    """Persist confirmed HS codes to user_preferences.hs_codes."""
    conn, user = tenant
    user_email = user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        codes = [
            {"code": c.code, "description": c.description, "confidence": c.confidence, "confirmed": True}
            for c in request.hs_codes
        ]

        # Bootstrap row if missing, then update
        await conn.execute(
            "INSERT INTO tenant_subscription (id) VALUES (TRUE) ON CONFLICT DO NOTHING"
        )
        await conn.execute(
            "UPDATE tenant_subscription SET hs_codes = $1::jsonb, updated_at = NOW()",
            codes,
        )

        return ConfirmResponse(success=True, hs_codes=request.hs_codes)

    except Exception as e:
        logger.error(f"Error confirming HS codes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to confirm HS codes: {str(e)}")
