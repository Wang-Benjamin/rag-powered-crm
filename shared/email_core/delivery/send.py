"""Send orchestrator — single entry point for formatting → tracking → provider.

Callers pass raw body (plain text or HTML). The orchestrator normalizes to
body_html + body_text, injects tracking pixel, sends via provider, and
attaches tracking metadata to the result.
"""

import logging
from typing import Optional

from email_core.config import settings
from email_core.models import EmailSendResponse
from email_core.delivery.formatting import text_to_html, html_to_plain
from email_core.delivery.tracking_service import TrackingService

logger = logging.getLogger(__name__)


async def send_email(
    provider,
    user_email: str,
    to_email: str,
    subject: str,
    body: str,
    from_email: str,
    from_name: Optional[str] = None,
    reply_to_thread_id: Optional[str] = None,
    reply_to_rfc_message_id: Optional[str] = None,
    track_opens: bool = True,
    provider_hint: Optional[str] = None,
) -> EmailSendResponse:
    """Send an email: formatting → tracking → provider.send_email().

    Args:
        provider: Any object satisfying EmailDeliveryProvider protocol.
        user_email: Sender's email (used for token lookup + tracking routing).
        to_email: Recipient email.
        subject: Email subject.
        body: Plain text or HTML — orchestrator normalizes.
        from_email: From address.
        from_name: Display name for From header.
        reply_to_thread_id: Gmail threadId for reply threading.
        reply_to_rfc_message_id: RFC 2822 Message-ID for In-Reply-To header.
        track_opens: Whether to inject tracking pixel.
        provider_hint: 'outlook' for inline styles, None/'gmail' for <style> block.
    """
    # 1. Normalize to HTML + plain text
    body_html = text_to_html(body, provider_hint)
    body_text = html_to_plain(body_html)

    # 2. Inject tracking pixel (non-fatal — email still sends if tracking fails)
    tracking_token = None
    tracking_expires_at = None
    if track_opens:
        try:
            tracker = TrackingService(base_url=settings.tracking_base_url)
            tracking_token = tracker.generate_tracking_token()
            tracking_expires_at = tracker.get_token_expiration()
            body_html = tracker.add_tracking_pixel(body_html, tracking_token, user_email)
        except Exception as e:
            logger.warning(f"Tracking pixel injection failed (email will still send): {e}")
            tracking_token = None
            tracking_expires_at = None

    # 3. Send via provider
    result = await provider.send_email(
        user_email=user_email,
        to_email=to_email,
        subject=subject,
        body_html=body_html,
        body_text=body_text,
        from_email=from_email,
        from_name=from_name,
        reply_to_thread_id=reply_to_thread_id,
        reply_to_rfc_message_id=reply_to_rfc_message_id,
    )

    # 4. Attach tracking metadata only on successful sends
    if tracking_token and result.success:
        result.tracking_token = tracking_token
        result.tracking_expires_at = tracking_expires_at

    return result
