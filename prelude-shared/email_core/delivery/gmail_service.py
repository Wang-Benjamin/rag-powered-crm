"""Gmail API Email Provider — sends emails via Gmail OAuth API.

Extracted from prelude-leadgen's gmail_provider.py (cleaner consolidation
of CRM's split gmail.py + gmail_service_v2.py).

Send-only. Mailbox operations (search, read, labels) stay in each service's sync layer.
"""

import base64
import logging
from typing import Dict, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone

try:
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    logging.warning("Google API client not available. Gmail features will be disabled.")

from email_core.config import settings
from email_core.models import EmailProvider, EmailSendResponse

logger = logging.getLogger(__name__)


class GmailEmailProvider:
    """Gmail API email delivery provider with automatic token refresh."""

    def __init__(self, token_manager=None):
        self.client_id = settings.google_client_id
        self.client_secret = settings.google_client_secret
        self.token_manager = token_manager
        self.scopes = [
            'https://www.googleapis.com/auth/gmail.send',
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.modify'
        ]

    def _build_service(self, access_token: str, refresh_token: str = None):
        if not GOOGLE_API_AVAILABLE:
            raise ValueError("Google API client not available")

        credentials = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=self.scopes
        )

        return build('gmail', 'v1', credentials=credentials)

    def _create_message_with_html(
        self,
        to_email: str,
        subject: str,
        body_plain: str,
        body_html: str,
        from_email: str,
        from_name: str = None,
        reply_to_rfc_message_id: str = None
    ) -> Dict:
        """Create email message with custom HTML body (for tracking pixel)."""
        message = MIMEMultipart('alternative')

        if from_name:
            message['From'] = f"{from_name} <{from_email}>"
        else:
            message['From'] = from_email

        message['To'] = to_email
        message['Subject'] = subject

        if reply_to_rfc_message_id:
            message['In-Reply-To'] = reply_to_rfc_message_id
            message['References'] = reply_to_rfc_message_id

        text_part = MIMEText(body_plain, 'plain', 'utf-8')
        message.attach(text_part)

        html_part = MIMEText(body_html, 'html', 'utf-8')
        message.attach(html_part)

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        return {'raw': raw_message}

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
        """Send email via Gmail API. Expects pre-formatted body_html + body_text."""
        try:
            if not self.token_manager:
                raise ValueError("Token manager not configured")

            access_token = await self.token_manager.get_valid_access_token(user_email, 'google')

            if not access_token:
                return EmailSendResponse(
                    sent_to=to_email,
                    success=False,
                    message="No valid Gmail token found. Please re-authenticate with Google.",
                    provider=EmailProvider.GMAIL
                )

            service = self._build_service(access_token)

            message = self._create_message_with_html(
                to_email, subject, body_text, body_html, from_email, from_name,
                reply_to_rfc_message_id=reply_to_rfc_message_id
            )

            if reply_to_thread_id:
                message['threadId'] = reply_to_thread_id

            result = service.users().messages().send(
                userId='me', body=message
            ).execute()

            message_id = result.get('id')
            thread_id = result.get('threadId')

            sent_timestamp = None
            rfc_message_id = None
            try:
                msg_details = service.users().messages().get(
                    userId='me', id=message_id,
                    format='metadata', metadataHeaders=['Date', 'Message-ID']
                ).execute()

                internal_date = msg_details.get('internalDate')
                if internal_date:
                    sent_timestamp = datetime.fromtimestamp(int(internal_date) / 1000, tz=timezone.utc)

                headers = msg_details.get('payload', {}).get('headers', [])
                for header in headers:
                    if header.get('name', '').lower() == 'message-id':
                        rfc_message_id = header.get('value')
                        break
            except Exception as e:
                logger.warning(f"Could not fetch sent message details: {e}")
                sent_timestamp = datetime.now(timezone.utc)

            logger.info(f"Gmail email sent - thread_id: {thread_id}, rfc_message_id: {rfc_message_id}")

            return EmailSendResponse(
                sent_to=to_email,
                success=True,
                message="Email sent successfully via Gmail",
                message_id=message_id,
                provider=EmailProvider.GMAIL,
                sent_timestamp=sent_timestamp,
                thread_id=thread_id,
                rfc_message_id=rfc_message_id
            )

        except Exception as e:
            logger.error(f"Error sending email via Gmail: {e}")
            return EmailSendResponse(
                sent_to=to_email,
                success=False,
                message=f"Failed to send email via Gmail: {str(e)}",
                provider=EmailProvider.GMAIL
            )

    def is_available(self) -> bool:
        return GOOGLE_API_AVAILABLE and bool(self.client_id) and bool(self.client_secret)
