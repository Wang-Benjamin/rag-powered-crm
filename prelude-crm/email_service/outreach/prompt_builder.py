"""Prompt builder for initial outreach email generation — BoL leads.

The AI determines email intent from data signals (email history, lead status,
buyer intelligence). No email_type parameter needed.
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


def build_lead_email_prompt(
    lead_data: dict,
    email_history: List[dict],
    notes: str,
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
) -> str:
    """Build agentic email generation prompt for lead outreach.

    The AI classifies intent from data signals and generates the email in one
    structured-output call. No email_type parameter needed.
    """
    current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lead_status = lead_data.get('status', 'new')

    # --- Situational context (auto-detected from history) ---
    situation_block = build_situational_context(email_history, lead_status)

    # --- Buyer block ---
    buyer_lines = [
        f"Company: {lead_data.get('company', 'Unknown')}",
        f"Industry: {lead_data.get('industry', 'Business')}",
        f"Location: {lead_data.get('location', 'Unknown')}",
    ]
    contact_name = lead_data.get('name', '')
    if contact_name:
        buyer_lines.append(f"Contact: {contact_name}")
    buyer_block = "<buyer>\n" + "\n".join(buyer_lines) + "\n</buyer>"

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

    # --- Email history ---
    thread_summary = format_thread_summary(email_history)
    history_block = f"<email_history>\n{thread_summary}\n</email_history>"

    # --- Writing style (user's style or trade voice preset fallback) ---
    style_block = build_writing_style_instructions(writing_style)
    if not style_block:
        # Use trade voice preset as default writing style
        style_block = build_writing_style_instructions(TRADE_VOICE_PRESET)

    # --- Email samples ---
    samples_block = ""
    if email_samples:
        sample_lines = []
        for i, sample in enumerate(email_samples, 1):
            if isinstance(sample, dict):
                sample_lines.append(f"Sample {i}:\nSubject: {sample.get('subject', '')}\nBody: {sample.get('body', '')}")
            elif isinstance(sample, str):
                sample_lines.append(f"Sample {i}:\n{sample}")
        samples_block = "<email_samples>\n" + "\n\n".join(sample_lines) + "\n</email_samples>"

    # --- Notes ---
    notes_text = notes.strip() if notes and notes.strip() else "No notes."
    notes_block = f"<notes>\n{notes_text}\n</notes>"

    # --- Instructions ---
    instruction_parts = []
    if custom_prompt and custom_prompt.strip():
        instruction_parts.append(custom_prompt.strip())
    instruction_parts.append("Reference buyer's company name in opening.")
    instruction_parts.append("IMPORTANT: Do NOT write 'Regards,', 'Best,', 'Thanks,', 'Sincerely,', 'Cheers,', or ANY sign-off/closing at the end. Do NOT write your name or title. Your output ends with your last content sentence. A signature block is attached separately after your output.")
    instruction_parts.append("Start with 'Hi [Contact Name],' using the Contact from the <buyer> block. If the contact name is missing, empty, 'Unknown', or 'Unknown Contact', just start with 'Hi,'. Use the person's first name only, not the company name.")
    instruction_parts.append("Generate in English only.")
    instruction_parts.append("First contact: 50-80 words. Follow-ups: 25-50 words.")
    instruction_parts.append("PARAGRAPH STRUCTURE (CRITICAL): Write exactly 2-3 short paragraphs separated by blank lines (\\n\\n). Paragraph 1: buyer-relevant opening (1-2 sentences). Paragraph 2: your products/pricing (1-2 sentences). Paragraph 3: CTA as a question (1 sentence). Each paragraph MUST be separated by a blank line. Do NOT merge all content into a single paragraph.")
    if email_history:
        instruction_parts.append("CRITICAL: Do NOT repeat pricing, certifications, MOQ, or lead time that were already stated in prior emails. The buyer has already seen this information. Focus on answering their questions and advancing the conversation.")
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
    cultural_block = ""
    if needs_cultural_adaptation(custom_prompt=custom_prompt):
        cultural_block = CULTURAL_ADAPTATION_PROMPT

    # --- Buyer intelligence rules ---
    intel_rules = ""
    if buyer_signals_block:
        intel_rules = BUYER_INTELLIGENCE_RULES

    # --- Assemble prompt ---
    prompt = f"""Date: {current_date}

{situation_block}

{buyer_block}
"""

    if buyer_signals_block:
        prompt += f"\n{buyer_signals_block}\n"

    if manufacturer_block:
        prompt += f"\n{manufacturer_block}\n"

    prompt += f"""
{history_block}

{notes_block}

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
