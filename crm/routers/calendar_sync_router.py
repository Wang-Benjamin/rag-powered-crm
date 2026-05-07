"""
Calendar Sync Router - Handles Google/Outlook Calendar sync to CRM
"""

import asyncio
import logging
import json
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Header
from datetime import datetime, timedelta, timezone

from service_core.db import get_tenant_connection
from models.crm_models import GoogleCalendarSyncRequest
from routers.meetings_router import detect_calendar_provider

logger = logging.getLogger(__name__)
router = APIRouter()

# ============================================================================
# GOOGLE CALENDAR SYNC ENDPOINTS
# ============================================================================

@router.post("/customers/{customer_id}/sync-google-calendar")
async def sync_google_calendar_to_crm(
    customer_id: int,
    google_access_token: Optional[str] = Header(default=None, alias="X-Google-Access-Token"),
    sync_request: GoogleCalendarSyncRequest = GoogleCalendarSyncRequest(),
    tenant: tuple = Depends(get_tenant_connection)
):
    """
    Sync ALL meetings FROM Calendar (Google/Outlook) TO CRM for a specific customer.
    One-way sync: Calendar → CRM

    NO FILTERING - syncs all calendar events regardless of attendees.

    - If google_access_token is provided: Uses the old method (for backward compatibility)
    - If not provided: Auto-detects provider and uses stored tokens from database with auto-refresh

    Steps:
    1. Get employee_id from authenticated user
    2. Detect calendar provider
    3. Fetch ALL events from Calendar within time range
    4. For each event:
       - Check if google_event_id already exists in interaction_details
       - If not exists: create new meeting record linked to this customer
    5. Return sync summary
    """
    try:
        conn, user = tenant
        user_email = user.get('email', '')
        logger.info(f"🔄 Syncing ALL Calendar events for customer {customer_id} by user {user_email}")

        # Get employee_id
        row = await conn.fetchrow("SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1", user_email)
        employee_id = row["employee_id"] if row else None
        if not employee_id:
            raise HTTPException(status_code=404, detail="Employee not found")

        # Verify customer exists
        customer_row = await conn.fetchrow("SELECT client_id FROM clients WHERE client_id = $1", customer_id)
        if not customer_row:
            raise HTTPException(status_code=404, detail="Customer not found")

        # Step 1: Detect calendar provider and create appropriate service
        provider = None
        if google_access_token:
            # Legacy method: use provided token (may expire after 1 hour)
            from services.calendar.google_calendar_service import GoogleCalendarService
            logger.info("Using legacy GoogleCalendarService with provided token")
            calendar_service = GoogleCalendarService(google_access_token)
            provider = 'google'
        else:
            # Auto-detect provider and use stored token with auto-refresh
            provider = await detect_calendar_provider(user_email, conn)

            if not provider:
                raise HTTPException(
                    status_code=400,
                    detail="No calendar provider connected. Please connect Google Calendar or Outlook Calendar first."
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
                    detail=f"Unsupported calendar provider: {provider}"
                )

        # Default time range: 30 days ago to 90 days future
        time_min = sync_request.time_min or (datetime.now(timezone.utc) - timedelta(days=30)).isoformat().replace('+00:00', 'Z')
        time_max = sync_request.time_max or (datetime.now(timezone.utc) + timedelta(days=90)).isoformat().replace('+00:00', 'Z')

        events = await calendar_service.list_events(
            time_min=time_min,
            time_max=time_max,
            max_results=100
        )

        logger.info(f"📅 Fetched {len(events)} events from Google Calendar - syncing ALL events without filtering")

        synced_count = 0
        new_count = 0
        skipped_count = 0
        pending_embeds = []

        # Step 2: Process ALL events (no filtering)
        async with conn.transaction():
            for event in events:
                google_event_id = event['event_id']
                event_title = event.get('summary', 'Untitled Meeting')

                logger.info(f"🔍 Processing event: '{event_title}' (ID: {google_event_id})")

                # Check if event already exists in CRM
                existing = await conn.fetchrow("""
                    SELECT interaction_id FROM interaction_details
                    WHERE google_calendar_event_id = $1
                """, google_event_id)

                if existing:
                    logger.info(f"⏭️  Event '{event_title}' already synced (interaction_id: {existing['interaction_id']})")
                    synced_count += 1
                    continue

                # Create new meeting in CRM
                start_dt = event['start'].get('dateTime')
                end_dt = event['end'].get('dateTime')

                if start_dt and end_dt:
                    meeting_content = json.dumps({
                        "title": event_title,
                        "description": event.get('description', ''),
                        "start_time": start_dt,
                        "end_time": end_dt,
                        "attendees": event.get('attendees', []),
                        "location": event.get('location', ''),
                        "meeting_link": event.get('meeting_link', ''),
                        "timezone": event['start'].get('timeZone', 'UTC')
                    })

                    source = 'google_calendar_sync' if provider == 'google' else 'outlook_calendar_sync'

                    result = await conn.fetchrow("""
                        INSERT INTO interaction_details
                        (customer_id, employee_id, type, content, google_calendar_event_id, source, theme, created_at, updated_at)
                        VALUES ($1, $2, 'meet', $3, $4, $5, $6, NOW(), NOW())
                        RETURNING interaction_id
                    """, customer_id, employee_id, meeting_content, google_event_id, source, event_title)

                    new_count += 1
                    synced_count += 1
                    logger.info(f"✅ Created new meeting: '{event_title}' → customer {customer_id}, interaction_id {result['interaction_id']}")
                    pending_embeds.append((result['interaction_id'], meeting_content))
                else:
                    logger.warning(f"⚠️  Event '{event_title}' missing start/end time, skipping")
                    skipped_count += 1

        # Fire-and-forget embeddings after transaction commits
        for interaction_id, content in pending_embeds:
            try:
                from services.rag.embedding_sync_service import embed_single_interaction
                asyncio.ensure_future(embed_single_interaction(user_email, interaction_id, content))
            except Exception as embed_err:
                logger.warning(f"Meeting embedding skipped: {embed_err}")

        logger.info(f"✅ Sync complete: {len(events)} total events, {new_count} new meetings created, {skipped_count} skipped")

        return {
            "status": "success",
            "total_events": len(events),
            "total_synced": synced_count,
            "new_meetings": new_count,
            "skipped": skipped_count,
            "message": f"Synced {new_count} new meetings from {provider.capitalize()} Calendar"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing Calendar: {e}")
        logger.error("Full traceback:", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/sync-all-google-calendar")
async def sync_all_google_calendar_to_crm(
    google_access_token: Optional[str] = Header(default=None, alias="X-Google-Access-Token"),
    sync_request: GoogleCalendarSyncRequest = GoogleCalendarSyncRequest(),
    tenant: tuple = Depends(get_tenant_connection)
):
    """
    Sync ALL meetings FROM Calendar (Google/Outlook) TO CRM with auto-refresh tokens.
    One-way sync: Calendar (Google or Microsoft) → CRM

    NO FILTERING - syncs all calendar events and intelligently matches them to customers
    based on attendee email addresses. Events without matching customers are skipped.

    NEW: Now automatically detects calendar provider (Google or Microsoft).
    - If google_access_token is provided: Uses the old method (for backward compatibility)
    - If not provided: Auto-detects provider and uses stored tokens from database with auto-refresh

    Steps:
    1. Get employee_id from authenticated user
    2. Detect calendar provider (Google or Microsoft)
    3. Fetch ALL events from Calendar within time range (auto-refreshes token if expired)
    4. For each event:
       - Try to match attendees to customers in database
       - If customer found: link event to that customer
       - If no customer found: skip the event
    5. Return sync summary
    """
    try:
        conn, user = tenant
        user_email = user.get('email', '')
        logger.info(f"🔄 Syncing ALL Calendar events by user {user_email}")

        # Get employee_id
        row = await conn.fetchrow("SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1", user_email)
        employee_id = row["employee_id"] if row else None
        if not employee_id:
            raise HTTPException(status_code=404, detail="Employee not found")

        # Step 1: Detect calendar provider and create appropriate service
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
                    detail="No calendar provider connected. Please connect Google Calendar or Outlook Calendar first."
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
                    detail=f"Unsupported calendar provider: {provider}"
                )

        # Default time range: 30 days ago to 90 days future
        time_min = sync_request.time_min or (datetime.now(timezone.utc) - timedelta(days=30)).isoformat().replace('+00:00', 'Z')
        time_max = sync_request.time_max or (datetime.now(timezone.utc) + timedelta(days=90)).isoformat().replace('+00:00', 'Z')

        events = await calendar_service.list_events(
            time_min=time_min,
            time_max=time_max,
            max_results=100
        )

        logger.info(f"📅 Fetched {len(events)} events from {provider.capitalize()} Calendar - processing all events")

        # Step 2: Get all customer emails for matching
        customer_email_rows = await conn.fetch("SELECT client_id, LOWER(email) as email FROM personnel WHERE client_id IS NOT NULL AND email IS NOT NULL")
        customer_email_map = {row['email']: row['client_id'] for row in customer_email_rows}
        logger.info(f"📧 Loaded {len(customer_email_map)} customer emails for matching")

        synced_count = 0
        new_count = 0
        skipped_count = 0
        pending_embeds = []

        # Step 3: Process each event
        async with conn.transaction():
            for event in events:
                google_event_id = event['event_id']
                event_title = event.get('summary', 'Untitled Meeting')
                attendees = event.get('attendees', [])

                logger.info(f"🔍 Processing event: '{event_title}' (ID: {google_event_id}, {len(attendees)} attendees)")

                # Check if event already exists in CRM
                existing = await conn.fetchrow("""
                    SELECT interaction_id FROM interaction_details
                    WHERE google_calendar_event_id = $1
                """, google_event_id)

                if existing:
                    logger.info(f"⏭️  Event '{event_title}' already synced (interaction_id: {existing['interaction_id']})")
                    synced_count += 1
                    continue

                # Try to match attendees to customers
                matched_customer_id = None
                for attendee_email in attendees:
                    attendee_lower = attendee_email.lower()
                    if attendee_lower in customer_email_map:
                        matched_customer_id = customer_email_map[attendee_lower]
                        logger.info(f"✅ Matched attendee {attendee_email} to customer_id {matched_customer_id}")
                        break

                if not matched_customer_id:
                    logger.info(f"⏭️  No customer match found for event '{event_title}', skipping")
                    skipped_count += 1
                    continue

                # Create new meeting in CRM
                start_dt = event['start'].get('dateTime')
                end_dt = event['end'].get('dateTime')

                if start_dt and end_dt:
                    meeting_content = json.dumps({
                        "title": event_title,
                        "description": event.get('description', ''),
                        "start_time": start_dt,
                        "end_time": end_dt,
                        "attendees": event.get('attendees', []),
                        "location": event.get('location', ''),
                        "meeting_link": event.get('meeting_link', ''),
                        "timezone": event['start'].get('timeZone', 'UTC'),
                        "calendar_provider": provider
                    })

                    # Determine source based on provider
                    source = 'google_calendar_sync' if provider == 'google' else 'outlook_calendar_sync'

                    result = await conn.fetchrow("""
                        INSERT INTO interaction_details
                        (customer_id, employee_id, type, content, google_calendar_event_id, source, theme, created_at, updated_at)
                        VALUES ($1, $2, 'meet', $3, $4, $5, $6, NOW(), NOW())
                        RETURNING interaction_id
                    """, matched_customer_id, employee_id, meeting_content, google_event_id, source, event_title)

                    new_count += 1
                    synced_count += 1
                    logger.info(f"✅ Created new meeting: '{event_title}' → customer {matched_customer_id}, interaction_id {result['interaction_id']}")
                    pending_embeds.append((result['interaction_id'], meeting_content))
                else:
                    logger.warning(f"⚠️  Event '{event_title}' missing start/end time, skipping")
                    skipped_count += 1

        # Fire-and-forget embeddings after transaction commits
        for interaction_id, content in pending_embeds:
            try:
                from services.rag.embedding_sync_service import embed_single_interaction
                asyncio.ensure_future(embed_single_interaction(user_email, interaction_id, content))
            except Exception as embed_err:
                logger.warning(f"Meeting embedding skipped: {embed_err}")

        logger.info(f"✅ Sync complete: {len(events)} total events, {new_count} new meetings created, {skipped_count} skipped")

        return {
            "status": "success",
            "total_events": len(events),
            "total_synced": synced_count,
            "new_meetings": new_count,
            "skipped": skipped_count,
            "message": f"Synced {new_count} new meetings from {provider.capitalize()} Calendar"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing Calendar: {e}")
        logger.error("Full traceback:", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
