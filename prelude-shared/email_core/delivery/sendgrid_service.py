"""SendGrid email provider — for username/password and WeChat users."""

import os
import re
import logging
from typing import Optional

import httpx

from email_core.models import EmailSendResponse

logger = logging.getLogger(__name__)

OUTREACH_DOMAIN = os.getenv("OUTREACH_DOMAIN", "outreach.preludeos.com")
SENDING_DOMAIN = os.getenv("SENDING_DOMAIN", "preludeos.com")


def _get_api_key() -> str:
    return os.getenv("SENDGRID_API_KEY", "")


def _html_to_plain(html: str) -> str:
    text = re.sub(r'<br\s*/?>', '\n', html)
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()


class SendGridEmailProvider:
    """Sends email via SendGrid from the user's outreach alias."""

    def __init__(self, from_alias: str, display_name: str):
        self.from_alias = from_alias        # e.g. wanglei@outreach.preludeos.com
        self.display_name = display_name

    def is_available(self) -> bool:
        return bool(_get_api_key())

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
    ) -> EmailSendResponse:
        api_key = _get_api_key()
        if not api_key:
            logger.warning("SENDGRID_API_KEY not set — email not sent")
            return EmailSendResponse(sent_to=to_email, success=False, message="SendGrid not configured")

        # Send from username@preludeos.com (authenticated domain), reply-to is the alias
        username_part = self.from_alias.split('@')[0]
        sending_email = f"{username_part}@{SENDING_DOMAIN}"
        display = from_name or self.display_name

        body_plain = body_text or _html_to_plain(body_html)
        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": sending_email, "name": display},
            "reply_to": {"email": self.from_alias, "name": display},
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": body_plain},
                {"type": "text/html", "value": body_html},
            ],
            "headers": {
                "List-Unsubscribe": f"<mailto:{self.from_alias}?subject=unsubscribe>",
            },
        }
        if reply_to_rfc_message_id:
            payload["headers"]["In-Reply-To"] = reply_to_rfc_message_id
            payload["headers"]["References"] = reply_to_rfc_message_id

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=30,
                )
                if resp.status_code in (200, 201, 202):
                    msg_id = resp.headers.get("X-Message-Id", "")
                    logger.info(f"SendGrid sent: {self.from_alias} → {to_email} (id={msg_id})")
                    return EmailSendResponse(
                        sent_to=to_email,
                        success=True,
                        message_id=msg_id,
                        rfc_message_id=f"<{msg_id}@sendgrid.net>" if msg_id else None,
                    )
                else:
                    logger.error(f"SendGrid error {resp.status_code}: {resp.text}")
                    return EmailSendResponse(sent_to=to_email, success=False, message=f"SendGrid error {resp.status_code}")
        except Exception as e:
            logger.error(f"SendGrid send failed: {e}")
            return EmailSendResponse(sent_to=to_email, success=False, message=str(e))
