"""
CRM email models.
"""

from pydantic import BaseModel, Field, EmailStr
from typing import List, Literal, Optional, Dict, Any
from datetime import datetime

from email_core.models import EmailType, EmailProvider, EmailStatus, EmailSentiment  # noqa: F401


# Request Models

class EmailGenerationRequest(BaseModel):
    """Request model for generating emails (agentic mode).

    The AI determines email intent from data signals. No email_type needed.
    """
    customer_id: int
    custom_prompt: Optional[str] = None
    template_id: Optional[str] = None
    strictness_level: int = 50
    generation_mode: str = "custom"
    # Trade-specific fields
    products: Optional[List[dict]] = Field(default=None, description="Products with pricing [{name, fobPrice, landedPrice}]")
    fob_price: Optional[str] = None
    fob_price_old: Optional[str] = None
    certifications: Optional[List[str]] = None
    moq: Optional[str] = None
    lead_time: Optional[str] = None
    sample_status: Optional[str] = None
    effective_date: Optional[str] = None
    # Output language. None = legacy behavior (English + cultural adaptation
    # when the prompt contains Chinese characters). "zh" = generate Simplified
    # Chinese and skip the EN cultural-adaptation block.
    language: Optional[Literal["zh", "en"]] = None


class EmailSendRequest(BaseModel):
    """Request model for sending emails."""
    to_email: EmailStr
    subject: str
    body: str
    customer_id: Optional[int] = None
    deal_id: Optional[int] = None
    provider: Optional[str] = None
    access_token: Optional[str] = None
    reply_to_thread_id: Optional[str] = None
    reply_to_rfc_message_id: Optional[str] = None


# Response Models

class EmailGenerationResponse(BaseModel):
    """Response model for email generation."""
    email_data: Dict[str, Any] = Field(..., description="Generated email data")
    success: bool = Field(default=True, description="Whether generation was successful")
    subject: Optional[str] = Field(None, description="Generated email subject")
    body: Optional[str] = Field(None, description="Generated email body")
    template_used: Optional[str] = Field(None, description="Template used for generation")


class EmailSendResponse(BaseModel):
    """Response model for email sending."""
    sent_to: str = Field(..., description="Email address sent to")
    success: bool = Field(default=True, description="Whether send was successful")
    message: str = Field(default="Email sent successfully", description="Response message")
    message_id: Optional[str] = Field(None, description="Provider message ID")
    provider: Optional[EmailProvider] = Field(None, description="Email provider used")
    status_changed: bool = Field(default=False, description="Whether lead status was updated")
    new_status: Optional[str] = Field(None, description="New lead status if changed")
    sent_timestamp: Optional[datetime] = Field(None, description="Actual send timestamp from provider")
    tracking_token: Optional[str] = Field(None, description="Email open tracking token")
    tracking_expires_at: Optional[datetime] = Field(None, description="Tracking token expiration")
    thread_id: Optional[str] = Field(None, description="Gmail threadId or Outlook conversationId")
    rfc_message_id: Optional[str] = Field(None, description="RFC 2822 Message-ID header value")


# Mass Email Models

class MassEmailSendRequest(BaseModel):
    """Request to send mass email with template from User Settings service."""
    customer_ids: List[int] = Field(description="List of customer IDs to send to")
    template_id: Optional[str] = Field(default=None, description="UUID of template from User Settings service")
    subject: Optional[str] = Field(default=None, description="User-edited subject (overrides template if provided)")
    body: Optional[str] = Field(default=None, description="User-edited body (overrides template if provided)")
    provider: Optional[str] = Field(default=None, description="Email provider (gmail/outlook)")
    access_token: Optional[str] = Field(default=None, description="OAuth2 access token if needed")
    deal_mappings: Optional[List[Dict[str, int]]] = Field(default=None, description="Optional deal mappings for deal-specific tracking [{client_id, deal_id}, ...]")


