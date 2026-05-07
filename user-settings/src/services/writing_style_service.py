"""
Writing Style Service - Stateless version (no sample storage)
Updates writing style immediately when emails are sent.

Delegates to the shared Haiku 4.5 analyzer in email_core.writing_style.
"""

import json
import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def analyze_writing_style_with_ai(emails: List[Dict[str, str]]) -> Dict:
    """
    Analyze writing style using Anthropic Haiku 4.5.

    Args:
        emails: List of dicts with 'subject' and 'body' keys

    Returns:
        Writing style analysis dict with metadata
    """
    from email_core.writing_style import analyze_writing_style
    from email_core.config import settings

    style_data = await analyze_writing_style(emails)

    style_data['metadata'] = {
        'lastUpdated': datetime.now(timezone.utc).isoformat(),
        'emailsSampled': len(emails),
        'model': settings.writing_style_model,
    }

    logger.info(f"Successfully analyzed writing style from {len(emails)} emails")
    return style_data


def format_writing_style_for_prompt(writing_style: Optional[Dict]) -> str:
    """
    Format writing style dict into prompt text

    Args:
        writing_style: Writing style dict or None

    Returns:
        Formatted string to inject into email generation prompt
    """
    if not writing_style:
        return ""

    try:
        traits_list = "\n".join(f"- {trait}" for trait in writing_style.get('notableTraits', []))
        examples_list = "\n".join(f'- "{ex}"' for ex in writing_style.get('examples', []))

        return f"""
<writing_style>
Typical Length: {writing_style.get('typicalLength', 'N/A')}
Formality: {writing_style.get('formality', 'N/A')}
Common Greeting: {writing_style.get('commonGreeting', 'N/A')}

Notable Traits:
{traits_list}

Example Phrases from Past Emails:
{examples_list}
</writing_style>

CRITICAL INSTRUCTION: Match the user's writing style EXACTLY. Use their:
- Typical email length and structure
- Level of formality
- Greeting style (or lack thereof)
- Notable traits (contractions, punctuation, brevity, etc.)
- Tone and phrasing from the examples above

Generate an email that sounds like the user wrote it, not a generic AI assistant.
"""
    except Exception as e:
        logger.error(f"Error formatting writing style for prompt: {e}")
        return ""


async def fetch_writing_style_by_email(user_email: str) -> Optional[Dict]:
    """
    Fetch writing style for a user by their email address.
    Uses TenantPoolManager to route to the user's tenant database.
    """
    try:
        from service_core.db import get_pool_manager

        pm = get_pool_manager()
        db_name = await pm.lookup_db_name(user_email)

        async with pm.acquire(db_name) as conn:
            result = await conn.fetchrow(
                "SELECT employee_id, writing_style FROM employee_info WHERE email = $1",
                user_email
            )

            if not result:
                logger.info(f"No employee found for email {user_email}")
                return None

            writing_style = result['writing_style']
            if not writing_style:
                logger.info(f"No writing style found for {user_email}")
                return None

            if isinstance(writing_style, str):
                writing_style = json.loads(writing_style)

            logger.info(f"Fetched writing style for {user_email}")
            return writing_style

    except Exception as e:
        logger.warning(f"Failed to fetch writing style for {user_email}: {e}")
        return None
