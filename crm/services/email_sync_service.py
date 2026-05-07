"""Email sync service for CRM - handles email synchronization business logic"""

import logging
import re
import asyncpg
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any

from data.repositories.email_sync_repository import EmailSyncRepository
from data.repositories.employee_repository import EmployeeRepository
from services.employee_service import get_employee_id_by_email

logger = logging.getLogger(__name__)

# Initialize repositories
email_sync_repo = EmailSyncRepository()
employee_repo = EmployeeRepository()


async def get_email_sync_state(conn: asyncpg.Connection, employee_id: int = None) -> Optional[Dict[str, Any]]:
    """
    Get email sync state from database for specific employee.

    Args:
        conn: asyncpg connection for database access
        employee_id: Optional employee ID filter

    Returns:
        Dictionary with sync state or None
    """
    try:
        return await email_sync_repo.get_sync_state(conn, employee_id)
    except Exception as e:
        logger.error(f"Error getting sync state: {e}")
        return None


async def update_email_sync_state(conn: asyncpg.Connection, history_id: str, emails_synced: int, employee_id: int = None) -> bool:
    """
    Update email sync state in database for specific employee.

    Args:
        conn: asyncpg connection for database access
        history_id: Gmail history ID
        emails_synced: Number of emails synced
        employee_id: Optional employee ID filter

    Returns:
        True if successful
    """
    try:
        return await email_sync_repo.update_sync_state(conn, history_id, emails_synced, employee_id)
    except Exception as e:
        logger.error(f"Error updating sync state: {e}")
        raise


async def get_all_customer_emails(conn: asyncpg.Connection, employee_id: int = None) -> List[str]:
    """
    Get customer emails from database, optionally filtered by employee assignment.

    Args:
        conn: asyncpg connection for database access
        employee_id: Filter customers assigned to this employee (if None, returns all)

    Returns:
        List of customer email addresses
    """
    try:
        emails = await email_sync_repo.get_all_customer_emails(conn, employee_id)
        return [email.lower() for email in emails if email and email.strip()]
    except Exception as e:
        logger.error(f"Error fetching customer emails: {e}")
        return []


async def get_all_employee_emails(conn: asyncpg.Connection) -> List[str]:
    """
    Get all employee emails from database.

    Args:
        conn: asyncpg connection for database access

    Returns:
        List of employee email addresses
    """
    try:
        emails = await email_sync_repo.get_all_employee_emails(conn)
        return [email.lower() for email in emails if email and email.strip()]
    except Exception as e:
        logger.error(f"Error fetching employee emails: {e}")
        return []


async def get_customer_by_email(email: str, conn: asyncpg.Connection) -> Optional[Dict[str, Any]]:
    """
    Get customer info by email.

    Args:
        email: Customer email to lookup
        conn: asyncpg connection for database access

    Returns:
        Dictionary with customer info or None
    """
    try:
        customer = await email_sync_repo.find_customer_by_email(conn, email)
        if customer:
            return {
                'client_id': customer['client_id'],
                'client_name': customer['name'],
                'email': customer['email']
            }
        return None
    except Exception as e:
        logger.error(f"Error fetching customer by email: {e}")
        return None


async def get_employee_id_by_email_optional(email: str, conn: asyncpg.Connection) -> Optional[int]:
    """
    Get employee_id by email from employee_info table without throwing exception if not found.
    This is used for connected email scenarios where the employee might not exist.

    Args:
        email: Email to lookup
        conn: asyncpg connection for database access

    Returns:
        employee_id if found, None otherwise
    """
    try:
        employee_id = await employee_repo.find_id_by_email(email, conn)

        if not employee_id:
            logger.info(f"No employee found for email {email}")
            return None

        logger.info(f"Found employee_id {employee_id} for connected email {email}")
        return employee_id

    except Exception as e:
        logger.error(f"Error fetching employee_id for email {email}: {e}")
        return None


