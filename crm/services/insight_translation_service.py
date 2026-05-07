"""
Insight Translation Service — translates English summary_data to Chinese (zh-CN).

Uses OpenAI to translate the user-facing text fields (recent_activities, next_steps)
while preserving the JSON structure. The translation is stored alongside the English
original so we can serve the correct version based on locale.
"""

import json
import hashlib
import logging
import openai
import os
from typing import Dict, Any, Optional

from service_core.llm_json import extract_json

logger = logging.getLogger(__name__)


def _get_source_hash(summary_data: dict) -> str:
    """Deterministic hash of the English summary_data to detect staleness."""
    canonical = json.dumps(summary_data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def translate_summary_data(summary_data: dict) -> Optional[dict]:
    """
    Translate English summary_data to Chinese (zh-CN).

    Only translates the user-facing text fields:
      - recent_activities (list of insight strings)
      - next_steps (list of action strings)
      - summary (one-line description)

    Returns a new dict with the same structure but Chinese text,
    or None if translation fails.
    """
    recent_activities = summary_data.get("recent_activities", [])
    next_steps = summary_data.get("next_steps", [])
    summary_text = summary_data.get("summary", "")

    # Nothing to translate
    if not recent_activities and not next_steps and not summary_text:
        return None

    # Build a compact payload for the LLM
    payload = {
        "summary": summary_text,
        "recent_activities": recent_activities,
        "next_steps": next_steps,
    }

    prompt = f"""Translate the following JSON values from English to Simplified Chinese (zh-CN).
Keep the JSON keys exactly the same. Only translate the string values.
Preserve any names, dollar amounts, dates, and percentages as-is (do not translate proper nouns or numbers).
Return ONLY valid JSON — no markdown, no extra text.

{json.dumps(payload, ensure_ascii=False, indent=2)}"""

    system_message = (
        "You are a professional English-to-Simplified-Chinese translator "
        "specializing in business and CRM content. "
        "Return only the translated JSON object."
    )

    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set — skipping zh translation")
            return None

        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=2500,
        )

        raw = response.choices[0].message.content.strip()
        translated = extract_json(raw)
        if not isinstance(translated, dict):
            logger.error("Failed to parse zh translation JSON")
            return None

        # Merge translated fields back into a copy of the original structure
        result = dict(summary_data)
        result["summary"] = translated.get("summary", summary_text)
        result["recent_activities"] = translated.get("recent_activities", recent_activities)
        result["next_steps"] = translated.get("next_steps", next_steps)
        return result

    except Exception as e:
        logger.error(f"zh translation failed: {e}")
        return None
