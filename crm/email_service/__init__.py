"""
Email Service Package for CRM and Customer Success.
Provides AI-powered email generation. Delivery via shared email_core providers.
"""

from .data.models import (
    EmailType, EmailProvider, EmailStatus, EmailSentiment,
    EmailGenerationRequest, EmailSendRequest,
    EmailGenerationResponse, EmailSendResponse
)

__all__ = [
    # Models
    'EmailType', 'EmailProvider', 'EmailStatus', 'EmailSentiment',
    'EmailGenerationRequest', 'EmailSendRequest',
    'EmailGenerationResponse', 'EmailSendResponse',
]