class PersonalizedMassEmailRequest(BaseModel):
    """Request for personalized mass email generation.

    Supports two modes:
    - Template Mode: Uses template_id with strictness_level to control AI adherence
    - Custom Mode: Uses custom_prompt for freeform AI generation
    """
    customer_ids: List[int] = Field(..., min_length=1, max_length=25, description="List of customer IDs (max 25)")
    custom_prompt: Optional[str] = Field(default="", description="Custom instructions for AI generation")
    template_id: Optional[str] = Field(default=None, description="UUID of template to use")
    strictness_level: int = Field(default=50, ge=0, le=100, description="How closely to follow template (0=strict, 100=creative)")
    generation_mode: str = Field(default="custom", description="Generation mode: 'template' or 'custom'")
    # Trade-specific fields (pivot — batch-wide, same for all recipients)
    products: Optional[List[dict]] = Field(default=None, description="Products with pricing [{name, fobPrice, landedPrice}]")
    fob_price: Optional[str] = Field(default=None, description="FOB price")
    fob_price_old: Optional[str] = Field(default=None, description="Previous FOB price")
    certifications: Optional[List[str]] = Field(default=None, description="Selected certifications")
    moq: Optional[str] = Field(default=None, description="Minimum order quantity")
    lead_time: Optional[str] = Field(default=None, description="Lead time")
    sample_status: Optional[str] = Field(default=None, description="Sample status")
    effective_date: Optional[str] = Field(default=None, description="Effective date")


class PersonalizedMassEmailSendRequest(BaseModel):
    """Request to send personalized mass emails."""
    emails: List[Dict[str, Any]] = Field(description="List of emails with client_id, subject, body, to_email")
    provider: Optional[str] = Field(default=None, description="Email provider (gmail/outlook)")
    modified_emails: List[Dict[str, Any]] = Field(default_factory=list, description="List of edited emails for writing style updates")
    # Campaign context (persisted with campaign for analytics)
    offer: Optional[str] = Field(default=None, description="Offer context")
    ask: Optional[str] = Field(default=None, description="Ask context")
    detail: Optional[str] = Field(default=None, description="Detail context")
    custom_prompt: Optional[str] = Field(default=None, description="Custom prompt")
    fob_price: Optional[str] = Field(default=None, description="FOB price used")
    fob_price_old: Optional[str] = Field(default=None, description="Previous FOB price")
    certifications: Optional[List[str]] = Field(default=None, description="Certifications used")
    moq: Optional[str] = Field(default=None, description="MOQ used")
    lead_time: Optional[str] = Field(default=None, description="Lead time used")
    sample_status: Optional[str] = Field(default=None, description="Sample status")
    effective_date: Optional[str] = Field(default=None, description="Effective date")


# Scheduled Mass Email Models

class ScheduleMassEmailRequest(BaseModel):
    """Request to schedule a mass email for future delivery."""
    scheduled_at: str = Field(description="ISO 8601 datetime for when to send")
    email_type: str = Field(default="personalized", description="'template' or 'personalized'")
    customer_ids: Optional[List[int]] = Field(default=None, description="Customer IDs for template mode")
    template_id: Optional[str] = Field(default=None, description="Template UUID")
    subject: Optional[str] = Field(default=None, description="Email subject")
    body: Optional[str] = Field(default=None, description="Email body")
    provider: Optional[str] = Field(default=None, description="Email provider")
    deal_mappings: Optional[List[Dict[str, Any]]] = Field(default=None, description="Deal mappings")
    emails: Optional[List[Dict[str, Any]]] = Field(default=None, description="Pre-generated personalized emails")
    modified_emails: List[Dict[str, Any]] = Field(default_factory=list, description="Edited emails for writing style")
    # Campaign context (mirrors PersonalizedMassEmailSendRequest)
    offer: Optional[str] = Field(default=None, description="Offer context")
    ask: Optional[str] = Field(default=None, description="Ask context")
    detail: Optional[str] = Field(default=None, description="Detail context")
    custom_prompt: Optional[str] = Field(default=None, description="Custom prompt")
    fob_price: Optional[str] = Field(default=None, description="FOB price used")
    fob_price_old: Optional[str] = Field(default=None, description="Previous FOB price")
    certifications: Optional[List[str]] = Field(default=None, description="Certifications used")
    moq: Optional[str] = Field(default=None, description="MOQ used")
    lead_time: Optional[str] = Field(default=None, description="Lead time used")
    sample_status: Optional[str] = Field(default=None, description="Sample status")
    effective_date: Optional[str] = Field(default=None, description="Effective date")


class ScheduleDirectEmailRequest(BaseModel):
    """Schedule a single direct email for future delivery."""
    scheduled_at: str = Field(description="ISO 8601 datetime for when to send")
    to_email: str = Field(description="Recipient email address")
    subject: str = Field(description="Email subject")
    body: str = Field(description="Email body (HTML)")
    customer_id: Optional[int] = Field(default=None, description="CRM customer ID")
    deal_id: Optional[str] = Field(default=None, description="Associated deal ID")
    provider: Optional[str] = Field(default=None, description="Email provider (gmail/outlook/sendgrid)")
