"""Translation service for AI-generated content.

Uses gpt-5.4-nano for all translation (both background and interactive).
OpenAI is cheaper than Haiku for translation, so we keep it on OpenAI.

English is always the source of truth. Chinese translation is a convenience layer.
"""

import json
import logging
from typing import Optional
from openai import AsyncOpenAI

from email_core.config import settings

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=settings.openai_api_key)

BACKGROUND_MODEL = settings.translation_background_model
INTERACTIVE_MODEL = settings.translation_interactive_model

SYSTEM_PROMPT = (
    "You are a professional business translator. "
    "Translate the following English text to Simplified Chinese. "
    "Preserve proper nouns, company names, product names, email addresses, "
    "and technical terms in English. "
    "Preserve all numerical values, currencies, and units exactly as written. "
    "Maintain the original tone, formatting, and paragraph structure. "
    "Return only the translation, no explanations."
)

CULTURAL_ADAPTATION_PROMPT = (
    "You are a professional B2B communication specialist for international trade. "
    "Translate the following Chinese text into polished Western B2B English. "
    "The writer is a Chinese manufacturer communicating with a Western buyer (US/EU). "
    "Adapt the tone to be professional, quantified, and culturally appropriate for Western business: "
    "- Remove overly casual greetings like 'Dear Friend' or excessive politeness markers "
    "- Use direct, confident language without being aggressive "
    "- Preserve all numerical values, product specifications, and company names "
    "- Maintain paragraph structure but improve clarity "
    "- The result should read as if written by a native English-speaking sales professional "
    "Return only the adapted English text, no explanations."
)


async def translate_to_chinese(text: str, model: str = BACKGROUND_MODEL) -> str:
    """Translate English text to Simplified Chinese.

    Args:
        text: English text to translate.
        model: Which model to use. Use INTERACTIVE_MODEL for user-facing calls.
    """
    if not text or not text.strip():
        return text
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Translation failed for text ({len(text)} chars): {e}")
        return None


ENGLISH_SYSTEM_PROMPT = (
    "You are a professional business translator. "
    "Translate the following Chinese text to English. "
    "Preserve proper nouns, company names, product names, email addresses, "
    "and technical terms. "
    "Preserve all numerical values, currencies, and units exactly as written. "
    "Maintain the original tone, formatting, and paragraph structure. "
    "Return only the translation, no explanations."
)


async def translate_to_english(text: str, model: str = BACKGROUND_MODEL) -> Optional[str]:
    """Translate Chinese text to English.

    Args:
        text: Chinese text to translate.
        model: Which model to use. Use INTERACTIVE_MODEL for user-facing calls.
    """
    if not text or not text.strip():
        return text
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": ENGLISH_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Translation to English failed for text ({len(text)} chars): {e}")
        return None


async def translate_json_values(data: dict) -> dict | None:
    """Translate all string values in a JSON object, preserving keys.

    Uses BACKGROUND_MODEL — individual calls per string.
    Only used in background jobs (scheduler, insight agents).
    Returns None if any translation fails so the caller can store NULL.
    """
    translated = {}
    for key, value in data.items():
        if isinstance(value, str) and value.strip():
            result = await translate_to_chinese(value)
            if result is None:
                return None
            translated[key] = result
        elif isinstance(value, dict):
            result = await translate_json_values(value)
            if result is None:
                return None
            translated[key] = result
        elif isinstance(value, list):
            items = []
            for item in value:
                if isinstance(item, str):
                    result = await translate_to_chinese(item)
                    if result is None:
                        return None
                    items.append(result)
                else:
                    items.append(item)
            translated[key] = items
        else:
            translated[key] = value
    return translated


async def adapt_to_western_b2b(text: str, model: str = INTERACTIVE_MODEL) -> str:
    """Culturally adapt Chinese text to polished Western B2B English.

    Used for deal room custom messages — manufacturer writes in Chinese,
    the deal room displays professionally adapted English.

    Args:
        text: Chinese text from the manufacturer.
        model: Which model to use. Defaults to INTERACTIVE_MODEL for real-time UI.
    """
    if not text or not text.strip():
        return text
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": CULTURAL_ADAPTATION_PROMPT},
                {"role": "user", "content": text},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Cultural adaptation failed for text ({len(text)} chars): {e}")
        return None


async def translate_email_batch(subject: str, body: str) -> dict:
    """Translate email subject + body in a single batch call.

    Uses INTERACTIVE_MODEL — single batch call for user-facing preview.
    Used in the email composer for bilingual toggle.
    """
    batch_prompt = (
        "Translate each numbered item below to Simplified Chinese. "
        "Preserve all numerical values, currencies, and units exactly as written. "
        'Return a JSON object with keys "subject" and "body".\n\n'
        f"1. Subject: {subject}\n\n"
        f"2. Body: {body}"
    )
    try:
        response = await client.chat.completions.create(
            model=INTERACTIVE_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": batch_prompt},
            ],
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content.strip())
    except json.JSONDecodeError as e:
        logger.warning(f"Batch translation parse failed, falling back to individual calls: {e}")
        subject_zh = await translate_to_chinese(subject, model=INTERACTIVE_MODEL)
        body_zh = await translate_to_chinese(body, model=INTERACTIVE_MODEL)
        if subject_zh is None or body_zh is None:
            return {}
        return {"subject": subject_zh, "body": body_zh}