async def batch_create_email_interactions(conn: asyncpg.Connection, email_batch: List[Dict[str, Any]], include_body: bool = False, synced_by_employee_id: Optional[int] = None, user_email: str = None) -> int:
    """
    Batch create email records in crm_emails table.

    Note: Emails are stored in crm_emails only, NOT in interaction_details.
    The interaction_details table is reserved for calls and meetings.

    Args:
        conn: asyncpg connection for database access
        email_batch: List of email records, each containing:
            - customer_id: The customer ID
            - email_data: Email data including from, to, subject, etc.
            - employee_id: Employee ID
        include_body: Whether to include email body
        synced_by_employee_id: Optional ID of manager/user who performed the sync
        user_email: Authenticated user's email for employee matching

    Returns:
        Number of emails successfully inserted
    """
    if not email_batch:
        return 0

    inserted_count = 0

    try:
        # Pre-load ONLY the signed-in employee's data
        logger.info(f"Pre-loading signed-in employee data for batch insert (user: {user_email})...")

        employee_email_set = {user_email.lower()}
        employee_id_map = {}

        try:
            emp_id = await get_employee_id_by_email(conn, user_email)
            employee_id_map[user_email.lower()] = emp_id
            logger.info(f"Pre-loaded signed-in employee: {user_email} (ID: {emp_id})")
        except Exception as e:
            logger.error(f"Failed to get employee ID for {user_email}: {e}")

        # Prepare batch data for crm_emails insert
        email_records = []

        for email_record in email_batch:
            try:
                customer_id = email_record['customer_id']
                email_data = email_record['email_data']
                employee_id = email_record.get('employee_id')

                subject = email_data.get('subject', 'No Subject')
                body = email_data.get('body', '')
                stored_body = body if include_body else ""
                thread_id = email_data.get('thread_id')

                # Extract and parse from/to emails from email headers
                from_email_raw = email_data.get('from', '')
                to_email_raw = email_data.get('to', '')

                # Parse email addresses from fields (format: "Name <email@example.com>")
                email_pattern = r'<([^>]+)>|([^\s,;<]+@[^\s,;<]+)'

                from_email = from_email_raw
                from_match = re.search(email_pattern, from_email_raw)
                if from_match:
                    from_email = (from_match.group(1) or from_match.group(2)).strip()

                to_email = to_email_raw
                to_match = re.search(email_pattern, to_email_raw)
                if to_match:
                    to_email = (to_match.group(1) or to_match.group(2)).strip()

                # Determine direction based on actual email headers
                direction = 'received'
                if any(emp_email in from_email.lower() for emp_email in employee_email_set):
                    direction = 'sent'

                # Determine employee_id if not provided
                if employee_id is None:
                    email_pattern = r'<([^>]+@[^>]+)>|([^\s,;<]+@[^\s,;<]+)'

                    all_email_fields = [from_email, to_email, email_data.get('cc', '')]

                    for field in all_email_fields:
                        if not field:
                            continue
                        matches = re.findall(email_pattern, field)
                        for match in matches:
                            email_addr = (match[0] or match[1]).lower().strip()
                            if email_addr in employee_email_set:
                                employee_id = employee_id_map.get(email_addr)
                                if employee_id:
                                    logger.debug(f"Found employee_id {employee_id} for email: {email_addr}")
                                    break
                        if employee_id:
                            break

                    if employee_id is None:
                        logger.warning(f"No employee found in email fields for message {email_data.get('id', 'unknown')}. Skipping this email.")
                        continue

                # Use email's actual timestamp if available, otherwise use current time
                email_date = email_data.get('date')
                if email_date is None:
                    email_date = datetime.now(timezone.utc)
                    logger.warning(f"Email {email_data.get('id', 'unknown')} has no date field, using current time")

                email_record = (
                    customer_id,
                    employee_id,
                    email_data.get('id', ''),
                    email_date,
                    from_email,
                    to_email,
                    subject,
                    stored_body,
                    direction,
                    thread_id
                )
                email_records.append(email_record)

            except Exception as record_error:
                logger.error(f"Error preparing email record for batch insert: {record_error}")
                continue

        if not email_records:
            logger.warning("No valid email records to batch insert")
            return 0

        # Batch insert into crm_emails table ONLY
        from data.repositories.email_repository import EmailRepository
        email_repo = EmailRepository()

        inserted_count = 0
        for record in email_records:
            try:
                (customer_id, employee_id,
                 gmail_message_id, created_at,
                 from_email, to_email, subject, body, direction, thread_id) = record

                # Check if email already exists BEFORE classification
                existing = await conn.fetchrow("""
                    SELECT 1 FROM crm_emails WHERE message_id = $1
                """, gmail_message_id)
                email_exists = existing is not None

                if email_exists:
                    logger.debug(f"Email already exists, skipping: {gmail_message_id}")

                # Insert into crm_emails using actual email data from headers
                email_id = await email_repo.insert_email(
                    conn,
                    from_email=from_email,
                    to_email=to_email,
                    subject=subject,
                    body=body,
                    direction=direction,
                    customer_id=customer_id,
                    deal_id=None,
                    employee_id=employee_id,
                    message_id=gmail_message_id,
                    thread_id=thread_id,
                    created_at=created_at
                )

                if email_id:
                    inserted_count += 1
                    logger.debug(f"NEW email inserted: {email_id}")

                    # Fire-and-forget: generate embedding for RAG search
                    try:
                        import asyncio
                        from services.rag.embedding_sync_service import embed_single_email
                        asyncio.ensure_future(embed_single_email(user_email, email_id, subject, body))
                    except Exception as embed_err:
                        logger.debug(f"Email embedding skipped: {embed_err}")
                else:
                    logger.debug(f"Email already exists, skipped: {gmail_message_id}")

            except Exception as e:
                logger.error(f"Error inserting email to crm_emails: {e}")
                continue

        logger.info(f"Batch database insert: {inserted_count} emails inserted from {len(email_batch)} processed")

        return inserted_count

    except Exception as e:
        logger.error(f"Error in batch email creation: {e}")
        return 0


