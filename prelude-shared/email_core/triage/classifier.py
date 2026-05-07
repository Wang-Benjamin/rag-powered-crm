"""Inbound email classifier using Haiku 4.5.

Classifies inbound emails into 7 intents during sync. Fast (~200-400ms),
cheap, runs in parallel via asyncio.Semaphore. Classification is persisted
to conversation_state JSONB for Phase 2 hint injection.

Uses Anthropic SDK's messages.parse() with InboundClassification Pydantic
model for structured output.

Bounce detection is deterministic (sender pattern matching) — no LLM needed.
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional

from anthropic import AsyncAnthropic

from email_core.config import settings
from email_core.models import InboundClassification

logger = logging.getLogger(__name__)

CLASSIFICATION_MODEL = settings.classification_model

# Lazy singleton — avoids creating a new HTTP connection pool per classify_email call
_classifier_client: Optional[AsyncAnthropic] = None


def _get_classifier_client() -> AsyncAnthropic:
    global _classifier_client
    if _classifier_client is None:
        _classifier_client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=30.0)
    return _classifier_client

# Bounce sender patterns — skip Haiku, classify deterministically
BOUNCE_SENDER_PATTERNS = [
    re.compile(r"^mailer-daemon@", re.IGNORECASE),
    re.compile(r"^postmaster@", re.IGNORECASE),
]

# Reply loop headers — skip classification entirely
SKIP_HEADERS = {
    "auto-submitted": {"auto-replied", "auto-generated", "auto-notified"},
    "x-auto-response-suppress": {"all"},
    "precedence": {"bulk", "auto_reply", "junk", "list"},
}


def is_bounce_sender(from_email: str) -> bool:
    """Check if sender matches known bounce patterns."""
    return any(p.match(from_email) for p in BOUNCE_SENDER_PATTERNS)


def should_skip_classification(headers: Optional[Dict[str, str]]) -> bool:
    """Check if email headers indicate auto-reply / bulk — skip classification."""
    if not headers:
        return False
    for header_name, skip_values in SKIP_HEADERS.items():
        header_val = headers.get(header_name, "").lower().strip()
        if header_val and any(sv in header_val for sv in skip_values):
            return True
    return False


def _build_classifier_prompt(thread_emails: List[dict]) -> str:
    """Build classification prompt from the last 3 emails in the thread.

    Includes both inbound and outbound — classifier needs to see what we said
    to understand the intent of the reply. Cap at 500 tokens per email.
    """
    # Take last 3 emails (thread_emails should be newest-first)
    recent = thread_emails[:3]
    # Reverse so they're in chronological order for the prompt
    recent = list(reversed(recent))

    email_blocks = []
    for i, email in enumerate(recent, 1):
        direction = email.get("direction", "unknown")
        subject = email.get("subject", "")[:100]
        body = email.get("body", "")
        # Rough token cap: ~4 chars per token, 500 tokens = 2000 chars
        if len(body) > 2000:
            body = body[:2000] + "..."
        email_blocks.append(
            f"Email {i} ({direction}):\n"
            f"Subject: {subject}\n"
            f"Body: {body}"
        )

    thread_text = "\n\n---\n\n".join(email_blocks)

    return f"""Classify the most recent inbound email in this thread.

<thread>
{thread_text}
</thread>

Classify the LAST inbound email's intent. Consider the full thread context
(what was said by both sides) to determine the buyer's intent.

