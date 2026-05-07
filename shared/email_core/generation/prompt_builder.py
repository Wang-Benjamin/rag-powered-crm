"""Shared strictness bands and prompt scaffold for template-based email generation.

The strictness mapping + template/output shell are identical between CRM and leadgen.
Recipient data blocks differ (CRM: company/contact/email; leadgen: company/location/website/phone)
and stay in each service's local prompt_builder.
"""


# Strictness level → instruction text
STRICTNESS_BANDS = {
    'strict': (
        "STRICT MODE: Follow the template EXACTLY. Only replace placeholder tokens with actual values.\n"
        "Do not change any wording, structure, or tone. The output should be nearly identical to the template."
    ),
    'mostly_strict': (
        "MOSTLY STRICT MODE: Follow the template closely. Minor phrasing adjustments are allowed.\n"
        "Keep the same structure, key phrases, and overall message. Small variations in word choice are acceptable."
    ),
    'balanced': (
        "BALANCED MODE: Use the template as a strong guide. Keep the same structure and intent.\n"
        "You may adapt tone, phrasing, and specific wording while maintaining the core message and flow."
    ),
    'creative': (
        "CREATIVE MODE: Use the template as inspiration. You have significant freedom to adapt.\n"
        "Maintain the general purpose and key points, but feel free to restructure and rephrase substantially."
    ),
}

OUTPUT_FORMAT_BLOCK = """
OUTPUT FORMAT:
Return a JSON object with "subject" and "body" keys only.
{
  "subject": "...",
  "body": "..."
}

Output JSON only. No markdown formatting."""


def get_strictness_instruction(strictness_level: int) -> str:
    """Map a 0-100 strictness level to the corresponding instruction text."""
    if strictness_level <= 10:
        return STRICTNESS_BANDS['strict']
    elif strictness_level <= 40:
        return STRICTNESS_BANDS['mostly_strict']
    elif strictness_level <= 70:
        return STRICTNESS_BANDS['balanced']
    else:
        return STRICTNESS_BANDS['creative']


def build_strictness_scaffold(
    template: dict,
    strictness_level: int,
    custom_context: str = None,
) -> str:
    """Build the shared portion of a strictness prompt (no recipient data).

    Returns the prompt with:
    - Strictness instruction
    - Template subject/body
    - Template prompt_instructions (if any)
    - Custom context (if any)
    - Output format block

    Callers append their own recipient data section before the output format
    by inserting it into the returned string (before OUTPUT_FORMAT_BLOCK).
    """
    instruction = get_strictness_instruction(strictness_level)

    prompt = f"""{instruction}

TEMPLATE TO FOLLOW:
Subject: {template.get('subject', '')}
Body:
{template.get('body', '')}
"""

    if template.get('prompt_instructions'):
        prompt += f"""
TEMPLATE INSTRUCTIONS:
{template['prompt_instructions']}
"""

    # Placeholder for caller to insert recipient data here
    # (CRM adds RECIPIENT DATA, leadgen adds LEAD DATA)

    if custom_context and custom_context.strip():
        prompt += f"""
ADDITIONAL CONTEXT:
{custom_context.strip()}
"""

    prompt += OUTPUT_FORMAT_BLOCK

    return prompt
