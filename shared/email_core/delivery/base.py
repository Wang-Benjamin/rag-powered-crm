"""Email delivery provider protocol — target contract for all providers.

Providers will conform to this after Phase 3 (when formatting/tracking is
stripped and the send orchestrator handles pre-processing). During Phase 1-2,
providers still accept `body` and do their own formatting internally.
"""

from typing import Optional, Protocol

from email_core.models import EmailSendResponse


class EmailDeliveryProvider(Protocol):
    """Protocol that all email delivery providers must satisfy."""

    async def send_email(
        self,
        user_email: str,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: str,
        from_email: str,
        from_name: Optional[str] = None,
        reply_to_thread_id: Optional[str] = None,
        reply_to_rfc_message_id: Optional[str] = None,
    ) -> EmailSendResponse: ...

    def is_available(self) -> bool: ...