Return your confidence as a float between 0.0 and 1.0.
For suggested_approach, write one sentence describing how to respond."""


CLASSIFIER_SYSTEM = (
    "You are an email classifier for a B2B trade platform. "
    "Chinese manufacturers use this system to communicate with North American buyers. "
    "Classify the buyer's most recent reply into exactly one intent."
)


async def classify_email(
    thread_emails: List[dict],
    from_email: str = "",
    headers: Optional[Dict[str, str]] = None,
) -> Optional[dict]:
    """Classify a single inbound email.

    Args:
        thread_emails: Recent emails in thread, newest-first.
        from_email: Sender address (for bounce detection).
        headers: Email headers (for reply loop detection).

    Returns:
        Classification dict or None if skipped/failed.
    """
    # Deterministic bounce detection
    if from_email and is_bounce_sender(from_email):
        return {
            "intent": "bounce",
            "sentiment": "neutral",
            "confidence": 1.0,
            "topics_discussed": [],
            "unanswered_questions": [],
            "info_already_shared": [],
            "suggested_approach": "Mark email as invalid.",
        }

    # Skip auto-replies / bulk
    if should_skip_classification(headers):
        logger.debug(f"Skipping classification for auto-reply from {from_email}")
        return None

    api_key = settings.anthropic_api_key
    if not api_key:
        logger.warning("Anthropic API key not configured — skipping classification")
        return None

    prompt = _build_classifier_prompt(thread_emails)

    try:
        client = _get_classifier_client()
        response = await client.messages.parse(
            model=CLASSIFICATION_MODEL,
            max_tokens=500,
            system=CLASSIFIER_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            output_format=InboundClassification,
        )

        parsed: InboundClassification = response.parsed_output
        if parsed is None:
            logger.warning("Empty response from Haiku classifier")
            return None

        result = parsed.model_dump()
        logger.info(
            f"Classified email from {from_email}: "
            f"intent={result['intent']} confidence={result.get('confidence', 0):.2f}"
        )
        return result

    except Exception as e:
        logger.warning(f"Classification failed for {from_email}: {e}")
        return None


async def classify_batch(
    emails: List[dict],
    conn,
    table: str = "crm_emails",
    id_column: str = "email_id",
) -> int:
    """Classify a batch of inbound emails in parallel.

    Args:
        emails: List of dicts with 'email_id', 'from_email', 'thread_emails',
                and optionally 'headers'.
        conn: asyncpg connection for persisting results.
        table: Target table ('crm_emails').
        id_column: Primary key column name.

    Returns:
        Number of emails successfully classified.
    """
    if not emails:
        return 0

    ALLOWED_TABLES = {"crm_emails"}
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Invalid table for classify_batch: {table}")
    if id_column not in {"email_id"}:
        raise ValueError(f"Invalid id_column for classify_batch: {id_column}")

    # Classify in parallel (Haiku API calls are independent), but
    # serialize DB writes (asyncpg connections are not safe for concurrent ops).
    sem = asyncio.Semaphore(10)

    async def classify_one(email: dict) -> Optional[dict]:
        async with sem:
            try:
                classification = await classify_email(
                    thread_emails=email.get("thread_emails", []),
                    from_email=email.get("from_email", ""),
                    headers=email.get("headers"),
                )
                if classification is None:
                    return None

                thread_count = len(email.get("thread_emails", []))
                return {
                    "email_id": email["email_id"],
                    "classification": classification,
                    "conversation_state": {
                        **classification,
                        "thread_message_count": thread_count,
                    },
                }
            except Exception as e:
                logger.warning(
                    f"Classification failed for {email.get('email_id')}: {e}"
                )
                return None

    # Fan out Haiku API calls
    results = await asyncio.gather(*[classify_one(e) for e in emails])

    # Serialize DB writes on the single connection
    classified_count = 0
    for result in results:
        if result is None:
            continue
        try:
            await conn.execute(
                f"""
                UPDATE {table}
                SET conversation_state = $1, intent = $2
                WHERE {id_column} = $3
                """,
                result["conversation_state"],  # asyncpg JSONB codec handles serialization
                result["classification"]["intent"],
                result["email_id"],
            )
            classified_count += 1
        except Exception as e:
            logger.warning(f"Failed to persist classification for {result['email_id']}: {e}")

    logger.info(f"Classified {classified_count}/{len(emails)} emails in batch")
    return classified_count
