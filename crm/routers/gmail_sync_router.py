"""Gmail sync functionality for CRM email integration"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import List, Dict, Optional, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import asyncio

from email_core.sync.common import extract_email_addresses
from email_core.sync.gmail_helpers import parse_gmail_headers, extract_gmail_body, decode_gmail_base64
from email_core.triage.classifier import classify_batch

from service_core.db import get_tenant_connection, get_pool_manager
from services.email_sync_service import (
    get_email_sync_state,
    update_email_sync_state,
    get_all_customer_emails,
    get_all_employee_emails,
    get_customer_by_email,
    create_email_interaction,
    batch_create_email_interactions
)
from services.calendar.oauth_token_manager import OAuthTokenManager
from email_service.sync.gmail_sync import GmailSyncService
import auth.providers

import os

logger = logging.getLogger(__name__)
router = APIRouter()

# Set SYNC_VERBOSE=true to restore step-by-step diagnostic logging
_SYNC_VERBOSE = os.getenv('SYNC_VERBOSE', '').lower() in ('1', 'true', 'yes')

# Pydantic models
class GmailSyncRequest(BaseModel):
    access_token: Optional[str] = None  # Optional - will use stored token with auto-refresh if not provided
    include_body: bool = False
    include_sent: bool = True
    include_received: bool = True

class CustomerEmail(BaseModel):
    customer_name: str
    subject: str
    customer_id: Optional[str] = None  # Customer ID for frontend redirect
    email_id: Optional[str] = None  # Email ID for opening specific email
    body_snippet: Optional[str] = None  # Body preview for notifications (max 50 chars)

class GmailSyncResponse(BaseModel):
    success: bool
    emails_synced: int
    last_sync_timestamp: str
    total_emails_synced: int
    message: str
    customer_emails: List[CustomerEmail] = []

class GmailStatusResponse(BaseModel):
    last_sync_timestamp: Optional[str] = None
    total_emails_synced: int = 0

# Helper functions — delegated to email_core/sync shared helpers
# extract_email_addresses → email_core.sync.common
# parse_gmail_headers, extract_gmail_body, decode_gmail_base64 → email_core.sync.gmail_helpers

# Alias for backward compat (call sites use extract_email_data)
extract_email_data = parse_gmail_headers

# API Endpoints
@router.get("/gmail/test")
async def test_gmail_endpoint():
    """Test endpoint to verify Gmail sync is loaded"""
    return {"status": "Gmail sync endpoints are loaded and working"}

@router.get("/gmail/status")
async def get_gmail_status(tenant: tuple = Depends(get_tenant_connection)) -> GmailStatusResponse:
    """Get Gmail sync status"""
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

        sync_state = await get_email_sync_state(conn, employee_id)

        if not sync_state:
            return GmailStatusResponse(
                last_sync_timestamp=None,
                total_emails_synced=0
            )

        return GmailStatusResponse(
            last_sync_timestamp=sync_state['last_sync_timestamp'].isoformat() if sync_state['last_sync_timestamp'] else None,
            total_emails_synced=sync_state['emails_synced_count']
        )

    except Exception as e:
        logger.error(f"Error getting Gmail status: {e}")
        return GmailStatusResponse(total_emails_synced=0)

async def _perform_gmail_sync(
    request: GmailSyncRequest,
    conn,
    user: dict
) -> GmailSyncResponse:
    """Internal function to perform Gmail sync (used by both foreground and background endpoints)"""
    try:
        user_email = user.get('email', '')
        logger.info(f"[CRM Sync] Gmail sync started for {user_email}")

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
            logger.error(f"[CRM Sync] Error getting employee ID: {e}")
            raise

        # Initialize Gmail sync service with token manager for auto-refresh
        try:
            current_auth_provider = auth.providers.auth_provider

            if not current_auth_provider:
                raise HTTPException(
                    status_code=500,
                    detail="Auth provider not configured. Please reconnect your Google account."
                )

            token_manager = OAuthTokenManager(current_auth_provider)
            gmail_sync = GmailSyncService(token_manager=token_manager)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error initializing Gmail sync service: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize Gmail sync service: {str(e)}"
            )

        sync_state = await get_email_sync_state(conn, employee_id)
        customer_emails = await get_all_customer_emails(conn, employee_id)
        logger.info(f"[CRM Sync] Gmail: {len(customer_emails)} customer emails for employee {employee_id}")

        if not customer_emails:
            return GmailSyncResponse(
                success=True,
                emails_synced=0,
                last_sync_timestamp=datetime.now(timezone.utc).isoformat(),
                total_emails_synced=0,
                message="No customers found in database",
                customer_emails=[]
            )

        # Build search query for signed-in employee's emails with their customers
        all_tracked_emails = set(customer_emails) | {user_email}

        if len(all_tracked_emails) > 0:
            tracked_emails_list = sorted(list(all_tracked_emails))
            email_queries = []
            included_emails = []
            for email in tracked_emails_list:
                if email and email.strip() and '@' in email:
                    email_queries.append(f"(from:{email} OR to:{email})")
                    included_emails.append(email)

            if not email_queries:
                logger.error("[CRM Sync] No valid email addresses found to search for")
                return GmailSyncResponse(
                    success=False,
                    emails_synced=0,
                    last_sync_timestamp=datetime.now(timezone.utc).isoformat(),
                    total_emails_synced=0,
                    message="No valid email addresses found in database",
                    customer_emails=[]
                )

            email_filter = " OR ".join(email_queries)

            if sync_state and sync_state.get('last_sync_timestamp'):
                last_sync = sync_state['last_sync_timestamp']
                date_filter = (last_sync - timedelta(days=1)).strftime('%Y/%m/%d')
                query = f"({email_filter}) AND after:{date_filter}"
                logger.debug(f"[CRM Sync] Incremental sync after:{date_filter}")
            else:
                date_30_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).strftime('%Y/%m/%d')
                query = f"({email_filter}) AND after:{date_30_days_ago}"
                logger.debug("[CRM Sync] Initial sync — last 30 days")
        else:
            if sync_state and sync_state.get('last_sync_timestamp'):
                last_sync = sync_state['last_sync_timestamp']
                date_filter = (last_sync - timedelta(days=1)).strftime('%Y/%m/%d')
                query = f"after:{date_filter}"
            else:
                query = ""

        try:
            messages = await gmail_sync.get_messages_list(user_email, query, max_results=500)
            total_messages = len(messages)
            logger.info(f"[CRM Sync] Gmail: {total_messages} messages found for {user_email}")
        except ValueError as e:
            error_msg = str(e)
            logger.error(f"[CRM Sync] Gmail auth error: {error_msg}")
            if "authentication failed" in error_msg.lower() or "token" in error_msg.lower():
                raise HTTPException(status_code=401, detail=error_msg)
            else:
                raise HTTPException(status_code=500, detail=f"Failed to fetch Gmail messages: {error_msg}")
        except Exception as e:
            logger.error(f"[CRM Sync] Error fetching message list: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to fetch Gmail messages: {str(e)}")

        if total_messages == 0:
            return GmailSyncResponse(
                success=True,
                emails_synced=0,
                last_sync_timestamp=datetime.now(timezone.utc).isoformat(),
                total_emails_synced=sync_state.get('emails_synced_count', 0) if sync_state else 0,
                message="No new emails to sync",
                customer_emails=[]
            )

        start_time = time.time()
        message_ids = [msg['id'] for msg in messages]

        try:
            access_token = await token_manager.get_valid_access_token(user_email, 'google')
            if not access_token:
                logger.error("[CRM Sync] No valid access token available")
                raise HTTPException(
                    status_code=401,
                    detail="No valid Google access token available for batch operations."
                )
            if _SYNC_VERBOSE:
                logger.debug(f"[CRM Sync] Access token obtained (length: {len(access_token)} chars)")

            # Build Gmail service for batch API
            gmail_service = gmail_sync._build_service(access_token)

            all_message_details = gmail_sync.batch_get_messages(
                gmail_service,
                message_ids,
                request.include_body
            )
            fetch_time = time.time() - start_time
            logger.debug(f"[CRM Sync] Batch fetch: {len(all_message_details)} messages in {fetch_time:.2f}s")

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[CRM Sync] Error during batch message retrieval: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve message details: {str(e)}"
            )

        process_start = time.time()
        customer_lookup = {}  # email -> customer_data
        try:
            rows = await conn.fetch("""
                SELECT p.client_id, ci.name, LOWER(p.email) as email
                FROM personnel p
                JOIN clients ci ON p.client_id = ci.client_id
                WHERE p.client_id IS NOT NULL
                  AND p.email IS NOT NULL AND p.email != ''
            """)
            for row in rows:
                customer_lookup[row['email'].lower()] = {
                    'client_id': row['client_id'],
                    'client_name': row['name'],
                    'email': row['email']
                }
        except Exception as e:
            logger.error(f"[CRM Sync] Error pre-loading customers: {e}")
            customer_lookup = {}

        existing_message_ids = set()
        try:
            id_rows = await conn.fetch("""
                SELECT gmail_message_id
                FROM interaction_details
                WHERE gmail_message_id IS NOT NULL
            """)
            for row in id_rows:
                existing_message_ids.add(row['gmail_message_id'])
        except Exception as e:
            logger.error(f"[CRM Sync] Error pre-loading message IDs: {e}")
            existing_message_ids = set()

        emails_to_insert = []  # Collect all emails for batch insert
        duplicates_skipped = 0  # Track how many duplicates we skip

        for idx, message_data in enumerate(all_message_details):
            try:
                if not message_data:
                    continue

                # Extract message ID first to check for duplicates
                gmail_message_id = message_data['id']

                if gmail_message_id in existing_message_ids:
                    duplicates_skipped += 1
                    continue

                # Extract headers and thread ID
                headers = message_data.get('payload', {}).get('headers', [])
                thread_id = message_data.get('threadId')  # Gmail thread ID for thread grouping

                email_data = {
                    'id': gmail_message_id,
                    'thread_id': thread_id,  # Store Gmail threadId for conversation tracking
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

                # Always extract body for notifications, store full or snippet based on include_body
                raw_body = extract_gmail_body(message_data.get('payload', {}))
                email_data['body'] = raw_body if request.include_body else (raw_body[:50] if raw_body else '')

                # Extract all email addresses from the email
                all_emails = []
                all_emails.extend(extract_email_addresses(email_data['from']))
                all_emails.extend(extract_email_addresses(email_data['to']))
                all_emails.extend(extract_email_addresses(email_data['cc']))

                # Log first few emails for debugging
                if idx < 5:
                    logger.info(f"Email {idx+1}: From={email_data['from']}, To={email_data['to']}, Subject={email_data['subject'][:50]}")

                # Find matching customer - check if ANY email in the conversation is a customer
                # Use in-memory lookup instead of database query (much faster!)
                customer_email_found = None
                customer = None
                for email_addr in all_emails:
                    email_lower = email_addr.lower()
                    if email_lower in customer_lookup:
                        customer_email_found = email_addr
                        customer = customer_lookup[email_lower]
                        break

                if customer:
                    # Add to batch insert list
                    emails_to_insert.append({
                        'customer_id': customer['client_id'],
                        'email_data': email_data,
                        'customer_name': customer['client_name']
                    })

                    if idx < 5:
                        logger.info(f"Matched email to customer: {customer['client_name']} ({customer_email_found})")
                elif idx < 5:
                    logger.info(f"No customer match for email addresses: {all_emails}")

                # Log progress every 100 emails
                if (idx + 1) % 100 == 0:
                    logger.info(f"Processed {idx + 1}/{len(all_message_details)} emails in memory, {len(emails_to_insert)} matched to customers")

            except Exception as e:
                logger.error(f"Error processing message {message_data.get('id', 'unknown')}: {e}")
                continue

        process_time = time.time() - process_start
        logger.info("=" * 80)
        logger.info(f"STEP 9 COMPLETE: In-memory processing finished")
        logger.info(f"   Time: {process_time:.2f}s")
        logger.info(f"   Total emails fetched: {len(all_message_details)}")
        logger.info(f"   Duplicates skipped: {duplicates_skipped}")
        logger.info(f"   New emails to process: {len(all_message_details) - duplicates_skipped}")
        logger.info(f"   Emails matched to customers: {len(emails_to_insert)}/{len(all_message_details) - duplicates_skipped}")
        logger.info("=" * 80)

        # Get employee access level and filter emails by assignment for notifications
        access_level = None
        assigned_customer_ids = set()

        if employee_id:
            try:
                access_row = await conn.fetchrow(
                    "SELECT access FROM employee_info WHERE employee_id = $1",
                    employee_id
                )

                if access_row:
                    access_level = access_row['access']
                    logger.info(f"User {user_email} has access level: {access_level}")

                    if access_level == 'user':
                        # Get assigned customers from employee_client_links
                        assigned_rows = await conn.fetch(
                            "SELECT client_id FROM employee_client_links WHERE employee_id = $1 AND status = 'active'",
                            employee_id
                        )
                        assigned_customer_ids = {row['client_id'] for row in assigned_rows}
                        logger.info(f"User has {len(assigned_customer_ids)} assigned customers")
                    else:
                        # Admin sees all customers
                        logger.info(f"Admin user - no customer filtering for notifications")

            except Exception as e:
                logger.error(f"Error getting access level: {e}")
                # Default to user access (secure by default)
                access_level = 'user'

        # Collect enriched notification data (customer names + subjects) - limit to 4 most recent
        # Filter: (1) by assigned customers if user access, (2) received emails only (not sent by employee)
        customer_email_previews = []

        # Filter emails for notifications
        filtered_emails = []
        for item in emails_to_insert:
            # Skip if user access and not assigned to this customer
            if access_level == 'user' and assigned_customer_ids and item['customer_id'] not in assigned_customer_ids:
                continue
            # Skip sent emails (employee is in 'from' field) - only notify for received emails
            from_field = item['email_data'].get('from', '').lower()
            if user_email.lower() in from_field:
                continue
            filtered_emails.append(item)

        logger.info(f"Filtered to {len(filtered_emails)}/{len(emails_to_insert)} received emails for notifications")

        for item in filtered_emails[:4]:  # Get first 4 (most recent)
            subject = item['email_data']['subject']
            if len(subject) > 30:
                subject = subject[:30] + '...'
            # Get body snippet for notification preview (max 50 chars)
            body = item['email_data'].get('body', '')
            body_snippet = body[:50] + '...' if len(body) > 50 else body

            customer_email_previews.append({
                'customer_name': item['customer_name'],
                'subject': subject,
                'customer_id': str(item['customer_id']),
                'email_id': item['email_data'].get('id', ''),
                'body_snippet': body_snippet
            })
        logger.info(f"Collected {len(customer_email_previews)} email previews for notification")

        # ============================================================
        # BATCH DATABASE INSERT - Insert all emails in one transaction
        # ============================================================
        logger.info("=" * 80)
        logger.info("Step 10: BATCH DATABASE INSERT")
        logger.info("=" * 80)
        emails_synced = 0
        insert_start = time.time()  # Track insert time even if no emails

        if len(emails_to_insert) > 0:
            logger.info(f"Starting batch database insert for {len(emails_to_insert)} emails...")
            logger.info(f"   Employee ID: {employee_id}")
            logger.info(f"   Include body: {request.include_body}")

            try:
                # Prepare batch data for batch_create_email_interactions
                # Format: List of dicts with customer_id, email_data, employee_id (optional)
                batch_data = []
                for item in emails_to_insert:
                    batch_data.append({
                        'customer_id': item['customer_id'],
                        'email_data': item['email_data'],
                        'employee_id': None  # Will be auto-detected from email content
                    })

                # Call batch insert function (uses executemany for single transaction)
                emails_synced = await batch_create_email_interactions(
                    conn,
                    batch_data,
                    include_body=request.include_body,
                    synced_by_employee_id=employee_id,
                    user_email=user_email
                )

                insert_time = time.time() - insert_start
                logger.info("=" * 80)
                logger.info(f"STEP 10 COMPLETE: Batch insert finished")
                logger.info(f"   Time: {insert_time:.2f}s")
                logger.info(f"   New emails inserted: {emails_synced}")
                logger.info("=" * 80)

                if emails_synced < len(emails_to_insert):
                    duplicates = len(emails_to_insert) - emails_synced
                    logger.info(f"Skipped {duplicates} duplicate emails (already in database)")

                # Phase 1: Classify inbound emails with Haiku
                # Direction is determined during batch_create_email_interactions(),
                # so we query the DB for newly inserted inbound emails.
                if emails_synced > 0:
                    try:
                        affected_cids = list({item['customer_id'] for item in emails_to_insert if item.get('customer_id')})
                        inbound_rows = await conn.fetch(
                            """
                            SELECT ce.email_id, ce.from_email, ce.customer_id,
                                   ce.subject, ce.body, ce.direction, ce.created_at
                            FROM crm_emails ce
                            WHERE ce.customer_id = ANY($1)
                              AND ce.direction = 'received'
                              AND ce.conversation_state IS NULL
                            ORDER BY ce.created_at DESC
                            """,
                            affected_cids,
                        )

                        if inbound_rows:
                            # Batch fetch thread context for all affected customers (avoids N+1)
                            unique_cids = list({row['customer_id'] for row in inbound_rows})
                            all_thread_rows = await conn.fetch(
                                """
                                SELECT customer_id, email_id, subject, body, direction, created_at
                                FROM (
                                    SELECT customer_id, email_id, subject, body, direction, created_at,
                                           ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY created_at DESC) as rn
                                    FROM crm_emails
                                    WHERE customer_id = ANY($1)
                                ) sub
                                WHERE rn <= 3
                                ORDER BY customer_id, created_at DESC
                                """,
                                unique_cids,
                            )
                            thread_context = {}
                            for tr in all_thread_rows:
                                thread_context.setdefault(tr['customer_id'], []).append(dict(tr))

                            inbound_emails = []
                            for row in inbound_rows:
                                inbound_emails.append({
                                    'email_id': row['email_id'],
                                    'from_email': row['from_email'] or '',
                                    'thread_emails': thread_context.get(row['customer_id'], []),
                                })

                            classified = await classify_batch(
                                inbound_emails, conn, table="crm_emails"
                            )
                            logger.info(f"Classified {classified} inbound CRM emails")
                    except Exception as classify_err:
                        logger.warning(f"CRM email classification failed: {classify_err}")

                # Stage auto-progression for all synced customers
                if emails_synced > 0:
                    try:
                        from services.stage_progression_service import apply_stage_progression
                        affected_customer_ids = list({item['customer_id'] for item in emails_to_insert if item.get('customer_id')})
                        for cid in affected_customer_ids:
                            await apply_stage_progression(conn, cid)
                        logger.info(f"Stage progression evaluated for {len(affected_customer_ids)} customers")
                    except Exception as stage_err:
                        logger.debug(f"Stage progression skipped: {stage_err}")

            except Exception as e:
                logger.error(f"Error during batch insert: {e}", exc_info=True)
                # Fall back to individual inserts if batch fails
                logger.warning("Falling back to individual inserts...")
                for item in emails_to_insert:
                    try:
                        result = await create_email_interaction(
                            conn,
                            item['customer_id'],
                            item['email_data'],
                            request.include_body
                        )
                        if result:
                            emails_synced += 1
                    except Exception as individual_error:
                        logger.error(f"Error inserting individual email: {individual_error}")
                        continue
        else:
            logger.info("=" * 80)
            logger.info("STEP 10 SKIPPED: No emails matched to customers, nothing to insert")
            logger.info("=" * 80)

        total_time = time.time() - start_time

        # Update sync state for this employee
        try:
            await update_email_sync_state(conn, f"sync_{datetime.now(timezone.utc).isoformat()}", emails_synced, employee_id)
        except Exception as e:
            logger.error(f"[CRM Sync] Failed to update sync state: {e}")

        try:
            updated_state = await get_email_sync_state(conn, employee_id)
            total_synced = updated_state['emails_synced_count'] if updated_state else emails_synced
        except Exception as e:
            logger.error(f"[CRM Sync] Failed to get sync state: {e}")
            total_synced = emails_synced

        logger.info(f"[CRM Sync] Gmail complete: synced={emails_synced} found={total_messages} matched={len(emails_to_insert)} time={total_time:.1f}s")

        return GmailSyncResponse(
            success=True,
            emails_synced=emails_synced,
            last_sync_timestamp=datetime.now(timezone.utc).isoformat(),
            total_emails_synced=total_synced,
            message=f"Successfully synced {emails_synced} new customer emails in {total_time:.1f}s",
            customer_emails=customer_email_previews
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing Gmail emails: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/gmail/sync")
async def sync_gmail_emails(
    request: GmailSyncRequest,
    tenant: tuple = Depends(get_tenant_connection)
) -> GmailSyncResponse:
    """
    Sync emails from Gmail - FOREGROUND MODE (blocks until complete)

    Use this endpoint for manual sync operations where you want to wait for results.
    For automatic/background sync (e.g., on app startup), use /gmail/sync-background instead.
    """
    conn, user = tenant
    return await _perform_gmail_sync(request, conn, user)


@router.post("/gmail/sync-background")
async def sync_gmail_emails_background(
    request: GmailSyncRequest,
    tenant: tuple = Depends(get_tenant_connection)
) -> Dict[str, Any]:
    """
    Sync emails from Gmail - BACKGROUND MODE (returns immediately, truly non-blocking)

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
            await _perform_gmail_sync(request, bg_conn, user)

    task = asyncio.create_task(_bg_sync())

    # Generate task ID for tracking
    task_id = f"gmail_sync_{user_email}_{datetime.now(timezone.utc).timestamp()}"

    logger.info(f"Background Gmail sync started for user: {user_email} (task_id: {task_id})")
    logger.info(f"Sync is running independently and will NOT block other requests")

    return {
        "status": "started",
        "message": f"Gmail sync started in background for {user_email}",
        "user_email": user_email,
        "task_id": task_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "note": "Sync is running independently and will not block other CRM operations"
    }


# MANAGER TEAM SYNC ENDPOINTS
