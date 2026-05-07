"""Shared email models — enums and base request/response types.

Enums are 100% identical between CRM and Leadgen. Request models provide
a shared base; each service extends with its entity ID (customer_id / lead_id).
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


# --- Enums (extracted from both services, identical) ---

class EmailType(str, Enum):
    COLD_OUTREACH = "cold_outreach"
    WARM_INTRODUCTION = "warm_introduction"
    FOLLOW_UP = "follow_up"
    MEETING_REQUEST = "meeting_request"
    THANK_YOU = "thank_you"
    PROPOSAL = "proposal"
    NURTURE = "nurture"
    PROMOTIONAL = "promotional"
    TRANSACTIONAL = "transactional"
    NEWSLETTER = "newsletter"


class EmailProvider(str, Enum):
    GMAIL = "gmail"
    OUTLOOK = "outlook"
    SMTP = "smtp"


class EmailStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    REPLIED = "replied"
    BOUNCED = "bounced"
    FAILED = "failed"


class EmailSentiment(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"


# --- Trade email type identifiers ---

TRADE_EMAIL_TYPES = {
    "initial_outreach",
    "rfq_response",
    "sample_followup",
    "price_update",
}


# --- Base request model ---

class EmailGenerationRequestBase(BaseModel):
    """Shared base for email generation requests.

    CRM extends with customer_id: int.
    Leadgen extends with lead_id: str.
    """
    email_type: Optional[str] = None
    custom_prompt: Optional[str] = ""
    template_id: Optional[str] = None
    strictness_level: int = Field(default=50, ge=0, le=100)
    generation_mode: str = "custom"
    # Existing context fields (en-locale users)
    offer: Optional[str] = None
    ask: Optional[str] = None
    detail: Optional[str] = None
    # Trade-specific fields (zh-CN locale users)
    fob_price: Optional[str] = None
    fob_price_old: Optional[str] = None
    certifications: Optional[List[str]] = None
    moq: Optional[str] = None
    lead_time: Optional[str] = None
    sample_status: Optional[str] = None
    effective_date: Optional[str] = None


# --- Shared response models ---

class EmailGenerationResponse(BaseModel):
    """Response model for email generation."""
    email_data: Dict[str, Any] = Field(..., description="Generated email data")
    success: bool = Field(default=True)
    subject: Optional[str] = Field(None)
    body: Optional[str] = Field(None)
    template_used: Optional[str] = Field(None)


class EmailSendResponse(BaseModel):
    """Response model for email sending."""
    sent_to: str = Field(...)
    success: bool = Field(default=True)
    message: str = Field(default="Email sent successfully")
    message_id: Optional[str] = Field(None)
    provider: Optional[EmailProvider] = Field(None)
    status_changed: bool = Field(default=False)
    new_status: Optional[str] = Field(None)
    tracking_token: Optional[str] = Field(None)
    tracking_expires_at: Optional[datetime] = Field(None)
    sent_timestamp: Optional[datetime] = Field(None)
    thread_id: Optional[str] = Field(None)
    rfc_message_id: Optional[str] = Field(None)


# --- Utility functions ---

def get_email_type_display_name(email_type: EmailType) -> str:
    display_names = {
        EmailType.COLD_OUTREACH: "Cold Outreach",
        EmailType.WARM_INTRODUCTION: "Warm Introduction",
        EmailType.FOLLOW_UP: "Follow Up",
        EmailType.MEETING_REQUEST: "Meeting Request",
        EmailType.THANK_YOU: "Thank You",
        EmailType.PROPOSAL: "Proposal",
        EmailType.NURTURE: "Nurture",
        EmailType.PROMOTIONAL: "Promotional",
        EmailType.TRANSACTIONAL: "Transactional",
        EmailType.NEWSLETTER: "Newsletter",
    }
    return display_names.get(email_type, email_type.value)


def get_sentiment_display_name(sentiment: EmailSentiment) -> str:
    display_names = {
        EmailSentiment.POSITIVE: "Positive",
        EmailSentiment.NEGATIVE: "Negative",
        EmailSentiment.NEUTRAL: "Neutral",
        EmailSentiment.INTERESTED: "Interested",
        EmailSentiment.NOT_INTERESTED: "Not Interested",
    }
    return display_names.get(sentiment, sentiment.value)


# --- Structured output models (Classify-Then-Generate) ---

class ConversationClassification(BaseModel):
    """Unified 9-intent taxonomy: 7 inbound (Haiku classifies) + 2 sent-only (data-determined).

    Collapsed from 16 based on industry benchmarks (Instantly: 8, Outreach: 5+14,
    Reply.io: 6, standard: ~7). Classification complexity lives in Sonnet (generation),
    not Haiku (triage). See docs/email/auto-reply-plan.md for full rationale.
    """
    intent: Literal[
        # Sent-only (data-determined, not classified by Haiku)
        "first_contact",       # No prior emails
        "ghosted",             # No reply after 2+ attempts
        # Inbound (Haiku classifies during sync)
        "interested",          # Buyer shows interest, wants to meet/reschedule
        "question",            # Asks about specs, MOQ, certs, pricing
        "objection",           # Pushback on price, timing, fit, or counter-offer
        "not_interested",      # Explicit rejection or unsubscribe
        "referral",            # Forwarded to another person or wrong contact
        "ooo",                 # Out of office
        "bounce",              # Delivery failure (header-detected, not LLM)
    ]
    sentiment: Literal["positive", "neutral", "negative"]
    topics_discussed: list[str]
    unanswered_questions: list[str]
    info_already_shared: list[str]


class InboundClassification(BaseModel):
    """Haiku classifier output — 7 inbound intents only (no sent-only intents)."""
    intent: Literal[
        "interested", "question", "objection",
        "not_interested", "referral", "ooo", "bounce",
    ]
    sentiment: Literal["positive", "neutral", "negative"]
    confidence: float
    topics_discussed: list[str]
    unanswered_questions: list[str]
    info_already_shared: list[str]
    suggested_approach: str


class EmailOutput(BaseModel):
    classification: ConversationClassification
    subject: Optional[str] = None  # null when intent is ooo
    body: Optional[str] = None     # null when intent is ooo


INTENT_INSTRUCTIONS = {
    "first_contact":    "Warm introduction. Lead with buyer relevance. Include pricing.",
    "ghosted":          "Change the angle entirely. Bring something new. Short and low-pressure.",
    "interested":       "Advance the conversation. Propose concrete next steps (samples, spec sheet, call, or calendar link depending on context).",
    "question":         "Answer ALL questions directly and completely from factory data. #1 failure mode is skipping a question. Include pricing if asked.",
    "objection":        "Acknowledge the concern directly. If price: reframe value (landed cost, quality, MOQ flexibility). If timing: plant a seed, offer to reconnect. If fit: ask clarifying questions, offer alternatives.",
    "not_interested":   "One graceful closing email. Leave the door open without being pushy.",
    "referral":         "Introduce yourself to the new contact. Reference who referred you. Brief.",
    "ooo":              "Do NOT generate an email. Return subject and body as null.",
    "bounce":           "Do NOT generate an email. Return subject and body as null.",
}
