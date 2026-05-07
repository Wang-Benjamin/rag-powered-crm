"""
Meetings Router - Handles meeting CRUD and calendar integration endpoints
"""

import logging
import json
from fastapi import APIRouter, HTTPException, Depends, Header
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone

from service_core.db import get_tenant_connection
from services.cache_service import clear_cache
from models.crm_models import paginated_response

logger = logging.getLogger(__name__)
router = APIRouter()

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class MeetingCreate(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: str  # ISO 8601 format
    end_time: str    # ISO 8601 format
    attendees: List[str] = []  # Email addresses
    location: Optional[str] = None
    timezone: str = "UTC"  # Browser timezone from frontend

class MeetingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    attendees: Optional[List[str]] = None
    location: Optional[str] = None
    timezone: Optional[str] = None

class MeetingResponse(BaseModel):
    interaction_id: int
    customer_id: int
    employee_id: int
    title: str
    description: Optional[str]
    start_time: str
    end_time: str
    attendees: List[str]
    location: Optional[str]
    meeting_link: Optional[str]
    google_event_id: Optional[str]
    timezone: str
    created_at: datetime
    updated_at: datetime

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def detect_calendar_provider(user_email: str, conn) -> str:
    """
    Detect which calendar provider the user has connected (Google or Microsoft).

    Args:
        user_email: User's email address
        conn: asyncpg connection

    Returns:
        'google', 'microsoft', or None if no provider connected
    """
    try:
        result = await conn.fetchrow("""
            SELECT provider FROM oauth_tokens
            WHERE user_email = $1 AND provider IN ('google', 'microsoft')
            ORDER BY updated_at DESC
            LIMIT 1
        """, user_email)

        if result:
            return result['provider']

        return None

    except Exception as e:
        logger.error(f"Error detecting calendar provider: {e}")
        return None

def format_meeting_content(meeting_data: MeetingCreate) -> str:
    """Convert meeting data to JSON string for storage in content field"""
    content = {
        "title": meeting_data.title,
        "description": meeting_data.description,
        "start_time": meeting_data.start_time,
        "end_time": meeting_data.end_time,
        "attendees": meeting_data.attendees,
        "location": meeting_data.location,
        "timezone": meeting_data.timezone
    }
    return json.dumps(content)

def parse_meeting_content(content: str) -> dict:
    """Parse JSON meeting content from interaction_details"""
    if not content:
        return {}
    try:
        data = json.loads(content)
        return data
    except json.JSONDecodeError:
        # Handle legacy plain text meeting content
        logger.warning(f"Failed to parse meeting content as JSON, treating as legacy text")
        return {
            "title": "Legacy Meeting",
            "description": content,
            "start_time": "",  # Return empty string instead of None
            "end_time": "",    # Return empty string instead of None
            "attendees": [],
            "location": None,
            "timezone": "UTC"
        }

# ============================================================================
# MEETING ENDPOINTS
# ============================================================================

@router.post("/customers/{customer_id}/meetings", response_model=MeetingResponse)
async def create_customer_meeting(
    customer_id: int,
    meeting_data: MeetingCreate,
    google_access_token: Optional[str] = Header(default=None, alias="X-Google-Access-Token"),
    tenant: tuple = Depends(get_tenant_connection)
) -> MeetingResponse:
    """
    Create a new meeting for a customer in both Calendar (Google/Outlook) and CRM with auto-refresh tokens.
    Two-way sync: CRM -> Calendar (Google or Microsoft)

    NEW: Now automatically detects whether user has Google or Microsoft calendar connected.
    - If google_access_token is provided: Uses the old method (for backward compatibility)
    - If not provided: Auto-detects provider and uses stored tokens from database with auto-refresh

    Steps:
    1. Validate customer exists
    2. Get employee_id from authenticated user
    3. Detect calendar provider (Google or Microsoft)
    4. Create event in Calendar FIRST (auto-refreshes token if expired)
    5. Store meeting in interaction_details with type='meet'
    6. Return meeting response with meeting link (Google Meet or Teams)
    """
    try:
        conn, user = tenant
        user_email = user.get('email', '')
        logger.info(f"Creating meeting for customer {customer_id} by user {user_email}")

        # Get employee_id for the authenticated user
        row = await conn.fetchrow(
            "SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1", user_email
        )
        employee_id = row["employee_id"] if row else None
        if not employee_id:
            raise HTTPException(status_code=404, detail="Employee not found")

        # Verify customer exists and get customer name
        customer = await conn.fetchrow(
            "SELECT client_id, name FROM clients WHERE client_id = $1", customer_id
        )
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")

        customer_name = dict(customer).get('name', f'ID {customer_id}')

        # Verify employee-client link exists (required for foreign key constraint)
        link = await conn.fetchrow("""
            SELECT 1 FROM employee_client_links
            WHERE employee_id = $1 AND client_id = $2
        """, employee_id, customer_id)
        if not link:
            raise HTTPException(
                status_code=403,
                detail={"code": "MEETING_PERMISSION_DENIED", "message": f"You don't have the right to schedule meetings for customer '{customer_name}'."}
            )

        # Step 1: Detect calendar provider and create appropriate service
        calendar_event_id = None
        meeting_link = None
        provider = None

        if google_access_token:
            # Legacy method: use provided token (may expire after 1 hour)
            from services.calendar.google_calendar_service import GoogleCalendarService
            logger.info("Using legacy GoogleCalendarService with provided token")
            calendar_service = GoogleCalendarService(google_access_token)
            provider = 'google'
        else:
            # New method: auto-detect provider and use stored token with auto-refresh
            provider = await detect_calendar_provider(user_email, conn)

            if not provider:
                raise HTTPException(
                    status_code=400,
                    detail={"code": "CALENDAR_PROVIDER_NOT_CONNECTED", "message": "No calendar provider connected. Please connect Google Calendar or Outlook Calendar first."}
                )

            logger.info(f"Detected calendar provider: {provider}")

            if provider == 'google':
                from services.calendar.google_calendar_service_v2 import GoogleCalendarServiceV2
                from auth.providers import auth_provider
                logger.info("Using GoogleCalendarServiceV2 with auto-refresh")
                calendar_service = GoogleCalendarServiceV2(
                    user_email=user_email,
                    conn=conn,
                    auth_provider=auth_provider
                )
            elif provider == 'microsoft':
                from services.calendar.outlook_calendar_service_v2 import OutlookCalendarServiceV2
                from auth.providers import auth_provider
                logger.info("Using OutlookCalendarServiceV2 with auto-refresh")
                calendar_service = OutlookCalendarServiceV2(
                    user_email=user_email,
                    conn=conn,
                    auth_provider=auth_provider
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail={"code": "CALENDAR_PROVIDER_UNSUPPORTED", "message": f"Unsupported calendar provider: {provider}"}
                )

        # Create event in calendar
        calendar_event = await calendar_service.create_event(
            summary=meeting_data.title,
            description=meeting_data.description or "",
            start_datetime=meeting_data.start_time,
            end_datetime=meeting_data.end_time,
            attendees=meeting_data.attendees,
            timezone=meeting_data.timezone,
            location=meeting_data.location
        )

        calendar_event_id = calendar_event['event_id']
        meeting_link = calendar_event.get('meeting_link')

        logger.info(f"Event created in {provider.capitalize()} Calendar: {calendar_event_id}")

        # Step 2: Store in CRM database with calendar_event_id
        meeting_content = format_meeting_content(meeting_data)

        # Add meeting_link and provider to content
        content_dict = json.loads(meeting_content)
        content_dict['meeting_link'] = meeting_link
        content_dict['calendar_provider'] = provider
        meeting_content = json.dumps(content_dict)

        # Determine source based on provider
        source = 'google_calendar' if provider == 'google' else 'outlook_calendar'

        new_meeting = await conn.fetchrow("""
            INSERT INTO interaction_details
            (customer_id, employee_id, type, content, google_calendar_event_id, source, theme, created_at, updated_at)
            VALUES ($1, $2, 'meet', $3, $4, $5, $6, NOW(), NOW())
            RETURNING interaction_id, created_at, updated_at
        """, customer_id, employee_id, meeting_content, calendar_event_id, source, meeting_data.title)

        logger.info(f"Meeting stored in CRM: interaction_id={new_meeting['interaction_id']}")

        # Fire-and-forget: generate embedding for RAG search
        try:
            import asyncio
            from services.rag.embedding_sync_service import embed_single_interaction
            asyncio.ensure_future(embed_single_interaction(user_email, new_meeting['interaction_id'], meeting_content))
        except Exception as embed_err:
            logger.debug(f"Meeting embedding skipped: {embed_err}")

        # Clear interactions cache for this customer
        clear_cache(f"customer_id={customer_id}")
        clear_cache("get_recent_interactions")

        # Step 3: Return meeting response
        return MeetingResponse(
            interaction_id=new_meeting['interaction_id'],
            customer_id=customer_id,
            employee_id=employee_id,
            title=meeting_data.title,
            description=meeting_data.description,
            start_time=meeting_data.start_time,
            end_time=meeting_data.end_time,
            attendees=meeting_data.attendees,
            location=meeting_data.location,
            meeting_link=meeting_link,
            google_event_id=calendar_event_id,
            timezone=meeting_data.timezone,
            created_at=new_meeting['created_at'],
            updated_at=new_meeting['updated_at']
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating customer meeting: {e}")
        logger.error("Full traceback:", exc_info=True)
        error_msg = str(e)
        if 'No valid Google access token' in error_msg or 'reconnect' in error_msg.lower():
            raise HTTPException(status_code=400, detail={"code": "CALENDAR_RECONNECT_REQUIRED", "message": error_msg})
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/meetings")
async def get_all_meetings(
    page: Optional[int] = None,
    per_page: Optional[int] = None,
    tenant: tuple = Depends(get_tenant_connection)
):
    """
    Get all meetings for the authenticated employee across all customers.
    """
    try:
        conn, user = tenant
        user_email = user.get('email', '')
        logger.info(f"Getting all meetings for user {user_email}")

        row = await conn.fetchrow(
            "SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1", user_email
        )
        employee_id = row["employee_id"] if row else None
        if not employee_id:
            raise HTTPException(status_code=404, detail="Employee not found")

        if page is not None and per_page is not None:
            offset = (page - 1) * per_page
            meetings = await conn.fetch("""
                SELECT *, COUNT(*) OVER() AS _total_count
                FROM (
                    SELECT interaction_id, customer_id, employee_id, content,
                           google_calendar_event_id, created_at, updated_at
                    FROM interaction_details
                    WHERE employee_id = $1 AND type = 'meet'
                    ORDER BY created_at DESC
                ) _sub
                LIMIT $2 OFFSET $3
            """, employee_id, per_page, offset)
        else:
            meetings = await conn.fetch("""
                SELECT interaction_id, customer_id, employee_id, content,
                       google_calendar_event_id, created_at, updated_at
                FROM interaction_details
                WHERE employee_id = $1 AND type = 'meet'
                ORDER BY created_at DESC
            """, employee_id)

        total = None
        if page is not None and per_page is not None and meetings:
            total = meetings[0]['_total_count']

        result = []
        for meeting in meetings:
            m = dict(meeting)
            m.pop('_total_count', None)
            content = parse_meeting_content(m['content'])

            result.append(MeetingResponse(
                interaction_id=m['interaction_id'],
                customer_id=m['customer_id'],
                employee_id=m['employee_id'],
                title=content.get('title', 'Untitled Meeting'),
                description=content.get('description'),
                start_time=content.get('start_time', ''),
                end_time=content.get('end_time', ''),
                attendees=content.get('attendees', []),
                location=content.get('location'),
                meeting_link=content.get('meeting_link'),
                google_event_id=m['google_calendar_event_id'],
                timezone=content.get('timezone', 'UTC'),
                created_at=m['created_at'],
                updated_at=m['updated_at']
            ))

        if total is not None:
            return paginated_response(result, total, page, per_page, key="meetings")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting all meetings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/customers/{customer_id}/meetings")
async def get_customer_meetings(
    customer_id: int,
    page: Optional[int] = None,
    per_page: Optional[int] = None,
    tenant: tuple = Depends(get_tenant_connection)
):
    """
    Get all meetings for a specific customer.
    """
    try:
        conn, user = tenant
        user_email = user.get('email', '')
        logger.info(f"Getting meetings for customer {customer_id} by user {user_email}")

        if page is not None and per_page is not None:
            offset = (page - 1) * per_page
            meetings = await conn.fetch("""
                SELECT *, COUNT(*) OVER() AS _total_count
                FROM (
                    SELECT interaction_id, customer_id, employee_id, content,
                           google_calendar_event_id, created_at, updated_at
                    FROM interaction_details
                    WHERE customer_id = $1 AND type = 'meet'
                    ORDER BY created_at DESC
                ) _sub
                LIMIT $2 OFFSET $3
            """, customer_id, per_page, offset)
        else:
            meetings = await conn.fetch("""
                SELECT interaction_id, customer_id, employee_id, content,
                       google_calendar_event_id, created_at, updated_at
                FROM interaction_details
                WHERE customer_id = $1 AND type = 'meet'
                ORDER BY created_at DESC
            """, customer_id)

        total = None
        if page is not None and per_page is not None and meetings:
            total = meetings[0]['_total_count']

        result = []
        for meeting in meetings:
            m = dict(meeting)
            m.pop('_total_count', None)
            content = parse_meeting_content(m['content'])

            result.append(MeetingResponse(
                interaction_id=m['interaction_id'],
                customer_id=m['customer_id'],
                employee_id=m['employee_id'],
                title=content.get('title', 'Untitled Meeting'),
                description=content.get('description'),
                start_time=content.get('start_time', ''),
                end_time=content.get('end_time', ''),
                attendees=content.get('attendees', []),
                location=content.get('location'),
                meeting_link=content.get('meeting_link'),
                google_event_id=m['google_calendar_event_id'],
                timezone=content.get('timezone', 'UTC'),
                created_at=m['created_at'],
                updated_at=m['updated_at']
            ))

        if total is not None:
            return paginated_response(result, total, page, per_page, key="meetings")

        return result

    except Exception as e:
        logger.error(f"Error getting customer meetings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/meetings/{interaction_id}", response_model=MeetingResponse)
async def get_meeting_by_id(
    interaction_id: int,
    tenant: tuple = Depends(get_tenant_connection)
) -> MeetingResponse:
    """Get single meeting by interaction_id"""
    try:
        conn, user = tenant
        user_email = user.get('email', '')
        logger.info(f"Getting meeting {interaction_id} by user {user_email}")

        meeting = await conn.fetchrow("""
            SELECT interaction_id, customer_id, employee_id, content,
                   google_calendar_event_id, created_at, updated_at
            FROM interaction_details
            WHERE interaction_id = $1 AND type = 'meet'
        """, interaction_id)

        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")

        content = parse_meeting_content(meeting['content'])

        return MeetingResponse(
            interaction_id=meeting['interaction_id'],
            customer_id=meeting['customer_id'],
            employee_id=meeting['employee_id'],
            title=content.get('title', 'Untitled Meeting'),
            description=content.get('description'),
            start_time=content.get('start_time', ''),
            end_time=content.get('end_time', ''),
            attendees=content.get('attendees', []),
            location=content.get('location'),
            meeting_link=content.get('meeting_link'),
            google_event_id=meeting['google_calendar_event_id'],
            timezone=content.get('timezone', 'UTC'),
            created_at=meeting['created_at'],
            updated_at=meeting['updated_at']
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting meeting: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/meetings/{interaction_id}", response_model=MeetingResponse)
async def update_meeting(
    interaction_id: int,
    meeting_data: MeetingUpdate,
    google_access_token: Optional[str] = Header(default=None, alias="X-Google-Access-Token"),
    tenant: tuple = Depends(get_tenant_connection)
) -> MeetingResponse:
    """
    Update meeting in both Calendar (Google/Outlook) and CRM with auto-refresh tokens.
    Two-way sync: CRM -> Calendar (Google or Microsoft)

    NEW: Now automatically detects calendar provider from stored meeting data.
    - If google_access_token is provided: Uses the old method (for backward compatibility)
    - If not provided: Auto-detects provider from meeting content and uses stored tokens with auto-refresh

    Steps:
    1. Get meeting from interaction_details
    2. Verify employee owns this meeting
    3. Detect calendar provider from meeting content
    4. Update in Calendar using event_id (auto-refreshes token if expired)
    5. Update interaction_details record
    6. Return updated meeting
    """
    try:
        conn, user = tenant
        user_email = user.get('email', '')
        logger.info(f"Updating meeting {interaction_id} by user {user_email}")

        # Get employee_id
        row = await conn.fetchrow(
            "SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1", user_email
        )
        employee_id = row["employee_id"] if row else None
        if not employee_id:
            raise HTTPException(status_code=404, detail="Employee not found")

        # Get existing meeting
        existing_meeting = await conn.fetchrow("""
            SELECT interaction_id, customer_id, employee_id, content,
                   google_calendar_event_id, created_at
            FROM interaction_details
            WHERE interaction_id = $1 AND type = 'meet'
        """, interaction_id)

        if not existing_meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")

        # Verify ownership
        if existing_meeting['employee_id'] != employee_id:
            raise HTTPException(status_code=403, detail={"code": "MEETING_PERMISSION_DENIED", "message": "You do not have permission to modify this meeting."})

        # Verify employee-client link exists (authorization check)
        customer_id = existing_meeting['customer_id']
        link = await conn.fetchrow("""
            SELECT 1 FROM employee_client_links
            WHERE employee_id = $1 AND client_id = $2
        """, employee_id, customer_id)
        if not link:
            raise HTTPException(
                status_code=403,
                detail={"code": "MEETING_PERMISSION_DENIED", "message": "You don't have the right to modify meetings for this customer."}
            )

        calendar_event_id = existing_meeting['google_calendar_event_id']
        existing_content = parse_meeting_content(existing_meeting['content'])

        # Detect provider from existing content or user's current setup
        provider = existing_content.get('calendar_provider')
        if not provider:
            # Fallback: detect from current user setup
            provider = await detect_calendar_provider(user_email, conn)
            if not provider:
                provider = 'google'  # Default to Google for backward compatibility

        logger.info(f"Using calendar provider: {provider}")

        # Step 1: Create appropriate calendar service and update event
        if google_access_token:
            # Legacy method: use provided token (may expire after 1 hour)
            from services.calendar.google_calendar_service import GoogleCalendarService
            logger.info("Using legacy GoogleCalendarService with provided token")
            calendar_service = GoogleCalendarService(google_access_token)
        else:
            # New method: use stored token with auto-refresh
            if provider == 'google':
                from services.calendar.google_calendar_service_v2 import GoogleCalendarServiceV2
                from auth.providers import auth_provider
                logger.info("Using GoogleCalendarServiceV2 with auto-refresh")
                calendar_service = GoogleCalendarServiceV2(
                    user_email=user_email,
                    conn=conn,
                    auth_provider=auth_provider
                )
            elif provider == 'microsoft':
                from services.calendar.outlook_calendar_service_v2 import OutlookCalendarServiceV2
                from auth.providers import auth_provider
                logger.info("Using OutlookCalendarServiceV2 with auto-refresh")
                calendar_service = OutlookCalendarServiceV2(
                    user_email=user_email,
                    conn=conn,
                    auth_provider=auth_provider
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail={"code": "CALENDAR_PROVIDER_UNSUPPORTED", "message": f"Unsupported calendar provider: {provider}"}
                )

        # Only pass fields that were provided
        update_kwargs = {}
        if meeting_data.title is not None:
            update_kwargs['summary'] = meeting_data.title
        if meeting_data.description is not None:
            update_kwargs['description'] = meeting_data.description
        if meeting_data.start_time is not None and meeting_data.timezone is not None:
            update_kwargs['start_datetime'] = meeting_data.start_time
            update_kwargs['timezone'] = meeting_data.timezone
        if meeting_data.end_time is not None and meeting_data.timezone is not None:
            update_kwargs['end_datetime'] = meeting_data.end_time
        if meeting_data.attendees is not None:
            update_kwargs['attendees'] = meeting_data.attendees
        if meeting_data.location is not None:
            update_kwargs['location'] = meeting_data.location

        google_event = await calendar_service.update_event(
            event_id=calendar_event_id,
            **update_kwargs
        )

        logger.info(f"Event updated in {provider.capitalize()} Calendar: {calendar_event_id}")

        # Step 2: Update in CRM database
        # Merge updated fields with existing content
        updated_content = existing_content.copy()
        if meeting_data.title is not None:
            updated_content['title'] = meeting_data.title
        if meeting_data.description is not None:
            updated_content['description'] = meeting_data.description
        if meeting_data.start_time is not None:
            updated_content['start_time'] = meeting_data.start_time
        if meeting_data.end_time is not None:
            updated_content['end_time'] = meeting_data.end_time
        if meeting_data.attendees is not None:
            updated_content['attendees'] = meeting_data.attendees
        if meeting_data.location is not None:
            updated_content['location'] = meeting_data.location
        if meeting_data.timezone is not None:
            updated_content['timezone'] = meeting_data.timezone

        # Update meeting link if returned from Google
        if google_event.get('meeting_link'):
            updated_content['meeting_link'] = google_event['meeting_link']

        result = await conn.fetchrow("""
            UPDATE interaction_details
            SET content = $1, updated_at = NOW()
            WHERE interaction_id = $2
            RETURNING updated_at
        """, json.dumps(updated_content), interaction_id)

        logger.info(f"Meeting updated in CRM: {interaction_id}")

        # Clear interactions cache for this customer
        clear_cache(f"customer_id={existing_meeting['customer_id']}")
        clear_cache("get_recent_interactions")

        return MeetingResponse(
            interaction_id=interaction_id,
            customer_id=existing_meeting['customer_id'],
            employee_id=existing_meeting['employee_id'],
            title=updated_content.get('title', ''),
            description=updated_content.get('description'),
            start_time=updated_content.get('start_time', ''),
            end_time=updated_content.get('end_time', ''),
            attendees=updated_content.get('attendees', []),
            location=updated_content.get('location'),
            meeting_link=updated_content.get('meeting_link'),
            google_event_id=calendar_event_id,
            timezone=updated_content.get('timezone', 'UTC'),
            created_at=existing_meeting['created_at'],
            updated_at=result['updated_at']
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating meeting: {e}")
        logger.error("Full traceback:", exc_info=True)
        error_msg = str(e)
        if 'No valid Google access token' in error_msg or 'reconnect' in error_msg.lower():
            raise HTTPException(status_code=400, detail={"code": "CALENDAR_RECONNECT_REQUIRED", "message": error_msg})
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/meetings/{interaction_id}")
async def delete_meeting(
    interaction_id: int,
    google_access_token: Optional[str] = Header(default=None, alias="X-Google-Access-Token"),
    tenant: tuple = Depends(get_tenant_connection)
):
    """
    Hard delete meeting from both Google Calendar and CRM with auto-refresh tokens.
    Two-way sync: CRM -> Google Calendar

    NEW: Now uses stored OAuth tokens with auto-refresh.
    - If google_access_token is provided: Uses the old method (for backward compatibility)
    - If not provided: Uses stored tokens from database with auto-refresh

    Steps:
    1. Get meeting from interaction_details
    2. Verify employee owns this meeting
    3. Delete from Google Calendar using google_event_id (auto-refreshes token if expired)
    4. Hard delete from interaction_details
    5. Return success status
    """
    try:
        conn, user = tenant
        user_email = user.get('email', '')
        logger.info(f"Deleting meeting {interaction_id} by user {user_email}")

        # Get employee_id
        row = await conn.fetchrow(
            "SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1", user_email
        )
        employee_id = row["employee_id"] if row else None
        if not employee_id:
            raise HTTPException(status_code=404, detail="Employee not found")

        # Get meeting
        meeting = await conn.fetchrow("""
            SELECT google_calendar_event_id, employee_id, customer_id, content
            FROM interaction_details
            WHERE interaction_id = $1 AND type = 'meet'
        """, interaction_id)

        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")

        # Verify ownership
        if meeting['employee_id'] != employee_id:
            raise HTTPException(status_code=403, detail={"code": "MEETING_PERMISSION_DENIED", "message": "You do not have permission to modify this meeting."})

        calendar_event_id = meeting['google_calendar_event_id']
        customer_id = meeting['customer_id']
        meeting_content = parse_meeting_content(meeting['content'])

        # Detect provider from meeting content or user's current setup
        provider = meeting_content.get('calendar_provider')
        if not provider:
            provider = await detect_calendar_provider(user_email, conn)
            if not provider:
                provider = 'google'  # Default to Google for backward compatibility

        logger.info(f"Using calendar provider: {provider}")

        # Step 1: Delete from Calendar FIRST
        if google_access_token:
            # Legacy method: use provided token (may expire after 1 hour)
            from services.calendar.google_calendar_service import GoogleCalendarService
            logger.info("Using legacy GoogleCalendarService with provided token")
            calendar_service = GoogleCalendarService(google_access_token)
        else:
            # New method: use stored token with auto-refresh
            if provider == 'google':
                from services.calendar.google_calendar_service_v2 import GoogleCalendarServiceV2
                from auth.providers import auth_provider
                logger.info("Using GoogleCalendarServiceV2 with auto-refresh")
                calendar_service = GoogleCalendarServiceV2(
                    user_email=user_email,
                    conn=conn,
                    auth_provider=auth_provider
                )
            elif provider == 'microsoft':
                from services.calendar.outlook_calendar_service_v2 import OutlookCalendarServiceV2
                from auth.providers import auth_provider
                logger.info("Using OutlookCalendarServiceV2 with auto-refresh")
                calendar_service = OutlookCalendarServiceV2(
                    user_email=user_email,
                    conn=conn,
                    auth_provider=auth_provider
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail={"code": "CALENDAR_PROVIDER_UNSUPPORTED", "message": f"Unsupported calendar provider: {provider}"}
                )

        await calendar_service.delete_event(calendar_event_id)

        logger.info(f"Event deleted from {provider.capitalize()} Calendar: {calendar_event_id}")

        # Step 2: Hard delete from CRM database
        await conn.execute("""
            DELETE FROM interaction_details
            WHERE interaction_id = $1
        """, interaction_id)

        logger.info(f"Meeting deleted from CRM: {interaction_id}")

        # Clear interactions cache for this customer
        clear_cache(f"customer_id={customer_id}")
        clear_cache("get_recent_interactions")

        return {
            "success": True,
            "message": f"Meeting deleted from both {provider.capitalize()} Calendar and CRM"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting meeting: {e}")
        logger.error("Full traceback:", exc_info=True)
        error_msg = str(e)
        if 'No valid Google access token' in error_msg or 'reconnect' in error_msg.lower():
            raise HTTPException(status_code=400, detail={"code": "CALENDAR_RECONNECT_REQUIRED", "message": error_msg})
        raise HTTPException(status_code=500, detail="Internal server error")
