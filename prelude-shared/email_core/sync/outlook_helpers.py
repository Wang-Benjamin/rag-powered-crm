"""Outlook / Microsoft Graph API helper functions shared across sync services.

Deduplicated from CRM outlook_sync_router.py and Leadgen outlook_sync.py.
Provides low-level parsing — sync service classes stay service-specific.
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

# Microsoft Graph API constants
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
MESSAGES_ENDPOINT = f"{GRAPH_API_BASE}/me/messages"
USER_PROFILE_ENDPOINT = f"{GRAPH_API_BASE}/me"

# Default fields to select when fetching messages (reduces payload size)
DEFAULT_MESSAGE_SELECT = "id,subject,from,toRecipients,ccRecipients,receivedDateTime,bodyPreview,conversationId,internetMessageId"


def extract_outlook_email_address(email_obj: Dict) -> str:
    """Extract email address string from Outlook's email object format.

    Args:
        email_obj: Microsoft Graph emailAddress object
                   e.g. {"emailAddress": {"name": "John", "address": "john@co.com"}}

    Returns:
        Lowercase email address string, or empty string
    """
    if not email_obj or 'emailAddress' not in email_obj:
        return ''
    return email_obj['emailAddress'].get('address', '').lower().strip()


def format_outlook_email_address(email_obj: Dict) -> str:
    """Format Outlook email object to 'Name <email>' format (like Gmail headers).

    Args:
        email_obj: Microsoft Graph emailAddress object

    Returns:
        Formatted string like "John Doe <john@co.com>" or bare "john@co.com"
    """
    if not email_obj or 'emailAddress' not in email_obj:
        return ''

    email_addr = email_obj['emailAddress']
    name = email_addr.get('name', '')
    address = email_addr.get('address', '')

    if name and name != address:
        return f"{name} <{address}>"
    return address


def parse_outlook_recipients(recipients: List[Dict]) -> List[str]:
    """Parse Outlook recipients list to email address strings.

    Args:
        recipients: List of Microsoft Graph recipient objects
                    e.g. [{"emailAddress": {"address": "a@co.com"}}, ...]

    Returns:
        List of lowercase email addresses
    """
    if not recipients:
        return []

    emails = []
    for recipient in recipients:
        if 'emailAddress' in recipient and 'address' in recipient['emailAddress']:
            emails.append(recipient['emailAddress']['address'].lower().strip())
    return emails


def format_outlook_recipients(recipients: List[Dict]) -> str:
    """Format Outlook recipients list to comma-separated 'Name <email>' string.

    Args:
        recipients: List of Microsoft Graph recipient objects

    Returns:
        Comma-separated formatted string like "John <j@co.com>, Jane <a@co.com>"
    """
    if not recipients:
        return ''

    formatted = []
    for recipient in recipients:
        formatted.append(format_outlook_email_address(recipient))

    return ', '.join(f for f in formatted if f)