async def create_email_interaction(conn: asyncpg.Connection, customer_id: int, email_data: Dict[str, Any], include_body: bool = False, employee_id: Optional[int] = None, synced_by_employee_id: Optional[int] = None, user_email: str = None) -> bool:
    """Create email record in crm_emails table.

    Note: Emails are stored in crm_emails only, NOT in interaction_details.
    The interaction_details table is reserved for calls and meetings.

    Args:
        conn: asyncpg connection for database access
        customer_id: The customer ID
        email_data: Email data including from, to, subject, etc.
        include_body: Whether to include email body
        employee_id: Optional employee ID (if not provided, will try to extract from sender email)
        synced_by_employee_id: Optional ID of manager/user who performed the sync
    """
    try:
        subject = email_data.get('subject', 'No Subject')
        body = email_data.get('body', '')

        # Get email date
        email_date = email_data.get('date')

        # Use provided employee_id or try to find from email
        if employee_id is None:
            all_email_fields = []
            from_field = email_data.get('from', '')
            to_field = email_data.get('to', '')
            cc_field = email_data.get('cc', '')

            if from_field:
                all_email_fields.append(from_field)
            if to_field:
                all_email_fields.append(to_field)
            if cc_field:
                all_email_fields.append(cc_field)

            logger.debug(f"Looking for employee in email fields: from={from_field}, to={to_field}, cc={cc_field}")

            email_pattern = r'<([^>]+@[^>]+)>|([^\s,;<]+@[^\s,;<]+)'

            for field in all_email_fields:
                matches = re.findall(email_pattern, field)
                for match in matches:
                    email_addr = (match[0] or match[1]).lower().strip()
                    if email_addr:
                        logger.debug(f"Checking if {email_addr} is an employee...")
                        result = await conn.fetchrow("SELECT employee_id FROM employee_info WHERE LOWER(email) = LOWER($1)", email_addr)
                        if result:
                            employee_id = result['employee_id']
                            logger.debug(f"Found employee_id {employee_id} for email: {email_addr}")
                            break

                if employee_id:
                    break

            if not employee_id:
                logger.warning(f"No employee found in any email field (from/to/cc). Skipping this email.")
                return False
        else:
            logger.debug(f"Using provided employee_id: {employee_id}")

        # Extract from/to emails from email_data
        from_email = email_data.get('from', 'unknown@example.com')
        to_email = email_data.get('to', 'unknown@example.com')

        # Parse email addresses from fields (format: "Name <email@example.com>")
        email_pattern = r'<([^>]+)>|([^\s,;<]+@[^\s,;<]+)'

        from_match = re.search(email_pattern, from_email)
        if from_match:
            from_email = (from_match.group(1) or from_match.group(2)).strip()

        to_match = re.search(email_pattern, to_email)
        if to_match:
            to_email = (to_match.group(1) or to_match.group(2)).strip()

        # Parse subject and body
        subject = email_data.get('subject', 'No Subject')
        body = email_data.get('body', '')
        if not include_body:
            body = ""

        # Determine email direction based on employee email
        direction = 'received'
        try:
            employee_result = await conn.fetchrow("SELECT email FROM employee_info WHERE employee_id = $1", employee_id)
            if employee_result:
                employee_email = employee_result['email'].lower() if employee_result['email'] else ''
                if employee_email and employee_email in from_email.lower():
                    direction = 'sent'
                    logger.debug(f"Email direction: sent (employee {employee_email} in from field)")
                else:
                    direction = 'received'
                    logger.debug(f"Email direction: received (employee {employee_email} not in from field)")
        except Exception as e:
            logger.warning(f"Could not determine email direction, defaulting to 'received': {e}")
            direction = 'received'

        # Insert into crm_emails table ONLY
        from data.repositories.email_repository import EmailRepository
        email_repo = EmailRepository()

        # Extract thread_id for conversation tracking
        thread_id = email_data.get('thread_id')

        try:
            email_id = await email_repo.insert_email(
                conn,
                from_email=from_email,
                to_email=to_email,
                subject=subject,
                body=body if body else "",
                direction=direction,
                customer_id=customer_id,
                deal_id=None,
                employee_id=employee_id,
                message_id=email_data.get('id'),
                thread_id=thread_id,
                created_at=email_date or datetime.now(timezone.utc)
            )

            inserted = email_id is not None

            if inserted:
                logger.debug(f"Successfully created email in crm_emails: email_id={email_id} for customer {customer_id}")

                # Fire-and-forget: generate embedding for RAG search
                try:
                    import asyncio
                    from services.rag.embedding_sync_service import embed_single_email
                    asyncio.ensure_future(embed_single_email(user_email, email_id, subject, body))
                except Exception as embed_err:
                    logger.debug(f"Email embedding skipped: {embed_err}")
            else:
                logger.debug(f"Email already exists for message_id: {email_data.get('id')}")

            return inserted

        except Exception as e:
            logger.error(f"Error inserting to crm_emails: {e}")
            return False
    except Exception as e:
        logger.error(f"Error creating email interaction: {e}")
        return False
