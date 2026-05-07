"""Writing style analyzer using Haiku 4.5.

Analyzes sent emails to build a personalized writing style profile.
Uses Anthropic SDK's messages.parse() with Pydantic structured output,
matching the pattern in triage/classifier.py.

Replaces the previous GPT-5-mini / GPT-4.1-mini OpenAI implementations
in CRM fetchers.py and user-settings writing_style_service.py.
"""

import logging
from typing import Dict, List, Optional

from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field

from email_core.config import settings

logger = logging.getLogger(__name__)

_style_client: Optional[AsyncAnthropic] = None


def _get_style_client() -> AsyncAnthropic:
    global _style_client
    if _style_client is None:
        _style_client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=45.0)
    return _style_client


class WritingStyleAnalysis(BaseModel):
    """Structured output for writing style analysis.

    Field names are camelCase to match the existing DB schema
    stored in employee_info.writing_style JSONB.
    """
    typicalLength: str = Field(description="Average email length, e.g. '2-3 sentences' or '1-2 paragraphs'")
    formality: str = Field(description="Formality level, e.g. 'Informal with professional undertones'")
    commonGreeting: str = Field(description="Standard opening pattern, e.g. 'Hi,' or 'No greeting - starts directly'")
    notableTraits: List[str] = Field(description="3-5 distinctive characteristics of the writing style")
    examples: List[str] = Field(description="2-3 representative sentences or phrases from the emails")


STYLE_SYSTEM_PROMPT = (
    "You are a writing style analyst specializing in email communication patterns.\n\n"
    "Analyze the user's writing style based on their sent emails. Identify patterns in their "
    "communication style and create a personalized style guide."
)


async def analyze_writing_style(emails: List[Dict[str, str]]) -> Dict:
    """Analyze writing style from sent emails using Haiku 4.5.

    Args:
        emails: List of dicts with 'subject' and 'body' keys.

    Returns:
        Writing style dict matching the existing DB schema
        (typicalLength, formality, commonGreeting, notableTraits, examples).

    Raises:
        Exception: If API call fails or response cannot be parsed.
    """
    email_list = []
    for email in emails:
        subject = email.get("subject", "No subject")
        body = email.get("body", "")
        if len(body) > 1000:
            body = body[:1000] + "..."
        email_list.append(
            f"<email>\n  <subject>{subject}</subject>\n  <body>{body}</body>\n</email>"
        )

    emails_xml = "\n".join(email_list)

    user_prompt = (
        f"Analyze the writing style from these emails:\n\n"
        f"<emails>\n{emails_xml}\n</emails>\n\n"
        f"Identify typical length, formality, greeting style, notable traits, "
        f"and extract 2-3 representative example phrases."
    )

    client = _get_style_client()
    response = await client.messages.parse(
        model=settings.writing_style_model,
        system=STYLE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        max_tokens=1000,
        output_format=WritingStyleAnalysis,
    )

    if not response.parsed_output:
        raise ValueError(f"Writing style analysis returned no output (stop_reason={response.stop_reason})")

    return response.parsed_output.model_dump()
