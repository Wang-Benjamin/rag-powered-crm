"""Gmail API helper functions shared across sync and delivery.

Deduplicated from CRM gmail_sync_router.py and Leadgen gmail_sync.py.
Provides low-level parsing — sync service classes stay service-specific.
"""

import base64
import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

logger = logging.getLogger(__name__)


def build_gmail_service(access_token: str, client_id: str = None, client_secret: str = None):
    """Build authenticated Gmail API service object.

    Shared across delivery (send) and sync (fetch). Both need the same
    service construction but use different methods on it.
    """
    try:
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials
    except ImportError:
        raise ImportError("google-api-python-client and google-auth are required for Gmail")

    scopes = [
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.modify'
    ]

    credentials = Credentials(
        token=access_token,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=client_id,
        client_secret=client_secret,
        scopes=scopes
    )

    return build('gmail', 'v1', credentials=credentials)


def decode_gmail_base64(data: str) -> str:
    """Decode URL-safe base64 encoded data from Gmail API."""
    try:
        padding = 4 - (len(data) % 4)
        if padding != 4:
            data += '=' * padding
        return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
    except Exception as e:
        logger.error(f"Error decoding base64: {e}")
        return ""


def extract_gmail_body(payload: Dict) -> str:
    """Extract email body from Gmail message payload (MIME structure).

    Prefers text/plain. Falls back to text/html with tag stripping
    to handle HTML-only emails that would otherwise be lost.
    Recursively walks nested multipart structures.
    """
    import re
    import html as html_mod

    plain = ""
    html = ""

    def _walk_parts(part):
        nonlocal plain, html
        mime = part.get('mimeType', '')
        data = part.get('body', {}).get('data')
        if data:
            if mime == 'text/plain' and not plain:
                plain = decode_gmail_base64(data)
            elif mime == 'text/html' and not html:
                html = decode_gmail_base64(data)
        for sub in part.get('parts', []):
            _walk_parts(sub)

    _walk_parts(payload)

    if plain:
        return plain

    if html:
        text = re.sub(r'<(style|script)[^>]*>.*?</\1>', '', html, flags=re.DOTALL)
        text = re.sub(r'<br\s*/?>', '\n', text)
        text = re.sub(r'</p>', '\n\n', text)
        text = re.sub(r'</div>', '\n', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = html_mod.unescape(text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    return ""


def parse_gmail_headers(message: Dict, include_body: bool = False) -> Optional[Dict]:
    """Parse Gmail API message into a normalized email dict.

    Args:
        message: Gmail API message object (from messages.get)
        include_body: Whether to extract and include email body

    Returns:
        Normalized dict with id, subject, from, to, cc, date, body.
        None if required fields (from, subject) are missing.
    """
    try:
        payload = message.get('payload', {})
        headers = payload.get('headers', [])

        email_data = {
            'id': message.get('id', ''),
            'thread_id': message.get('threadId', ''),
            'subject': '',
            'from': '',
            'to': '',
            'cc': '',
            'date': None,
            'body': ''
        }

        for header in headers:
            name = header['name'].lower()
            value = header['value']

            if name == 'subject':
                email_data['subject'] = value
            elif name == 'from':
                email_data['from'] = value
            elif name == 'to':
                email_data['to'] = value
            elif name == 'cc':
                email_data['cc'] = value
            elif name == 'date':
                try:
                    parsed_date = parsedate_to_datetime(value)
                    if parsed_date.tzinfo is None:
                        parsed_date = parsed_date.replace(tzinfo=timezone.utc)
                    email_data['date'] = parsed_date
                except Exception:
                    email_data['date'] = datetime.now(timezone.utc)

        if include_body:
            email_data['body'] = extract_gmail_body(payload)

        if not email_data['from'] or not email_data['subject']:
            logger.warning(f"Email missing required fields: from={email_data['from']}, subject={email_data['subject']}")
            return None

        return email_data

    except Exception as e:
        logger.error(f"Error parsing Gmail message: {e}")
        return None
