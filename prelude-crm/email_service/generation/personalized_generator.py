"""Personalized email generation for CRM clients (asyncpg)."""

import logging
from datetime import datetime, timezone
from typing import Optional

import asyncpg

from email_service.data.fetchers import build_email_generation_payload
from email_service.generation.prompt_builder import build_crm_email_prompt, build_strictness_prompt
from email_core.generator import generate_email_with_ai
from email_core.delivery.signature_formatter import attach_signature_to_email

logger = logging.getLogger(__name__)

# Always use trade advisor persona (agentic mode)
TRADE_ADVISOR_PERSONA = (
    "You are an international trade advisor helping a manufacturer "
    "communicate with North American buyers."
)


async def generate_single_personalized_email_crm(
    client_id: int,
    custom_prompt: str,
    conn: asyncpg.Connection,
    user_email: str,
    user_name: str,
    employee_id: Optional[int],
    index: int,
    total: int,
    prefetched_payload: Optional[dict] = None,
    template: Optional[dict] = None,
    strictness_level: int = 50,
    generation_mode: str = "custom",
    trade_fields: Optional[dict] = None,
    language: Optional[str] = None,
) -> Optional[dict]:
    """
    Generate a personalized email for a single client (CRM).

    This function is designed to be run in parallel with asyncio.gather().
    Returns None on failure instead of raising to allow partial success.
    """
    try:
        logger.info(f"Generating email {index+1}/{total} for client {client_id}")

        # Use pre-fetched payload if available, otherwise fetch individually
        if prefetched_payload:
            payload = prefetched_payload
        elif conn is not None:
            payload = await build_email_generation_payload(
                client_id,
                conn,
                employee_id=employee_id,
                user_email=user_email,
            )
        else:
            logger.warning(f"No prefetched payload and no DB connection for client {client_id}, skipping")
            return None

        # Phase 2: Read pre-computed classification from latest inbound email.
        # past_interactions is sorted newest-first (created_at DESC).
        pre_class = None
        past_interactions = payload.get('past_interactions', [])
        for interaction in past_interactions:
            if interaction.get('direction') == 'received' and interaction.get('conversation_state'):
                pre_class = interaction['conversation_state']
                break

        # Staleness check — skip hint if thread has grown since classification
        # Filter to emails only (past_interactions includes calls/meetings too)
        HISTORY_LIMIT = 20
        if pre_class:
            stored = pre_class.get('thread_message_count', 0)
            email_interactions = [i for i in past_interactions if i.get('type') == 'email']
            current = len(email_interactions)
            if min(stored, HISTORY_LIMIT) != min(current, HISTORY_LIMIT):
                logger.info(f"Stale classification for client {client_id}: stored={stored}, current={current}")
                pre_class = None

        # Build prompt based on generation mode
        if generation_mode == "template" and template:
            # Template mode: use strictness-based prompt
            combined_prompt = build_strictness_prompt(
                template=template,
                strictness_level=strictness_level,
                custom_context=custom_prompt if custom_prompt else None,
                recipient_data=payload['customer_data'],
            )
        else:
            # Agentic mode: custom_prompt passes through directly
            combined_prompt = custom_prompt

        # Build full agentic prompt — AI determines intent from data signals
        tf = trade_fields or {}
        prompt = build_crm_email_prompt(
            customer_data=payload['customer_data'],
            insights=payload['insights'],
            notes=payload['notes'],
            past_interactions=payload['past_interactions'],
            email_samples=payload.get('email_samples', []),
            user_name=user_name,
            writing_style=payload.get('writing_style'),
            custom_prompt=combined_prompt,
            products=tf.get('products'),
            fob_price=tf.get('fob_price'),
            fob_price_old=tf.get('fob_price_old'),
            certifications=tf.get('certifications'),
            moq=tf.get('moq'),
            lead_time=tf.get('lead_time'),
            sample_status=tf.get('sample_status'),
            effective_date=tf.get('effective_date'),
            buyer_intelligence=payload.get('buyer_intelligence'),
            manufacturer_name=payload.get('audience_context', {}).get('company_name') if payload.get('audience_context') else None,
            pre_classification=pre_class,
            language=language,
        )

        # Generate email — always use trade advisor persona
        result = await generate_email_with_ai(prompt, persona=TRADE_ADVISOR_PERSONA)

        # Log Haiku vs Sonnet disagreement for accuracy tracking
        if pre_class and result.get('classification'):
            haiku_intent = pre_class['intent']
            sonnet_intent = result['classification']['intent']
            if haiku_intent != sonnet_intent:
                logger.info(
                    f"Classification disagreement for client {client_id}: "
                    f"Haiku={haiku_intent} ({pre_class.get('confidence', 0):.0%}), "
                    f"Sonnet={sonnet_intent}"
                )

        # Attach signature (use pre-fetched data when available to avoid concurrent conn usage)
        try:
            prefetched_sig = payload.get('signature_data') if prefetched_payload else None
            result = await attach_signature_to_email(
                result, user_email, conn=conn, signature_data=prefetched_sig,
            )
        except Exception as e:
            logger.warning(f"Failed to attach signature for client {client_id}: {e}")

        # Build email data with all client fields
        email_data = {
            "client_id": client_id,
            "client_name": payload['customer_data'].get('company', 'Unknown'),
            "client_email": payload['customer_data'].get('email', ''),
            "primary_contact": payload['customer_data'].get('primary_contact', ''),
            "phone": payload['customer_data'].get('phone', ''),
            "subject": result['email_data']['subject'],
            "body": result['email_data']['body'],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "classification": result.get('classification'),
        }

        logger.info(f"Generated email for {payload['customer_data'].get('company')}")
        return email_data

    except Exception as e:
        logger.error(f"Failed to generate email for client {client_id}: {e}", exc_info=True)
        return None
