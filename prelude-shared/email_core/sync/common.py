"""Common email parsing utilities shared across sync services.

Deduplicated from CRM gmail_sync_router.py, outlook_sync_router.py,
and email_sync_service.py where these were copy-pasted.
"""

import re
import logging
from typing import List

logger = logging.getLogger(__name__)

_EMAIL_PATTERN = re.compile(r'<([^>]+@[^>]+)>|([^\s,;<]+@[^\s,;<]+)')


def extract_email_addresses(text: str) -> List[str]:
    """Extract email addresses from a string like 'Name <email>, Name <email>'.

    Handles both angle-bracket format and bare addresses.
    """
    if not text:
        return []

    matches = _EMAIL_PATTERN.findall(text)
    emails = []
    for match in matches:
        email = match[0] or match[1]
        if email:
            emails.append(email.lower().strip())

    return emails
