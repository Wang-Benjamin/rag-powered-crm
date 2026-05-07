"""
Google Calendar Service for creating, updating, and syncing meetings.
Uses REST API with access token (no refresh token needed).
Handles two-way sync between CRM and Google Calendar.
"""

import logging
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class GoogleCalendarService:
    """Service for interacting with Google Calendar API via REST"""

    def __init__(self, access_token: str):
        """
        Initialize Google Calendar service with user's access token.

        Args:
            access_token: OAuth2 access token from user's Google account
        """
        self.access_token = access_token
        self.base_url = "https://www.googleapis.com/calendar/v3"
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
        Create a new event in Google Calendar.

        Args:
            summary: Meeting title
            description: Meeting description
            start_datetime: Start time in ISO 8601 format (e.g., "2025-10-15T14:00:00")
            end_datetime: End time in ISO 8601 format
            attendees: List of attendee email addresses
            timezone: Timezone for the event (e.g., "America/Los_Angeles")
            location: Meeting location (optional)

        Returns:
            Dict with event_id, meeting_link (Google Meet), and html_link
        """
        try:
            # Build event object
            event = {
                'summary': summary,
                'description': description,
                'start': {
                    'dateTime': start_datetime,
                    'timeZone': timezone,
                },
                'end': {
                    'dateTime': end_datetime,
                    'timeZone': timezone,
                },
                'attendees': [{'email': email} for email in attendees],
                'conferenceData': {
                    'createRequest': {
                        'requestId': f'meet-{datetime.now(timezone.utc).timestamp()}',
                        'conferenceSolutionKey': {'type': 'hangoutsMeet'}
                    }
                },
                'reminders': {
                    'useDefault': True
                }
            }

            if location:
                event['location'] = location

            # Create event in Google Calendar
            logger.info(f"📅 Creating event in Google Calendar: {summary}")

            response = requests.post(
                f"{self.base_url}/calendars/primary/events",
                headers=self.headers,
                json=event,
                params={'conferenceDataVersion': 1}  # Required for Google Meet link
            )

            # Enhanced error logging
            if response.status_code == 403:
                logger.error(f"❌ Google Calendar API Error - Status: {response.status_code}")
                logger.error(f"❌ Response Headers: {dict(response.headers)}")
                error_body = response.json() if response.content else {}
                logger.error(f"❌ Error Response Body: {error_body}")

            if response.status_code == 401:
                raise Exception("Google access token expired or invalid. Please reconnect Google Calendar.")
            elif response.status_code == 403:
                # Enhanced error message for scope issues
                error_data = response.json() if response.content else {}
                error_msg = error_data.get('error', {}).get('message', '')
                if 'insufficient' in error_msg.lower() and 'scope' in error_msg.lower():
                    raise Exception("Permission denied: Request had insufficient authentication scopes.. Please ensure Calendar API is enabled and you have granted calendar permissions.")
                raise Exception(f"Permission denied: {error_msg}. Please ensure Calendar API is enabled and you have granted calendar permissions.")
            elif not response.ok:
                error_data = response.json() if response.content else {}
                raise Exception(f"Google Calendar API error: {error_data.get('error', {}).get('message', response.text)}")

            created_event = response.json()
            logger.info(f"✅ Event created successfully: {created_event.get('id')}")

            # Extract meeting link (Google Meet)
            meeting_link = None
            if 'conferenceData' in created_event:
                conference_data = created_event['conferenceData']
                if 'entryPoints' in conference_data:
                    for entry_point in conference_data['entryPoints']:
                        if entry_point.get('entryPointType') == 'video':
                            meeting_link = entry_point.get('uri')
                            break

            return {
                'event_id': created_event.get('id'),
                'meeting_link': meeting_link or created_event.get('hangoutLink'),
                'html_link': created_event.get('htmlLink'),
                'status': created_event.get('status')
            }

        except requests.RequestException as e:
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
        Update an existing event in Google Calendar.

        Args:
            event_id: Google Calendar event ID
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
            # First, get the existing event
            logger.info(f"📅 Fetching event from Google Calendar: {event_id}")

            get_response = requests.get(
                f"{self.base_url}/calendars/primary/events/{event_id}",
                headers=self.headers
            )

            if get_response.status_code == 404:
                raise Exception("Event not found in Google Calendar")
            elif get_response.status_code == 401:
                raise Exception("Google access token expired or invalid")
            elif not get_response.ok:
                raise Exception(f"Failed to fetch event: {get_response.text}")

            existing_event = get_response.json()

            # Update only the fields that were provided
            if summary is not None:
                existing_event['summary'] = summary

            if description is not None:
                existing_event['description'] = description

            if start_datetime is not None and timezone is not None:
                existing_event['start'] = {
                    'dateTime': start_datetime,
                    'timeZone': timezone
                }

            if end_datetime is not None and timezone is not None:
                existing_event['end'] = {
                    'dateTime': end_datetime,
                    'timeZone': timezone
                }

            if attendees is not None:
                existing_event['attendees'] = [{'email': email} for email in attendees]

            if location is not None:
                existing_event['location'] = location

            # Update event in Google Calendar
            logger.info(f"📝 Updating event in Google Calendar: {event_id}")

            update_response = requests.put(
                f"{self.base_url}/calendars/primary/events/{event_id}",
                headers=self.headers,
                json=existing_event
            )

            if not update_response.ok:
                raise Exception(f"Failed to update event: {update_response.text}")

            updated_event = update_response.json()
            logger.info(f"✅ Event updated successfully: {event_id}")

            # Extract meeting link
            meeting_link = None
            if 'conferenceData' in updated_event:
                conference_data = updated_event['conferenceData']
                if 'entryPoints' in conference_data:
                    for entry_point in conference_data['entryPoints']:
                        if entry_point.get('entryPointType') == 'video':
                            meeting_link = entry_point.get('uri')
                            break

            return {
                'event_id': updated_event.get('id'),
                'meeting_link': meeting_link or updated_event.get('hangoutLink'),
                'html_link': updated_event.get('htmlLink'),
                'status': updated_event.get('status')
            }

        except Exception as e:
            logger.error(f"❌ Error updating event: {e}")
            raise

    async def delete_event(self, event_id: str) -> bool:
        """
        Delete an event from Google Calendar.

        Args:
            event_id: Google Calendar event ID

        Returns:
            True if deleted successfully
        """
        try:
            logger.info(f"🗑️ Deleting event from Google Calendar: {event_id}")

            response = requests.delete(
                f"{self.base_url}/calendars/primary/events/{event_id}",
                headers=self.headers
            )

            if response.status_code == 404:
                logger.warning(f"⚠️ Event {event_id} not found (may have been deleted already)")
                return True  # Consider it deleted if not found
            elif response.status_code == 401:
                raise Exception("Google access token expired or invalid")
            elif response.status_code == 410:
                logger.warning(f"⚠️ Event {event_id} already deleted")
                return True
            elif not response.ok:
                raise Exception(f"Failed to delete event: {response.text}")

            logger.info(f"✅ Event deleted successfully: {event_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Error deleting event: {e}")
            raise

    async def get_event(self, event_id: str) -> Dict[str, Any]:
        """
        Get a single event from Google Calendar.

        Args:
            event_id: Google Calendar event ID

        Returns:
            Dict with event details
        """
        try:
            logger.info(f"📅 Fetching event from Google Calendar: {event_id}")

            response = requests.get(
                f"{self.base_url}/calendars/primary/events/{event_id}",
                headers=self.headers
            )

            if response.status_code == 404:
                raise Exception("Event not found in Google Calendar")
            elif response.status_code == 401:
                raise Exception("Google access token expired or invalid")
            elif not response.ok:
                raise Exception(f"Failed to fetch event: {response.text}")

            event = response.json()

            # Extract meeting link
            meeting_link = None
            if 'conferenceData' in event:
                conference_data = event['conferenceData']
                if 'entryPoints' in conference_data:
                    for entry_point in conference_data['entryPoints']:
                        if entry_point.get('entryPointType') == 'video':
                            meeting_link = entry_point.get('uri')
                            break

            return {
                'event_id': event.get('id'),
                'summary': event.get('summary'),
                'description': event.get('description'),
                'start': event.get('start'),
                'end': event.get('end'),
                'attendees': [att.get('email') for att in event.get('attendees', [])],
                'location': event.get('location'),
                'meeting_link': meeting_link or event.get('hangoutLink'),
                'html_link': event.get('htmlLink'),
                'status': event.get('status')
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
        List events from Google Calendar within a time range.
        Used for syncing FROM Google Calendar TO CRM.

        Args:
            time_min: Start time in RFC3339 format (e.g., "2025-10-01T00:00:00Z")
            time_max: End time in RFC3339 format
            max_results: Maximum number of events to return

        Returns:
            List of event dictionaries
        """
        try:
            logger.info(f"📅 Fetching events from Google Calendar (time_min: {time_min}, time_max: {time_max})")

            # Build request parameters
            params = {
                'maxResults': max_results,
                'singleEvents': True,
                'orderBy': 'startTime'
            }

            if time_min:
                params['timeMin'] = time_min
            if time_max:
                params['timeMax'] = time_max

            # Fetch events
            response = requests.get(
                f"{self.base_url}/calendars/primary/events",
                headers=self.headers,
                params=params
            )

            if response.status_code == 401:
                raise Exception("Google access token expired or invalid")
            elif not response.ok:
                error_data = response.json() if response.content else {}
                raise Exception(f"Failed to list events: {error_data.get('error', {}).get('message', response.text)}")

            events_result = response.json()
            events = events_result.get('items', [])

            logger.info(f"✅ Fetched {len(events)} events from Google Calendar")

            # Transform to standardized format
            standardized_events = []
            for event in events:
                # Extract meeting link
                meeting_link = None
                if 'conferenceData' in event:
                    conference_data = event['conferenceData']
                    if 'entryPoints' in conference_data:
                        for entry_point in conference_data['entryPoints']:
                            if entry_point.get('entryPointType') == 'video':
                                meeting_link = entry_point.get('uri')
                                break

                standardized_events.append({
                    'event_id': event.get('id'),
                    'summary': event.get('summary'),
                    'description': event.get('description'),
                    'start': event.get('start'),
                    'end': event.get('end'),
                    'attendees': [att.get('email') for att in event.get('attendees', [])],
                    'location': event.get('location'),
                    'meeting_link': meeting_link or event.get('hangoutLink'),
                    'html_link': event.get('htmlLink'),
                    'status': event.get('status'),
                    'created': event.get('created'),
                    'updated': event.get('updated')
                })

            return standardized_events

        except Exception as e:
            logger.error(f"❌ Error listing events: {e}")
            raise
