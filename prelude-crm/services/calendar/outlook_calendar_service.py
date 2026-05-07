"""
Outlook Calendar Service for creating, updating, and syncing meetings.
Uses Microsoft Graph API with access token.
Handles two-way sync between CRM and Outlook Calendar.
"""

import logging
import httpx
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class OutlookCalendarService:
    """Service for interacting with Microsoft Graph Calendar API"""

    def __init__(self, access_token: str):
        """
        Initialize Outlook Calendar service with user's access token.

        Args:
            access_token: OAuth2 access token from user's Microsoft account
        """
        self.access_token = access_token
        self.base_url = "https://graph.microsoft.com/v1.0"
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

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
        """
        Create a new event in Outlook Calendar.

        Args:
            summary: Meeting title
            description: Meeting description
            start_datetime: Start time in ISO 8601 format (e.g., "2025-10-15T14:00:00")
            end_datetime: End time in ISO 8601 format
            attendees: List of attendee email addresses
            timezone: Timezone for the event (e.g., "America/Los_Angeles")
            location: Meeting location (optional)

        Returns:
            Dict with event_id, meeting_link (Teams), and web_link
        """
        try:
            # Build event object for Microsoft Graph
            event = {
                'subject': summary,
                'body': {
                    'contentType': 'HTML',
                    'content': description or ''
                },
                'start': {
                    'dateTime': start_datetime,
                    'timeZone': timezone,
                },
                'end': {
                    'dateTime': end_datetime,
                    'timeZone': timezone,
                },
                'attendees': [
                    {
                        'emailAddress': {'address': email},
                        'type': 'required'
                    }
                    for email in attendees
                ],
                'isOnlineMeeting': True,
                'onlineMeetingProvider': 'teamsForBusiness'
            }

            if location:
                event['location'] = {'displayName': location}

            # Create event in Outlook Calendar
            logger.info(f"📅 Creating event in Outlook Calendar: {summary}")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/me/calendar/events",
                    headers=self.headers,
                    json=event
                )

                # Enhanced error logging
                if response.status_code == 403:
                    logger.error(f"❌ Outlook Calendar API Error - Status: {response.status_code}")
                    logger.error(f"❌ Response Headers: {dict(response.headers)}")
                    error_body = response.json() if response.content else {}
                    logger.error(f"❌ Error Response Body: {error_body}")

                if response.status_code == 401:
                    raise Exception("Outlook access token expired or invalid. Please reconnect Outlook Calendar.")
                elif response.status_code == 403:
                    error_data = response.json() if response.content else {}
                    error_msg = error_data.get('error', {}).get('message', '')
                    raise Exception(f"Permission denied: {error_msg}. Please ensure you have granted calendar permissions.")
                elif response.status_code != 201:
                    error_data = response.json() if response.content else {}
                    raise Exception(f"Outlook Calendar API error: {error_data.get('error', {}).get('message', response.text)}")

                created_event = response.json()
                logger.info(f"✅ Event created successfully: {created_event.get('id')}")

                # Debug: Log what Microsoft returned
                logger.info(f"Created event data: onlineMeeting={created_event.get('onlineMeeting')}, webLink={created_event.get('webLink')}")

                # Extract meeting link (Teams) - safely handle None
                meeting_link = None
                online_meeting = created_event.get('onlineMeeting')
                if online_meeting and isinstance(online_meeting, dict):
                    meeting_link = online_meeting.get('joinUrl')
                    logger.info(f"Teams meeting link: {meeting_link}")
                else:
                    logger.warning("No online meeting data returned by Microsoft Graph API")

                # Fallback: Use web link (Outlook calendar link) if no Teams link
                if not meeting_link:
                    meeting_link = created_event.get('webLink')
                    logger.info(f"Using web link as fallback: {meeting_link}")

                return {
                    'event_id': created_event.get('id'),
                    'meeting_link': meeting_link,
                    'web_link': created_event.get('webLink'),
                    'status': 'confirmed' if created_event.get('isCancelled') == False else 'cancelled'
                }

        except httpx.HTTPError as e:
            logger.error(f"❌ HTTP error creating event: {e}")
            raise Exception(f"Failed to create event: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Error creating event: {e}")
            raise

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
        """
        Update an existing event in Outlook Calendar.

        Args:
            event_id: Outlook Calendar event ID
            summary: Updated meeting title (optional)
            description: Updated description (optional)
            start_datetime: Updated start time (optional)
            end_datetime: Updated end time (optional)
            attendees: Updated attendee list (optional)
            timezone: Updated timezone (optional)
            location: Updated location (optional)

        Returns:
            Dict with updated event details
        """
        try:
            # Build update object with only provided fields
            update_data = {}

            if summary is not None:
                update_data['subject'] = summary

            if description is not None:
                update_data['body'] = {
                    'contentType': 'HTML',
                    'content': description
                }

            if start_datetime is not None and timezone is not None:
                update_data['start'] = {
                    'dateTime': start_datetime,
                    'timeZone': timezone
                }

            if end_datetime is not None and timezone is not None:
                update_data['end'] = {
                    'dateTime': end_datetime,
                    'timeZone': timezone
                }

            if attendees is not None:
                update_data['attendees'] = [
                    {
                        'emailAddress': {'address': email},
                        'type': 'required'
                    }
                    for email in attendees
                ]

            if location is not None:
                update_data['location'] = {'displayName': location}

            # Update event in Outlook Calendar
            logger.info(f"📝 Updating event in Outlook Calendar: {event_id}")

            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.base_url}/me/calendar/events/{event_id}",
                    headers=self.headers,
                    json=update_data
                )

                if response.status_code == 404:
                    raise Exception("Event not found in Outlook Calendar")
                elif response.status_code == 401:
                    raise Exception("Outlook access token expired or invalid")
                elif response.status_code != 200:
                    error_data = response.json() if response.content else {}
                    raise Exception(f"Failed to update event: {error_data.get('error', {}).get('message', response.text)}")

                updated_event = response.json()
                logger.info(f"✅ Event updated successfully: {event_id}")

                # Extract meeting link (safely handle None)
                meeting_link = None
                online_meeting = updated_event.get('onlineMeeting')
                if online_meeting and isinstance(online_meeting, dict):
                    meeting_link = online_meeting.get('joinUrl')

                return {
                    'event_id': updated_event.get('id'),
                    'meeting_link': meeting_link,
                    'web_link': updated_event.get('webLink'),
                    'status': 'confirmed' if updated_event.get('isCancelled') == False else 'cancelled'
                }

        except Exception as e:
            logger.error(f"❌ Error updating event: {e}")
            raise

    async def delete_event(self, event_id: str) -> bool:
        """
        Delete an event from Outlook Calendar.

        Args:
            event_id: Outlook Calendar event ID

        Returns:
            True if deleted successfully
        """
        try:
            logger.info(f"🗑️ Deleting event from Outlook Calendar: {event_id}")

            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.base_url}/me/calendar/events/{event_id}",
                    headers=self.headers
                )

                if response.status_code == 404:
                    logger.warning(f"⚠️ Event {event_id} not found (may have been deleted already)")
                    return True  # Consider it deleted if not found
                elif response.status_code == 401:
                    raise Exception("Outlook access token expired or invalid")
                elif response.status_code != 204:
                    error_data = response.json() if response.content else {}
                    raise Exception(f"Failed to delete event: {error_data.get('error', {}).get('message', response.text)}")

                logger.info(f"✅ Event deleted successfully: {event_id}")
                return True

        except Exception as e:
            logger.error(f"❌ Error deleting event: {e}")
            raise

    async def get_event(self, event_id: str) -> Dict[str, Any]:
        """
        Get a single event from Outlook Calendar.

        Args:
            event_id: Outlook Calendar event ID

        Returns:
            Dict with event details
        """
        try:
            logger.info(f"📅 Fetching event from Outlook Calendar: {event_id}")

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/me/calendar/events/{event_id}",
                    headers=self.headers
                )

                if response.status_code == 404:
                    raise Exception("Event not found in Outlook Calendar")
                elif response.status_code == 401:
                    raise Exception("Outlook access token expired or invalid")
                elif response.status_code != 200:
                    error_data = response.json() if response.content else {}
                    raise Exception(f"Failed to fetch event: {error_data.get('error', {}).get('message', response.text)}")

                event = response.json()

                # Extract meeting link (safely handle None)
                meeting_link = None
                online_meeting = event.get('onlineMeeting')
                if online_meeting and isinstance(online_meeting, dict):
                    meeting_link = online_meeting.get('joinUrl')

                # Extract attendees
                attendees = []
                attendees_list = event.get('attendees', [])
                if attendees_list:
                    for att in attendees_list:
                        if att and 'emailAddress' in att and 'address' in att['emailAddress']:
                            attendees.append(att['emailAddress']['address'])

                # Extract location (safely handle None)
                location = None
                location_obj = event.get('location')
                if location_obj and isinstance(location_obj, dict):
                    location = location_obj.get('displayName')

                # Extract body (safely handle None)
                description = ''
                body_obj = event.get('body')
                if body_obj and isinstance(body_obj, dict):
                    description = body_obj.get('content', '')

                return {
                    'event_id': event.get('id'),
                    'summary': event.get('subject'),
                    'description': description,
                    'start': event.get('start'),
                    'end': event.get('end'),
                    'attendees': attendees,
                    'location': location,
                    'meeting_link': meeting_link,
                    'web_link': event.get('webLink'),
                    'status': 'confirmed' if event.get('isCancelled') == False else 'cancelled'
                }

        except Exception as e:
            logger.error(f"❌ Error fetching event: {e}")
            raise

    async def list_events(
        self,
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List events from Outlook Calendar within a time range.
        Used for syncing FROM Outlook Calendar TO CRM.

        Args:
            time_min: Start time in ISO 8601 format (e.g., "2025-10-01T00:00:00Z")
            time_max: End time in ISO 8601 format
            max_results: Maximum number of events to return

        Returns:
            List of event dictionaries
        """
        try:
            logger.info(f"📅 Fetching events from Outlook Calendar (time_min: {time_min}, time_max: {time_max})")

            # Build query parameters
            params = {
                '$top': max_results,
                '$orderby': 'start/dateTime'
            }

            # Build filter for time range
            filters = []
            if time_min:
                filters.append(f"start/dateTime ge '{time_min}'")
            if time_max:
                filters.append(f"end/dateTime le '{time_max}'")

            if filters:
                params['$filter'] = ' and '.join(filters)

            # Fetch events
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/me/calendar/events",
                    headers=self.headers,
                    params=params
                )

                if response.status_code == 401:
                    raise Exception("Outlook access token expired or invalid")
                elif response.status_code != 200:
                    error_data = response.json() if response.content else {}
                    raise Exception(f"Failed to list events: {error_data.get('error', {}).get('message', response.text)}")

                events_result = response.json()
                events = events_result.get('value', [])

                logger.info(f"✅ Fetched {len(events)} events from Outlook Calendar")

                # Transform to standardized format
                standardized_events = []
                for event in events:
                    # Extract meeting link (safely handle None)
                    meeting_link = None
                    online_meeting = event.get('onlineMeeting')
                    if online_meeting and isinstance(online_meeting, dict):
                        meeting_link = online_meeting.get('joinUrl')

                    # Extract attendees
                    attendees = []
                    attendees_list = event.get('attendees', [])
                    if attendees_list:
                        for att in attendees_list:
                            if att and 'emailAddress' in att and 'address' in att['emailAddress']:
                                attendees.append(att['emailAddress']['address'])

                    # Extract location (safely handle None)
                    location = None
                    location_obj = event.get('location')
                    if location_obj and isinstance(location_obj, dict):
                        location = location_obj.get('displayName')

                    # Extract body (safely handle None)
                    description = ''
                    body_obj = event.get('body')
                    if body_obj and isinstance(body_obj, dict):
                        description = body_obj.get('content', '')

                    standardized_events.append({
                        'event_id': event.get('id'),
                        'summary': event.get('subject'),
                        'description': description,
                        'start': event.get('start'),
                        'end': event.get('end'),
                        'attendees': attendees,
                        'location': location,
                        'meeting_link': meeting_link,
                        'web_link': event.get('webLink'),
                        'status': 'confirmed' if event.get('isCancelled') == False else 'cancelled',
                        'created': event.get('createdDateTime'),
                        'updated': event.get('lastModifiedDateTime')
                    })

                return standardized_events

        except Exception as e:
            logger.error(f"❌ Error listing events: {e}")
            raise
