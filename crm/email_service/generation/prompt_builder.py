"""Prompt builder for agentic email generation - CRM.

The AI determines email intent from data signals (interaction history, customer
health metrics, deal stage). No email_type parameter needed.
"""

import logging
from typing import List, Optional
from datetime import datetime, timezone

from email_core.models import INTENT_INSTRUCTIONS
from email_core.generation.trade_utils import (
    build_trade_context,
    needs_cultural_adaptation,
    CULTURAL_ADAPTATION_PROMPT,
    BUYER_INTELLIGENCE_RULES,
)
from email_core.generation.trade_voice import TRADE_VOICE_PRESET
from email_core.generation.prompt_utils import (
    build_situational_context,
    build_buyer_signals,
    build_writing_style_instructions,
    format_thread_summary,
)

logger = logging.getLogger(__name__)


def build_strictness_prompt(
    template: dict,
    strictness_level: int,
    custom_context: str = None,
    recipient_data: dict = None
) -> str:
    """Build a prompt that controls how closely AI follows a template.

    Kept for template mode (mass email with strictness slider).
    """
    if strictness_level <= 10:
        instruction = "STRICT MODE: Follow the template EXACTLY. Only replace placeholders."
    elif strictness_level <= 40:
        instruction = "MOSTLY STRICT: Follow closely. Minor phrasing adjustments allowed."
    elif strictness_level <= 70:
        instruction = "BALANCED: Use as guide. Adapt tone/phrasing, keep core message."
    else:
        instruction = "CREATIVE: Use as inspiration. Keep purpose/key points, rephrase freely."

    prompt = f"""{instruction}

TEMPLATE:
Subject: {template.get('subject', '')}
Body:
{template.get('body', '')}
"""

    if template.get('prompt_instructions'):
        prompt += f"\nTEMPLATE INSTRUCTIONS:\n{template['prompt_instructions']}\n"

    if recipient_data:
        prompt += f"""
RECIPIENT DATA:
- Company: {recipient_data.get('name', recipient_data.get('company', 'Unknown'))}
- Contact: {recipient_data.get('primary_contact', recipient_data.get('contact', 'Unknown'))}
- Email: {recipient_data.get('email', '')}
"""

    if custom_context and custom_context.strip():
        prompt += f"\nADDITIONAL CONTEXT:\n{custom_context.strip()}\n"

    return prompt


def format_customer_data(customer_data) -> str:
    """Format customer data for prompt."""
    if not isinstance(customer_data, dict):
        return str(customer_data) if customer_data else "No customer data available."
    return f"""Company: {customer_data.get('company', 'Unknown')}
Primary Contact: {customer_data.get('primary_contact', 'Unknown')}
Email: {customer_data.get('email', '')}
Location: {customer_data.get('location', 'Unknown')}
Status: {customer_data.get('status', 'active')}
Total Deal Value: ${customer_data.get('total_deal_value', 0):,.2f}
Health Score: {customer_data.get('health_score', 75)}/100
Recent Notes: {customer_data.get('recent_notes', 'No notes')}"""


def format_insights(insights: Optional[dict]) -> str:
    """Format customer insights for prompt."""
    if not insights:
        return "No insights available."

    summary_data = insights.get('summary_data', {})
    if isinstance(summary_data, str):
        summary_text = summary_data
    else:
        summary_text = str(summary_data)

    return f"""Summary: {summary_text}
Period: Last {insights.get('period_analyzed_days', 'N/A')} days
Interactions Analyzed: {insights.get('interactions_analyzed', 0)}"""


def format_notes(notes: List[dict]) -> str:
    """Format employee notes for prompt."""
    if not notes:
        return "No notes available."

    formatted_notes = []
    for note in notes:
        date = note.get('created_at', 'Unknown date')
        if hasattr(date, 'strftime'):
            date = date.strftime("%Y-%m-%d")
        title = note.get('title', 'No title')
        body = note.get('body', '')
        star = note.get('star', 0)
        formatted_notes.append(f"[{date}] {title} - {body} [Star: {star}]")

    return "\n".join(formatted_notes)


