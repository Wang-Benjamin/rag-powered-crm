"""Outlook sync functionality for CRM email integration using Microsoft Graph API"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import asyncio

from email_core.sync.common import extract_email_addresses
from email_core.sync.outlook_helpers import (
    parse_outlook_recipients,
    format_outlook_email_address,
    format_outlook_recipients,
)

from service_core.db import get_tenant_connection, get_pool_manager
from services.email_sync_service import (
    get_email_sync_state,
    update_email_sync_state,
    get_all_customer_emails,
    get_all_employee_emails,
    get_customer_by_email,
    create_email_interaction
)
from services.calendar.oauth_token_manager import OAuthTokenManager
from email_service.sync.outlook_sync import OutlookSyncService
import auth.providers

import os

logger = logging.getLogger(__name__)
router = APIRouter()

# Set SYNC_VERBOSE=true to restore step-by-step diagnostic logging
_SYNC_VERBOSE = os.getenv('SYNC_VERBOSE', '').lower() in ('1', 'true', 'yes')

# Microsoft Graph API endpoints
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
OUTLOOK_MESSAGES_ENDPOINT = f"{GRAPH_API_BASE}/me/messages"
OUTLOOK_USER_ENDPOINT = f"{GRAPH_API_BASE}/me"

# Pydantic models
class OutlookSyncRequest(BaseModel):
    access_token: Optional[str] = None  # Optional - will use stored token with auto-refresh if not provided
    include_body: bool = True
    include_sent: bool = True
    include_received: bool = True

class CustomerEmail(BaseModel):
    customer_name: str
    subject: str
    customer_id: Optional[str] = None  # Customer ID for frontend redirect
    email_id: Optional[str] = None  # Email ID for opening specific email
    body_snippet: Optional[str] = None  # Body preview for notifications (max 50 chars)

class OutlookSyncResponse(BaseModel):
    success: bool
    emails_synced: int
    last_sync_timestamp: str
    total_emails_synced: int
    message: str
    customer_emails: List[CustomerEmail] = []

class OutlookStatusResponse(BaseModel):
    last_sync_timestamp: Optional[str] = None
    total_emails_synced: int = 0

# Helper functions — delegated to email_core/sync shared helpers
# extract_email_addresses → email_core.sync.common
# parse_outlook_recipients, format_outlook_email_address, format_outlook_recipients → email_core.sync.outlook_helpers


# API Endpoints
@router.get("/outlook/test")
async def test_outlook_endpoint():
    """Test endpoint to verify Outlook sync is loaded"""
    return {"status": "Outlook sync endpoints are loaded and working"}


@router.get("/outlook/status")
async def get_outlook_status(tenant: tuple = Depends(get_tenant_connection)) -> OutlookStatusResponse:
    """Get Outlook sync status"""
    try:
        conn, user = tenant
        # Get employee_id from authenticated user
        user_email = user.get('email', '')
        employee_id = None
        if user_email:
            try:
                row = await conn.fetchrow(
                    "SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1",
                    user_email
                )
                employee_id = row["employee_id"] if row else None
            except Exception:
                # Employee not found, use default sync state
                pass

        # Get sync state for this employee
        sync_state = await get_email_sync_state(conn, employee_id)

        if not sync_state:
            return OutlookStatusResponse(
                last_sync_timestamp=None,
                total_emails_synced=0
            )

        return OutlookStatusResponse(
            last_sync_timestamp=sync_state['last_sync_timestamp'].isoformat() if sync_state['last_sync_timestamp'] else None,
            total_emails_synced=sync_state['emails_synced_count']
        )

    except Exception as e:
        logger.error(f"Error getting Outlook status: {e}")
        return OutlookStatusResponse(total_emails_synced=0)

async def _perform_outlook_sync(
    request: OutlookSyncRequest,
    conn,
    user: dict
) -> OutlookSyncResponse:
    """Internal function to perform Outlook sync (used by both foreground and background endpoints)"""
    try:
        logger.info(f"Outlook sync requested by user: {user.get('email', 'unknown')}")

        # Get user's employee ID from authenticated session
        user_email = user.get('email', '')
        if not user_email:
            raise HTTPException(status_code=400, detail="User email not found in authentication")

        try:
            emp_row = await conn.fetchrow(
                "SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1",
                user_email
            )
            if not emp_row:
                raise HTTPException(status_code=403, detail="User is not registered as an employee")
            employee_id = emp_row["employee_id"]
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error looking up employee: {str(e)}")

        logger.info(f"Outlook sync started by user: {user_email} (employee_id: {employee_id})")

        # Initialize Outlook sync service with token manager for auto-refresh
        logger.info("Using OutlookSyncService with auto-refresh token manager...")
        try:
            current_auth_provider = auth.providers.auth_provider

            if not current_auth_provider:
                raise HTTPException(
                    status_code=500,
                    detail="Auth provider not configured. Please reconnect your Microsoft account."
                )

            token_manager = OAuthTokenManager(current_auth_provider)
            outlook_sync = OutlookSyncService(token_manager=token_manager)

            logger.info(f"Successfully initialized OutlookSyncService for {user_email}")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error initializing Outlook sync service: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize Outlook sync service: {str(e)}"
            )

        # Get sync state for this employee
        sync_state = await get_email_sync_state(conn, employee_id)

        # Get customer and employee emails assigned to this employee
        customer_emails = await get_all_customer_emails(conn, employee_id)
        employee_emails = await get_all_employee_emails(conn)

        logger.info(f"Found {len(customer_emails)} customer email addresses assigned to employee {employee_id}")
        logger.info(f"Found {len(employee_emails)} employee email addresses in database")

        if not customer_emails:
            return OutlookSyncResponse(
                success=True,
                emails_synced=0,
                last_sync_timestamp=datetime.now(timezone.utc).isoformat(),
                total_emails_synced=0,
                message="No customers found in database",
                customer_emails=[]
            )

        # Combine customer and employee emails for search (keep as-is, already lowercased from DB)
        all_tracked_emails = set(customer_emails) | set(employee_emails)
        logger.info(f"Total tracked emails (customers + employees): {len(all_tracked_emails)}")

        # Build query parameters for Microsoft Graph API
        query_params = {
            '$top': 500,  # Max results per request
            '$select': 'id,subject,from,toRecipients,ccRecipients,receivedDateTime,body,bodyPreview,conversationId',
            '$orderby': 'receivedDateTime desc'
        }

        # Add date filter for incremental sync (email filtering done client-side)
        if sync_state and sync_state.get('last_sync_timestamp'):
            last_sync = sync_state['last_sync_timestamp']
            # Ensure timezone-aware datetime (convert naive to UTC if needed)
            if last_sync.tzinfo is None:
                last_sync = last_sync.replace(tzinfo=timezone.utc)
            # Subtract 1 minute to ensure we don't miss emails from the same minute
            # The ON CONFLICT on gmail_message_id prevents duplicates
            last_sync_adjusted = last_sync - timedelta(minutes=1)
            # Microsoft Graph uses ISO 8601 format with Z suffix for UTC
            date_filter = last_sync_adjusted.isoformat().replace('+00:00', 'Z')
            query_params['$filter'] = f"receivedDateTime ge {date_filter}"
            logger.info(f"Using incremental sync from {date_filter} (last sync was {last_sync})")
        else:
            # Initial sync - get last 30 days
            date_30_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat().replace('+00:00', 'Z')
            query_params['$filter'] = f"receivedDateTime ge {date_30_days_ago}"
            logger.info(f"Initial sync - getting emails from last 30 days")

        # Get messages with full pagination support using OutlookSyncService
        # Set max_emails based on sync type
        max_emails = 5000  # Safety limit for incremental sync
        if not sync_state or not sync_state.get('last_sync_timestamp'):
            # Initial sync - limit to 2000 emails to avoid excessive API calls
            max_emails = 2000
            logger.info(f"Initial sync - will fetch up to {max_emails} emails from last 30 days")
        else:
            logger.info(f"Incremental sync - will fetch up to {max_emails} emails since last sync")

        logger.info("Fetching emails from Outlook with pagination using OutlookSyncService...")
        logger.info(f"Query params: $top={query_params['$top']}, $orderby={query_params['$orderby']}, $filter={query_params.get('$filter', 'none')}")
        messages = await outlook_sync.get_messages_list(user_email, query_params, max_results=max_emails)

        # Process emails
        emails_synced = 0
        total_messages = len(messages)
        logger.info(f"Fetched {total_messages} total messages from Outlook. Now filtering for customer emails...")

        # Collect enriched notification data (customer names + subjects)
        customer_email_previews = []

        for idx, msg in enumerate(messages):
            try:
                # Extract email data with thread ID (conversationId)
                email_data = {
                    'id': msg['id'],
                    'thread_id': msg.get('conversationId'),  # Outlook conversationId for thread grouping
                    'subject': msg.get('subject', ''),
                    'from': '',
                    'to': '',
                    'cc': '',
                    'date': None,
                    'body': ''
                }

                # Extract from address (formatted with display name like Gmail)
                if msg.get('from'):
                    email_data['from'] = format_outlook_email_address(msg['from'])

                # Extract to addresses (formatted with display names like Gmail)
                if msg.get('toRecipients'):
                    email_data['to'] = format_outlook_recipients(msg['toRecipients'])

                # Extract cc addresses (formatted with display names like Gmail)
                if msg.get('ccRecipients'):
                    email_data['cc'] = format_outlook_recipients(msg['ccRecipients'])

                # Parse date
                if msg.get('receivedDateTime'):
                    try:
                        parsed_date = datetime.fromisoformat(msg['receivedDateTime'].replace('Z', '+00:00'))
                        if parsed_date.tzinfo is None:
                            parsed_date = parsed_date.replace(tzinfo=timezone.utc)
                        email_data['date'] = parsed_date
                    except Exception:
                        email_data['date'] = datetime.now(timezone.utc)

                # Always extract body - use bodyPreview for notifications, full body if requested
                if request.include_body and msg.get('body'):
                    if msg['body'].get('contentType') == 'text':
                        email_data['body'] = msg['body'].get('content', '')
                    else:
                        email_data['body'] = msg.get('bodyPreview', '')
                else:
                    # Use bodyPreview for notification snippet (max 50 chars)
                    preview = msg.get('bodyPreview', '')
                    email_data['body'] = preview[:50] if preview else ''

                # Extract all email addresses from the email (must match Gmail logic)
                all_emails = []
                # Extract from 'from' field using the same pattern as Gmail
                all_emails.extend(extract_email_addresses(email_data['from']))
                # Extract from 'to' field - need to use the comma-separated string
                all_emails.extend(extract_email_addresses(email_data['to']))
                # Extract from 'cc' field - need to use the comma-separated string
                all_emails.extend(extract_email_addresses(email_data['cc']))

                if _SYNC_VERBOSE and idx < 5:
                    logger.debug(f"[CRM Sync] Outlook email {idx+1}: From={email_data['from']}, Subject={email_data['subject'][:50]}")

                # Find matching customer - check if ANY email in the conversation is a customer
                customer_email_found = None
                for email_addr in all_emails:
                    if email_addr in customer_emails:
                        customer_email_found = email_addr
                        break

                if customer_email_found:
                    customer = await get_customer_by_email(customer_email_found, conn)
                    if customer:
                        logger.info(f"Matched email to customer: {customer['client_name']} ({customer_email_found})")
                        result = await create_email_interaction(conn, customer['client_id'], email_data, request.include_body, employee_id)
                        if result:
                            emails_synced += 1
                            logger.info(f"Successfully synced email: {email_data['subject'][:50]}...")
                            # Collect for enriched notification (limit to 4, received emails only)
                            from_field = email_data.get('from', '').lower()
                            is_received = user_email.lower() not in from_field
                            if len(customer_email_previews) < 4 and is_received:
                                subject = email_data['subject']
                                if len(subject) > 30:
                                    subject = subject[:30] + '...'
                                # Get body snippet for notification preview (max 50 chars)
                                body = email_data.get('body', '')
                                body_snippet = body[:50] + '...' if len(body) > 50 else body

                                customer_email_previews.append({
                                    'customer_name': customer['client_name'],
                                    'subject': subject,
                                    'customer_id': str(customer['client_id']),
                                    'email_id': email_data.get('id', ''),
                                    'body_snippet': body_snippet
                                })
                        else:
                            logger.info(f"Email already exists in database (skipping): {email_data['subject'][:50]}...")
                elif idx < 5:
                    logger.info(f"No customer match for email addresses: {all_emails}")
                    logger.debug(f"Known customer emails: {list(customer_emails)[:5]}...")

                # Log progress every 100 emails
                if (idx + 1) % 100 == 0:
                    logger.info(f"Processed {idx + 1}/{total_messages} emails, synced {emails_synced} so far")

            except Exception as e:
                logger.error(f"Error processing email {msg.get('id', 'unknown')}: {e}")
                continue

        # Update sync state for this employee
        try:
            await update_email_sync_state(conn, f"outlook_sync_{datetime.now(timezone.utc).isoformat()}", emails_synced, employee_id)
        except Exception as e:
            logger.error(f"Failed to update sync state: {e}")
            # Don't fail the whole sync if state update fails

        # Get updated totals for this employee
        try:
            updated_state = await get_email_sync_state(conn, employee_id)
            total_synced = updated_state['emails_synced_count'] if updated_state else emails_synced
        except Exception as e:
            logger.error(f"Failed to get sync state: {e}")
            total_synced = emails_synced

        logger.info(f"[CRM Sync] Outlook complete: synced={emails_synced} found={total_messages} total_all_time={total_synced}")
        logger.debug(f"[CRM Sync] Outlook previews collected: {len(customer_email_previews)}")

        return OutlookSyncResponse(
            success=True,
            emails_synced=emails_synced,
            last_sync_timestamp=datetime.now(timezone.utc).isoformat(),
            total_emails_synced=total_synced,
            message=f"Successfully synced {emails_synced} new customer emails",
            customer_emails=customer_email_previews
        )

    except HTTPException:
        raise
    except ValueError as e:
        # Token/authentication errors — return 401 with helpful message.
        # Match Gmail's matcher exactly (gmail_sync_router.py:225) so both
        # providers classify auth failures consistently.
        error_msg = str(e)
        logger.error(f"Outlook sync authentication error: {error_msg}")
        if "authentication failed" in error_msg.lower() or "token" in error_msg.lower():
            raise HTTPException(status_code=401, detail=error_msg)
        raise HTTPException(status_code=500, detail=f"Outlook sync error: {error_msg}")
    except Exception as e:
        logger.error(f"Error syncing Outlook emails: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/outlook/sync")
async def sync_outlook_emails(
    request: OutlookSyncRequest,
    tenant: tuple = Depends(get_tenant_connection)
) -> OutlookSyncResponse:
    """
    Sync emails from Outlook - FOREGROUND MODE (blocks until complete)

    Use this endpoint for manual sync operations where you want to wait for results.
    For automatic/background sync (e.g., on app startup), use /outlook/sync-background instead.
    """
    conn, user = tenant
    return await _perform_outlook_sync(request, conn, user)


@router.post("/outlook/sync-background")
async def sync_outlook_emails_background(
    request: OutlookSyncRequest,
    tenant: tuple = Depends(get_tenant_connection)
) -> Dict[str, Any]:
    """
    Sync emails from Outlook - BACKGROUND MODE (returns immediately, truly non-blocking)

    This endpoint starts the sync operation in a separate asyncio task and returns immediately.
    The sync runs independently without blocking the event loop or other requests.

    Use this for automatic sync operations (e.g., on app startup) to avoid blocking the UI.

    Returns:
        - status: "started"
        - message: Confirmation message
        - user_email: Email of the user whose emails are being synced
        - task_id: Unique identifier for this sync task
    """
    conn, user = tenant
    user_email = user.get('email', 'unknown')
    db_name = user.get('db_name')
    if not db_name:
        db_name = await get_pool_manager().lookup_db_name(user_email)

    # Background task acquires its own connection (request-scoped conn will be released)
    async def _bg_sync():
        async with get_pool_manager().acquire(db_name) as bg_conn:
            await _perform_outlook_sync(request, bg_conn, user)

    _task = asyncio.create_task(_bg_sync())

    # Generate task ID for tracking
    task_id = f"outlook_sync_{user_email}_{datetime.now(timezone.utc).timestamp()}"

    logger.info(f"Background Outlook sync started for user: {user_email} (task_id: {task_id})")
    logger.info(f"Sync is running independently and will NOT block other requests")

    return {
        "status": "started",
        "message": f"Outlook sync started in background for {user_email}",
        "user_email": user_email,
        "task_id": task_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "note": "Sync is running independently and will not block other CRM operations"
    }
