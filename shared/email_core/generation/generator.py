"""AI email generator using Anthropic Claude.

Shared wrapper for CRM and Leadgen. Persona is passed per-call by each
service's prompt builder based on email_type.

Uses Anthropic SDK's messages.parse() with Pydantic models for structured
output — schema is derived automatically, response is validated on return.
"""

import logging
import traceback
from typing import Dict, Optional

from anthropic import APIError, APIStatusError, AsyncAnthropic
from fastapi import HTTPException

from email_core.config import settings
from email_core.models import EmailOutput

logger = logging.getLogger(__name__)

# Lazy singleton — avoids creating a new HTTP connection pool per generation call
_generator_client: Optional[AsyncAnthropic] = None


def _get_generator_client() -> AsyncAnthropic:
    global _generator_client
    if _generator_client is None:
        _generator_client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=60.0)
    return _generator_client


DEFAULT_PERSONA = (
    "You are an expert professional writing personalized emails."
)

GENERATION_MODEL = "claude-sonnet-4-6"


async def generate_email_with_ai(
    prompt: str,
    persona: Optional[str] = None,
) -> Dict:
    """Generate email using Anthropic Claude API with structured output.

    Args:
        prompt: Complete prompt for email generation.
        persona: System prompt persona. Each service passes this based on
                 email_type — e.g. "expert customer success manager" (CRM),
                 "expert sales development representative" (Leadgen),
                 or "international trade advisor" (trade types).

    Returns:
        Dict with status, classification, and email_data (subject, body, generated_by).
    """
    api_key = settings.anthropic_api_key
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Anthropic API key not configured. Set ANTHROPIC_API_KEY environment variable."
        )

    system_content = persona or DEFAULT_PERSONA

    try:
        logger.info(f"Generating email with model: {GENERATION_MODEL} (structured output)")

        client = _get_generator_client()
        response = await client.messages.parse(
            model=GENERATION_MODEL,
            max_tokens=2000,
            system=system_content,
            messages=[{"role": "user", "content": prompt}],
            output_format=EmailOutput,
        )

        # Check stop reason before using parsed output
        if response.stop_reason == "refusal":
            logger.error("Anthropic refused to generate email")
            raise HTTPException(status_code=422, detail="Email generation was refused by the model")
        if response.stop_reason == "max_tokens":
            logger.warning("Anthropic response truncated (max_tokens)")

        parsed: EmailOutput = response.parsed_output
        if parsed is None:
            raise HTTPException(status_code=502, detail="Empty response from email generation service")

        logger.info(
            f"AI response received, stop_reason: {response.stop_reason}, "
            f"intent: {parsed.classification.intent}"
        )

        # Guard: actionable intents must have subject and body
        no_content_intents = {"ooo", "bounce"}
        if parsed.classification.intent not in no_content_intents and (not parsed.subject or not parsed.body):
            logger.error(f"Blank draft for actionable intent: {parsed.classification.intent}")
            raise HTTPException(status_code=502, detail="Email generation returned empty content")

        subject = parsed.subject or ""
        body = parsed.body or ""

        # Minimal cleanup (structured output removes most issues)
        subject = subject.replace('"', '').replace('*', '').strip()

        logger.info(
            f"Email generated successfully - Intent: {parsed.classification.intent}, "
            f"Subject: {subject[:50]}..."
        )

        return {
            "status": "success",
            "classification": parsed.classification.model_dump(),
            "email_data": {
                "subject": subject,
                "body": body,
                "generated_by": GENERATION_MODEL,
                "formatted": True
            }
        }

    except HTTPException:
        raise
    except APIStatusError as e:
        logger.error(f"Anthropic API error: {e.status_code} - {e.message}")
        raise HTTPException(
            status_code=502,
            detail=f"Email generation service error: {e.status_code}"
        )
    except APIError as e:
        logger.error(f"Anthropic API error: {e.message}")
        raise HTTPException(
            status_code=502,
            detail=f"Email generation service error: {e.message}"
        )
    except Exception as e:
        logger.error(f"Error generating email with AI: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate email: {str(e)}"
        )