def format_past_interactions(interactions: List[dict]) -> str:
    """Format past interactions for prompt."""
    if not interactions:
        return "No previous interactions found."

    formatted_interactions = []
    for interaction in interactions:
        date = interaction.get('created_at', 'Unknown date')
        if hasattr(date, 'strftime'):
            date = date.strftime("%Y-%m-%d")
        type_ = interaction.get('type', 'unknown').upper()
        content = interaction.get('content', '')
        theme = interaction.get('theme', '')
        theme_str = f" [Theme: {theme}]" if theme else ""
        formatted_interactions.append(f"[{date}] {type_}: {content}{theme_str}")

    return "\n".join(formatted_interactions)


def format_email_samples(samples: list) -> str:
    """Format email samples for prompt."""
    if not samples:
        return ""

    formatted_samples = []
    for i, sample in enumerate(samples, 1):
        if isinstance(sample, str):
            formatted_samples.append(f"Sample {i}:\n{sample}")
        elif isinstance(sample, dict):
            formatted_samples.append(f"""Sample {i}:
Subject: {sample.get('subject', '')}
Body: {sample.get('body', '')}""")

    return "\n\n".join(formatted_samples)


def build_crm_email_prompt(
    customer_data: dict,
    insights: Optional[dict],
    notes: List[dict],
    past_interactions: List[dict],
    email_samples: List[dict],
    user_name: str,
    writing_style: Optional[dict] = None,
    custom_prompt: str = None,
    # Trade-specific fields
    products: Optional[list] = None,
    fob_price: Optional[str] = None,
    fob_price_old: Optional[str] = None,
    certifications: Optional[List[str]] = None,
    moq: Optional[str] = None,
    lead_time: Optional[str] = None,
    sample_status: Optional[str] = None,
    effective_date: Optional[str] = None,
    buyer_intelligence: Optional[dict] = None,
    manufacturer_name: Optional[str] = None,
    pre_classification: Optional[dict] = None,
    language: Optional[str] = None,
) -> str:
    """Build agentic email generation prompt for CRM outreach.

    The AI classifies intent from data signals (interaction history, health
    metrics, deal stage) and generates the email in one structured-output call.

    ``language`` controls output language. ``None`` (default) keeps the
    historical behavior — generate English and apply CN→EN cultural adaptation
    when the prompt contains Chinese. ``"zh"`` forces Simplified Chinese output
    and skips the EN cultural-adaptation block. ``"en"`` is the same as
    ``None`` today, but is accepted explicitly so callers can be unambiguous.
    """
    current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    has_samples = bool(email_samples)

    # --- Situational context (auto-detected from interactions) ---
    # Convert past_interactions to email-like format for build_situational_context
    interaction_as_history = []
    for interaction in past_interactions:
        interaction_as_history.append({
            'created_at': interaction.get('created_at'),
            'direction': interaction.get('direction', 'sent'),
            'subject': interaction.get('subject') or interaction.get('content', '')[:80],
            'body': interaction.get('content', ''),
        })
    customer_status = customer_data.get('status', 'active') if isinstance(customer_data, dict) else 'active'
    situation_block = build_situational_context(interaction_as_history, customer_status)

    # --- Customer block ---
    customer_section = format_customer_data(customer_data)
    customer_block = f"<customer>\n{customer_section}\n</customer>"

    # --- Buyer signals (flattened) ---
    buyer_signals_block = build_buyer_signals(buyer_intelligence)

    # --- Manufacturer / trade context ---
    trade_context = build_trade_context(
        products=products, fob_price=fob_price, fob_price_old=fob_price_old,
        certifications=certifications, moq=moq, lead_time=lead_time,
        sample_status=sample_status, effective_date=effective_date,
    )
    manufacturer_block = ""
    mfr_parts = []
    if manufacturer_name:
        mfr_parts.append(f"Company: {manufacturer_name}")
    if trade_context:
        mfr_parts.append(trade_context.strip())
    if mfr_parts:
        manufacturer_block = "<manufacturer>\n" + "\n".join(mfr_parts) + "\n</manufacturer>"

    # --- Interaction history ---
    interactions_section = format_past_interactions(past_interactions)
    history_block = f"<interaction_history>\n{interactions_section}\n</interaction_history>"

    # --- Notes ---
    notes_section = format_notes(notes)
    notes_block = f"<notes>\n{notes_section}\n</notes>"

    # --- Insights ---
    insights_section = format_insights(insights)
    insights_block = f"<insights>\n{insights_section}\n</insights>"

    # --- Writing style ---
    style_block = build_writing_style_instructions(writing_style)
    if not style_block:
        style_block = build_writing_style_instructions(TRADE_VOICE_PRESET)

    # --- Email samples ---
    samples_block = ""
    if has_samples:
        samples_section = format_email_samples(email_samples)
        samples_block = f"<email_samples>\n{samples_section}\n</email_samples>"

    # --- Instructions ---
    instruction_parts = []
    if custom_prompt and custom_prompt.strip():
        instruction_parts.append(custom_prompt.strip())
    instruction_parts.append("Reference buyer's company name in opening.")
    instruction_parts.append("IMPORTANT: Do NOT write 'Regards,', 'Best,', 'Thanks,', 'Sincerely,', 'Cheers,', or ANY sign-off/closing at the end. Do NOT write your name or title. Your output ends with your last content sentence. A signature block is attached separately after your output.")
    if language == "zh":
        instruction_parts.append("Start with '您好 [Primary Contact Name]，' using the Primary Contact from the <customer> block (use 您, not 你). If the contact name is missing, empty, 'Unknown', or 'Unknown Contact', just start with '您好，'.")
        instruction_parts.append("Generate the entire email — subject and body — in Simplified Chinese only. Do NOT output any English text in the subject or body.")
    else:
        instruction_parts.append("Start with 'Hi [Primary Contact Name],' using the Primary Contact from the <customer> block. If the contact name is missing, empty, 'Unknown', or 'Unknown Contact', just start with 'Hi,'. Use the person's first name only, not the company name.")
        instruction_parts.append("Generate in English only.")
    instruction_parts.append("First contact: 50-80 words. Follow-ups: 25-50 words.")
    instruction_parts.append("PARAGRAPH STRUCTURE (CRITICAL): Write exactly 2-3 short paragraphs separated by blank lines (\\n\\n). Paragraph 1: buyer-relevant opening (1-2 sentences). Paragraph 2: your products/pricing (1-2 sentences). Paragraph 3: CTA as a question (1 sentence). Each paragraph MUST be separated by a blank line. Do NOT merge all content into a single paragraph.")
    if past_interactions:
        instruction_parts.append("CRITICAL: Do NOT repeat pricing, certifications, MOQ, or lead time that were already stated in prior emails. The buyer has already seen this information. Focus on answering their questions and advancing the conversation.")

    # CRM-specific guidelines
    instruction_parts.append("Do not mention specific KPIs or metric values explicitly.")
    instruction_parts.append("If health_score < 60: be proactive, address concerns.")
    instruction_parts.append("The user is the person who wrote the notes.")

    instructions_block = "<instructions>\n" + "\n".join(instruction_parts) + "\n</instructions>"

    # --- Pre-classification hint (from Phase 1 Haiku classifier) ---
    hint_block = ""
    if pre_classification:
        conf = pre_classification.get('confidence', 0)
        intent = pre_classification['intent']
        hint_block = (
            f"<pre_classification>\n"
            f"Prior analysis classified this conversation as '{intent}' "
            f"({conf:.0%} confidence). Verify against the email thread before "
            f"generating. Override if the email clearly fits a different intent.\n"
        )
        if conf >= 0.80:
            details = []
            topics = pre_classification.get('topics_discussed', [])
            if topics:
                details.append(f"Topics discussed: {', '.join(topics)}")
            questions = pre_classification.get('unanswered_questions', [])
            if questions:
                details.append(f"Unanswered questions: {', '.join(questions)}")
            shared = pre_classification.get('info_already_shared', [])
            if shared:
                details.append(f"Info already shared: {', '.join(shared)}")
            approach = pre_classification.get('suggested_approach', '')
            if approach:
                details.append(f"Suggested approach: {approach}")
            if details:
                hint_block += "\n".join(details) + "\n"
        hint_block += "</pre_classification>"

    # --- Intent instructions (ALL intents so model can classify + follow) ---
    intent_lines = []
    for intent, guidance in INTENT_INSTRUCTIONS.items():
        intent_lines.append(f"- {intent}: {guidance}")
    intent_block = "<intent_instructions>\nClassify the conversation into one of these intents, then follow its guidance:\n" + "\n".join(intent_lines) + "\n</intent_instructions>"

    # --- Cultural adaptation ---
    # Cultural adaptation rewrites Chinese context into Western business English.
    # Skip it when the caller explicitly asked for Chinese output, otherwise the
    # block fights the language directive and forces English regardless.
    cultural_block = ""
    if language != "zh" and needs_cultural_adaptation(custom_prompt=custom_prompt):
        cultural_block = CULTURAL_ADAPTATION_PROMPT

    # --- Buyer intelligence rules ---
    intel_rules = ""
    if buyer_signals_block:
        intel_rules = BUYER_INTELLIGENCE_RULES

    # --- Assemble prompt ---
    prompt = f"""Date: {current_date}

{situation_block}

{customer_block}
"""

    if buyer_signals_block:
        prompt += f"\n{buyer_signals_block}\n"

    if manufacturer_block:
        prompt += f"\n{manufacturer_block}\n"

    prompt += f"""
{history_block}

{notes_block}

{insights_block}

{style_block}
"""

    if samples_block:
        prompt += f"\n{samples_block}\n"

    prompt += f"""
{instructions_block}
"""

    if hint_block:
        prompt += f"\n{hint_block}\n"

    prompt += f"""
{intent_block}
"""

    if intel_rules:
        prompt += f"\n{intel_rules}\n"

    if cultural_block:
        prompt += f"\n{cultural_block}\n"

    return prompt


