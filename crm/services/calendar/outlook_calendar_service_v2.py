"""
Outlook Calendar Service V2 with Auto-Refreshing Tokens
This version automatically handles token refresh using the OAuthTokenManager.
No more 1-hour expiration issues!
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from .outlook_calendar_service import OutlookCalendarService
from .oauth_token_manager import OAuthTokenManager

logger = logging.getLogger(__name__)


class OutlookCalendarServiceV2:
    """
    Outlook Calendar service with automatic token refresh.
    Wraps the original OutlookCalendarService and adds token management.
    """

    def __init__(self, user_email: str, get_connection_fn, auth_provider):
        """
        Initialize Outlook Calendar service with auto-refresh capability.

        Args:
            user_email: User's email address (used to lookup tokens)
            get_connection_fn: Function that returns a database connection (connection factory)
            auth_provider: SimpleAuthProvider instance for token refresh
        """
        self.user_email = user_email
        self.token_manager = OAuthTokenManager(auth_provider)
        self._calendar_service = None

    async def _get_calendar_service(self) -> OutlookCalendarService:
        """
        Get OutlookCalendarService with a valid access token.
        Auto-refreshes token if expired.

        Returns:
            OutlookCalendarService instance with valid token
        """
        # Get valid access token (auto-refreshes if needed)
        access_token = await self.token_manager.get_valid_access_token(
            user_email=self.user_email,
            provider='microsoft'
        )

        if not access_token:
            raise Exception(
                f"No valid Microsoft access token available for {self.user_email}. "
                "Please reconnect Outlook Calendar."
            )

        # Create new service instance with fresh token
        return OutlookCalendarService(access_token)

    async def create_event(
        self,
        summary: str,
        description: str,
        start_datetime: str,
        end_datetime: str,
        attendees: List[str],
        timezone: str = "UTC",
        location: str = None
    ) -> Dict[str, Any]:
        """Create a new event in Outlook Calendar with auto-refresh token."""
        service = await self._get_calendar_service()
        return await service.create_event(
            summary=summary,
            description=description,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            attendees=attendees,
            timezone=timezone,
            location=location
        )

    async def update_event(
        self,
        event_id: str,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        start_datetime: Optional[str] = None,
        end_datetime: Optional[str] = None,
        attendees: Optional[List[str]] = None,
        timezone: Optional[str] = None,
        location: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update an existing event in Outlook Calendar with auto-refresh token."""
        service = await self._get_calendar_service()
        return await service.update_event(
            event_id=event_id,
            summary=summary,
            description=description,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            attendees=attendees,
            timezone=timezone,
            location=location
        )

    async def delete_event(self, event_id: str) -> bool:
        """Delete an event from Outlook Calendar with auto-refresh token."""
        service = await self._get_calendar_service()
        return await service.delete_event(event_id)

    async def get_event(self, event_id: str) -> Dict[str, Any]:
        """Get a single event from Outlook Calendar with auto-refresh token."""
        service = await self._get_calendar_service()
        return await service.get_event(event_id)

    async def list_events(
        self,
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """List events from Outlook Calendar with auto-refresh token."""
        service = await self._get_calendar_service()
        return await service.list_events(
            time_min=time_min,
            time_max=time_max,
            max_results=max_results
        )
