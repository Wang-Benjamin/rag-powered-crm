"""SMTP Email Provider — sends emails via SMTP protocol.

Kept for future QQ Mail / 163 Mail integration (per-user SMTP credentials).
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from datetime import datetime, timezone

from email_core.config import settings
from email_core.models import EmailProvider, EmailSendResponse

logger = logging.getLogger(__name__)


class SMTPEmailProvider:
    """SMTP-based email delivery provider."""

    def __init__(self):
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_user = settings.smtp_user
        self.smtp_password = settings.smtp_password

    async def send_email(
        self,
        user_email: str,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: str,
        from_email: str,
        from_name: str = None,
        reply_to_thread_id: str = None,
        reply_to_rfc_message_id: str = None
    ) -> EmailSendResponse:
        """Send email using SMTP. Expects pre-formatted body_html."""
        try:
            if not self.smtp_user or not self.smtp_password:
                raise ValueError("SMTP credentials not configured")

            msg = MIMEMultipart('alternative')
            msg['From'] = formataddr((from_name or 'Sales Team', from_email or self.smtp_user))
            msg['To'] = to_email
            msg['Subject'] = subject

            if reply_to_rfc_message_id:
                msg['In-Reply-To'] = reply_to_rfc_message_id
                msg['References'] = reply_to_rfc_message_id

            text_part = MIMEText(body_text, 'plain', 'utf-8')
            msg.attach(text_part)

            html_part = MIMEText(body_html, 'html', 'utf-8')
            msg.attach(html_part)

            send_timestamp = datetime.now(timezone.utc)

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            return EmailSendResponse(
                sent_to=to_email,
                success=True,
                message="Email sent successfully via SMTP",
                provider=EmailProvider.SMTP,
                sent_timestamp=send_timestamp,
            )

        except Exception as e:
            logger.error(f"Error sending email via SMTP: {e}")
            return EmailSendResponse(
                sent_to=to_email,
                success=False,
                message=f"Failed to send email: {str(e)}",
                provider=EmailProvider.SMTP
            )

    def is_available(self) -> bool:
        return bool(self.smtp_user and self.smtp_password)
