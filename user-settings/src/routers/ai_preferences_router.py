"""
AI Preferences Router
Handles user AI customization preferences from questionnaire
"""

import logging
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any, List

from service_core.db import get_tenant_connection
from data.repositories.ai_preferences_repository import AIPreferencesRepository
from agent.user_preference_agent import get_user_preference_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-preferences")

# Request/Response Models
class TonePreferences(BaseModel):
    formality: Optional[str] = None
    conciseness: Optional[str] = None
    proactiveness: Optional[str] = None
    onBrandPhrases: Optional[str] = None
    avoidPhrases: Optional[str] = None

class GuardrailPreferences(BaseModel):
    topicsToAvoid: Optional[List[str]] = None
    hardRestrictions: Optional[List[str]] = None
    prohibitedStatements: Optional[List[str]] = None

class AudiencePreferences(BaseModel):
    idealCustomers: Optional[str] = None
    roles: Optional[str] = None
    products: Optional[str] = None

class AdditionalContextPreferences(BaseModel):
    additionalContext: Optional[str] = None

class SaveAIPreferencesRequest(BaseModel):
    email: EmailStr
    tone: TonePreferences
    guardrails: GuardrailPreferences
    audience: AudiencePreferences
    additional_context: AdditionalContextPreferences

class AIPreferencesResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None


async def generate_ai_summary(company_profile: dict, hs_codes: list, factory_details: dict, guardrails: dict, additional_context: dict) -> dict:
    """Generate AI summary using GPT via UserPreferenceAgent."""
    try:
        agent = get_user_preference_agent()
        logger.info("Analyzing user preferences with GPT agent")
        ai_summary = agent.analyze_preferences(
            company_profile=company_profile, hs_codes=hs_codes,
            factory_details=factory_details, guardrails=guardrails,
            additional_context=additional_context
        )
        logger.info(f"Generated AI summary via agent with keys: {list(ai_summary.keys())}")
        return ai_summary
    except Exception as e:
        logger.error(f"Error generating AI summary with agent: {e}")
        return {
            "communication_style": "Error occurred during analysis",
            "boundaries_restrictions": "Error occurred during analysis",
            "product_market_focus": "Error occurred during analysis",
            "key_recommendations": "Error occurred during analysis",
            "full_summary": "AI preferences saved. Error occurred during preference analysis."
        }


@router.post("/save", response_model=AIPreferencesResponse)
async def save_ai_preferences(
    request: SaveAIPreferencesRequest,
    tenant=Depends(get_tenant_connection)
):
    """Save user AI preferences from questionnaire."""
    conn, user = tenant
    try:
        logger.info(f"Saving AI preferences for user: {request.email}")

        guardrails_dict = request.guardrails.dict(exclude_none=True)
        additional_context_dict = request.additional_context.dict(exclude_none=True)

        # Fetch company_profile, hs_codes, factory_details from tenant_subscription for AI summary
        existing = await conn.fetchrow(
            "SELECT company_profile, hs_codes, factory_details FROM tenant_subscription LIMIT 1",
        )
        company_profile = (existing['company_profile'] if existing and existing['company_profile'] else {})
        hs_codes = (existing['hs_codes'] if existing and existing['hs_codes'] else [])
        factory_details = (existing['factory_details'] if existing and existing['factory_details'] else {})

        ai_summary = await generate_ai_summary(
            company_profile, hs_codes, factory_details, guardrails_dict, additional_context_dict
        )

        result = await AIPreferencesRepository.save_preferences(
            conn,
            email=request.email,
            tone_dict=request.tone.dict(exclude_none=True) if hasattr(request, 'tone') and request.tone else {},
            guardrails_dict=guardrails_dict,
            audience_dict=request.audience.dict(exclude_none=True) if hasattr(request, 'audience') and request.audience else {},
            additional_context_dict=additional_context_dict,
            ai_summary=ai_summary
        )

        return AIPreferencesResponse(
            success=True,
            message="AI preferences saved successfully",
            preferences=result["preferences"]
        )
    except Exception as e:
        logger.error(f"Error saving AI preferences: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save AI preferences: {str(e)}"
        )


@router.get("/get/{email}", response_model=AIPreferencesResponse)
async def get_ai_preferences(
    email: str,
    tenant=Depends(get_tenant_connection)
):
    """Get user AI preferences by email."""
    conn, user = tenant
    try:
        logger.info(f"Fetching AI preferences for user: {email}")

        preferences = await AIPreferencesRepository.get_preferences(conn, email)

        if not preferences:
            return AIPreferencesResponse(
                success=True, message="No preferences found for this user", preferences=None
            )

        if preferences and preferences.get("guardrails"):
            guardrails = preferences["guardrails"]
            if isinstance(guardrails, str):
                import json as _json
                try:
                    guardrails = _json.loads(guardrails)
                except Exception:
                    guardrails = {}
            # Rename old keys → new keys
            key_map = {"guardrailTopics": "topicsToAvoid", "avoidTopics": "hardRestrictions", "otherClaims": "prohibitedStatements"}
            for old_key, new_key in key_map.items():
                if old_key in guardrails:
                    val = guardrails.pop(old_key)
                    if isinstance(val, str) and val:
                        guardrails[new_key] = [f"custom:{val}"]
                    elif isinstance(val, list):
                        guardrails[new_key] = val
            # Ensure remaining new keys with string values are arrays
            for key in ["topicsToAvoid", "hardRestrictions", "prohibitedStatements"]:
                if key in guardrails and isinstance(guardrails[key], str):
                    guardrails[key] = [f"custom:{guardrails[key]}"] if guardrails[key] else []
            preferences["guardrails"] = guardrails

        return AIPreferencesResponse(
            success=True, message="AI preferences retrieved successfully", preferences=preferences
        )
    except Exception as e:
        logger.error(f"Error fetching AI preferences: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch AI preferences: {str(e)}"
        )


@router.delete("/delete/{email}")
async def delete_ai_preferences(
    email: str,
    tenant=Depends(get_tenant_connection)
):
    """Delete user AI preferences by email."""
    conn, user = tenant
    try:
        logger.info(f"Deleting AI preferences for user: {email}")

        deleted = await AIPreferencesRepository.delete_preferences(conn, email)

        if deleted:
            return {"success": True, "message": f"AI preferences deleted for {email}"}
        else:
            return {"success": False, "message": f"No preferences found for {email}"}
    except Exception as e:
        logger.error(f"Error deleting AI preferences: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete AI preferences: {str(e)}"
        )
