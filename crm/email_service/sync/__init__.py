"""Email sync services for CRM."""

from .gmail_sync import GmailSyncService
from .outlook_sync import OutlookSyncService

__all__ = ['GmailSyncService', 'OutlookSyncService']