def build_mass_email_prompt(
    email_type: str,
    custom_prompt: str,
    sample_client: dict,
    audience_context: Optional[dict] = None
) -> str:
    """Build prompt for mass email template generation.

    Unlike build_crm_email_prompt, this does NOT use interaction history
    because we're generating ONE template for ALL clients.
    """
    current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    prompt = f"""Email Template Generator for Mass Email Campaign

CRITICAL CONTEXT

You are generating an email TEMPLATE for a MASS EMAIL campaign to multiple CRM clients.
This template will be sent to MULTIPLE different companies, so it must be generic enough to work for all of them.

Date: {current_date}
Email Type: {email_type}

Sample client context (for general relevance only):
- Company: {sample_client.get('name', 'N/A')}
- Primary Contact: {sample_client.get('primary_contact', 'N/A')}

INSTRUCTIONS

1. Generate a template that works for MULTIPLE clients, not just one specific client.
2. Use placeholders in this EXACT format: [name], [primary_contact], [email], [phone]
3. Do NOT reference specific past conversations (this is a mass email to multiple clients).
4. Keep tone professional and relationship-focused (existing CRM clients, not cold outreach).
5. Focus on value proposition and continued partnership.
6. Make the email easy to personalize with placeholders.
7. Keep email body to 80-120 words maximum.
8. IMPORTANT: Always generate the email in English, even if some context fields are in Chinese or another language.

AVAILABLE PLACEHOLDERS (use these liberally)

- [name] - company name (REQUIRED - use this multiple times in the email)
- [primary_contact] - primary contact person
- [email] - client email address
- [phone] - phone number

STYLE GUIDELINES

1. Start with "Hi [primary_contact]," (with two newlines after comma).
2. Use [name] placeholder naturally throughout the email.
3. Keep subject lines short and include placeholders.
4. Always end with "Regards," (no name or signature - it will be added automatically).
5. Be human and authentic. Avoid corporate jargon.
"""

    if audience_context:
        company_name = audience_context.get('company_name', '')
        product_desc = audience_context.get('product_description', '')
        hs_codes = audience_context.get('hs_codes', [])
        if company_name or product_desc or hs_codes:
            hs_str = ', '.join(hs_codes) if isinstance(hs_codes, list) else str(hs_codes)
            prompt += f"""
<sender_context>
Your company context (use subtly, do not make the email about you):
- Company: {company_name}
- Products: {product_desc}
- HS Codes: {hs_str}
</sender_context>
"""

    prompt += f"""
CUSTOM CONTEXT

{custom_prompt if custom_prompt else "No additional context provided."}


OUTPUT FORMAT

Return a JSON object with this exact structure:

{{
  "subject": "Email subject line with [placeholders] where appropriate",
  "body": "Email body text with [placeholders] where appropriate.\\n\\nKeep it concise and professional.\\n\\nRegards,"
}}

Output JSON only. No markdown formatting."""

    return prompt
