import logging
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Dict

logger = logging.getLogger(__name__)

# Import auth and DB from service_core
from service_core.db import get_tenant_connection
from services.send_cap import check_daily_send_cap

from email_service.data.fetchers import (
    update_employee_writing_style_after_send,
    fetch_template_from_settings
)
from email_service.data.models import (
    EmailGenerationRequest,
    EmailSendRequest,
    ScheduleDirectEmailRequest,
)
from email_service.generation.personalized_generator import generate_single_personalized_email_crm
# Shared delivery
from email_core.delivery.send import send_email as send_email_via_provider
from email_service.delivery.provider_selector import select_provider
from temporal_workflows.worker import get_temporal_client, MASS_EMAIL_TASK_QUEUE, WORKFLOW_ID_PREFIX
from temporal_workflows.workflows import PersonalizedMassEmailWorkflow, PersonalizedMassEmailWorkflowInput

router = APIRouter()


@router.post("/generate-email")
async def generate_email(
    request: EmailGenerationRequest,
    tenant: tuple = Depends(get_tenant_connection),
    authorization: str = Header(None)
) -> Dict:
    """
    Generate email with auto data fetching.
    Delegates to generate_single_personalized_email_crm() for both custom and template modes.
    """
    try:
        conn, user = tenant
        user_email = user.get('email')
        user_name = user.get('name', 'Customer Success Manager')

        # Get employee_id from authenticated user
        employee_id = None
        try:
            row = await conn.fetchrow(
                "SELECT employee_id, name, role, department FROM employee_info WHERE email = $1 LIMIT 1",
                user_email
            )
            if row:
                employee_id = row["employee_id"]
                user_name = row.get("name", user_name)
            else:
                logger.warning(f"Employee not found for email {user_email}")
        except Exception as e:
            logger.warning(f"Error looking up employee for {user_email}: {e}")

        # Fetch template if template_id provided
        template = None
        if request.template_id:
            try:
                template = await fetch_template_from_settings(request.template_id, user_email, authorization)
            except Exception as e:
                logger.error(f"Failed to fetch template {request.template_id}: {e}")
                raise HTTPException(status_code=400, detail=f"Failed to fetch template: {str(e)}")

        # Delegate to existing helper (handles payload fetch, prompt building, AI gen, signature)
        result = await generate_single_personalized_email_crm(
            client_id=request.customer_id,
            custom_prompt=request.custom_prompt,
            conn=conn,
            user_email=user_email,
            user_name=user_name,
            employee_id=employee_id,
            index=0,
            total=1,
            template=template,
            strictness_level=request.strictness_level,
            generation_mode=request.generation_mode,
            trade_fields={
                'products': request.products,
                'fob_price': request.fob_price,
                'fob_price_old': request.fob_price_old,
                'certifications': request.certifications,
                'moq': request.moq,
                'lead_time': request.lead_time,
                'sample_status': request.sample_status,
                'effective_date': request.effective_date,
            } if any([request.products, request.fob_price, request.fob_price_old, request.certifications, request.moq, request.lead_time, request.sample_status, request.effective_date]) else None,
            language=request.language,
        )

        if result is None:
            raise HTTPException(status_code=500, detail="Failed to generate email")

        # Reshape to match individual endpoint format
        return {
            "email_data": {
                "subject": result["subject"],
                "body": result["body"],
                "to": result.get("client_email", ""),
                "customer_id": request.customer_id,
                "customer_company": result.get("client_name", ""),
                "customer_contact": result.get("primary_contact", ""),
                "sender_name": user_name,
                "sender_email": user_email,
            },
            "classification": result.get("classification"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in generate_email endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate email: {str(e)}"
        )

@router.get("/email-templates")
async def get_email_templates(
    tenant: tuple = Depends(get_tenant_connection)
) -> Dict:
    """Get available email templates."""
    templates = [
        {
            "id": "followup",
            "name": "Follow-up Email",
            "description": "Follow up on previous conversation or meeting"
        },
        {
            "id": "check_in",
            "name": "Check-in Email",
            "description": "Check in on customer status and satisfaction"
        },
        {
            "id": "renewal",
            "name": "Renewal Email",
            "description": "Discuss contract renewal and upsell opportunities"
        },
        {
            "id": "support",
            "name": "Support Email",
            "description": "Address customer concerns or issues"
        },
        {
            "id": "update",
            "name": "Product Update",
            "description": "Share new features or product improvements"
        }
    ]
    return {"templates": templates}

@router.post("/send-email")
async def send_email(
    request: EmailSendRequest,
    tenant: tuple = Depends(get_tenant_connection)
) -> Dict:
    """Send email to customer via Gmail/Outlook API with auto-refresh tokens."""
    try:
        conn, user = tenant
        await check_daily_send_cap(conn)
        logger.info(f"=== SEND EMAIL ENDPOINT CALLED ===")
        logger.info(f"To: {request.to_email}")
        logger.info(f"Subject: {request.subject}")
        logger.info(f"Customer ID: {request.customer_id}")
        logger.info(f"Provider: {request.provider}")
        logger.info(f"User: {user.get('email')}")

        user_email = user.get('email', 'support@company.com')
        user_name = user.get('name', 'Customer Success Manager')

        try:
            provider, provider_hint = await select_provider(user_email, request.provider)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Send via shared orchestrator (formatting → tracking → transport)
        result = await send_email_via_provider(
            provider=provider,
            user_email=user_email,
            to_email=request.to_email,
            subject=request.subject,
            body=request.body,
            from_email=user_email,
            from_name=user_name,
            reply_to_thread_id=request.reply_to_thread_id,
            reply_to_rfc_message_id=request.reply_to_rfc_message_id,
            provider_hint=provider_hint,
        )

        # Log sent email to database if customer_id provided
        if result.success and request.customer_id:
            try:
                user_email_for_logging = user.get('email')
                employee_id = None

                # Get employee_id for logging
                try:
                    emp_row = await conn.fetchrow(
                        "SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1",
                        user_email_for_logging
                    )
                    employee_id = emp_row["employee_id"] if emp_row else None
                    if employee_id:
                        logger.info(f"Found employee_id {employee_id} for user {user_email_for_logging}")
                except Exception as e:
                    logger.error(f"Failed to get employee_id for user {user_email_for_logging}: {e}")

                # Extract Gmail/Outlook message_id if available (for duplicate prevention during sync)
                message_id = result.message_id if hasattr(result, 'message_id') else None
                logger.info(f"Message ID from send response: {message_id}")

                # Use the actual send timestamp from the email provider if available, otherwise use current time
                sent_timestamp = result.sent_timestamp if hasattr(result, 'sent_timestamp') and result.sent_timestamp else datetime.now(timezone.utc)
                logger.info(f"Email sent timestamp: {sent_timestamp}")

                # Extract tracking data if available
                tracking_token = result.tracking_token if hasattr(result, 'tracking_token') else None
                tracking_expires_at = result.tracking_expires_at if hasattr(result, 'tracking_expires_at') else None

                # Insert into crm_emails table ONLY
                from data.repositories.email_repository import EmailRepository
                email_repo = EmailRepository()

                # Extract thread data if available
                thread_id = result.thread_id if hasattr(result, 'thread_id') else None
                rfc_message_id = result.rfc_message_id if hasattr(result, 'rfc_message_id') else None
                logger.info(f"Thread data from send response: thread_id={thread_id}, rfc_message_id={rfc_message_id}")

                email_id = await email_repo.insert_email(
                    conn=conn,
                    from_email=user_email,
                    to_email=request.to_email,
                    subject=request.subject,
                    body=request.body,
                    direction='sent',
                    customer_id=request.customer_id,
                    deal_id=request.deal_id,
                    employee_id=employee_id,
                    message_id=message_id,
                    thread_id=thread_id,
                    in_reply_to=request.reply_to_rfc_message_id,
                    rfc_message_id=rfc_message_id,
                    created_at=sent_timestamp,
                    tracking_token=tracking_token,
                    tracking_token_expires_at=tracking_expires_at
                )

                logger.info(f"Successfully logged email to crm_emails table: email_id={email_id}, message_id={message_id}")

                # Fire-and-forget: generate embedding for RAG search
                if email_id:
                    try:
                        import asyncio
                        from services.rag.embedding_sync_service import embed_single_email
                        asyncio.ensure_future(embed_single_email(user_email, email_id, request.subject, request.body))
                    except Exception as embed_err:
                        logger.debug(f"Email embedding skipped: {embed_err}")

                # Stage auto-progression (e.g. new → contacted)
                if email_id and request.customer_id:
                    try:
                        from services.stage_progression_service import apply_stage_progression
                        await apply_stage_progression(conn, request.customer_id)
                    except Exception as stage_err:
                        logger.debug(f"Stage progression skipped: {stage_err}")

            except Exception as e:
                logger.error(f"Failed to log email to database: {e}")
                logger.error(f"Email was sent but not logged.")

        # Check if email was actually sent successfully
        if result and result.success:
            # Update writing style from individually sent emails
            try:
                await update_employee_writing_style_after_send(
                    conn,
                    user_email,
                    [{'subject': request.subject, 'body': request.body}]
                )
            except Exception as e:
                logger.warning(f"Failed to update writing style: {e}")

            method = "gmail_api" if request.provider == "gmail" else "outlook_api"

            response_data = {
                "status": "success",
                "message": result.message if result else "Email sent successfully",
                "sent_to": request.to_email,
                "method": method
            }
            logger.info(f"Email sent successfully to {request.to_email}")
            logger.info(f"Response: {response_data}")
            return response_data
        else:
            # Email failed to send
            error_message = result.message or "Email provider returned no error detail"
            logger.error(f"Failed to send email to {request.to_email}: {error_message}")
            raise HTTPException(
                status_code=500,
                detail=error_message
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ERROR sending email: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send email: {str(e)}"
        )


# ============================================================================
# EMAIL THREAD ENDPOINTS
# ============================================================================

@router.get("/customers/{customer_id}/threads")
async def get_customer_email_threads(
    customer_id: int,
    limit: int = 50,
    tenant: tuple = Depends(get_tenant_connection)
) -> Dict:
    """
    Get all email threads for a customer.

    Returns a list of thread summaries with latest email info,
    grouped by thread_id (Gmail threadId or Outlook conversationId).
    """
    try:
        conn, user = tenant
        user_email = user.get('email')

        from data.repositories.email_repository import EmailRepository
        email_repo = EmailRepository()

        threads = await email_repo.get_all_threads(
            conn=conn,
            customer_id=customer_id,
            limit=limit
        )

        return {
            "customer_id": customer_id,
            "threads": threads,
            "total": len(threads)
        }

    except Exception as e:
        logger.error(f"Error retrieving threads for customer {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve threads: {str(e)}")


@router.get("/customers/{customer_id}/threads/{thread_id}")
async def get_customer_email_thread_detail(
    customer_id: int,
    thread_id: str,
    limit: int = 50,
    tenant: tuple = Depends(get_tenant_connection)
) -> Dict:
    """
    Get all emails in a specific thread.

    Returns emails in chronological order with full email content
    and RFC Message-ID for reply threading.
    """
    try:
        conn, user = tenant
        user_email = user.get('email')

        from data.repositories.email_repository import EmailRepository
        email_repo = EmailRepository()

        emails = await email_repo.get_emails_by_thread(
            conn=conn,
            thread_id=thread_id,
            customer_id=customer_id,
            limit=limit
        )

        if not emails:
            raise HTTPException(
                status_code=404,
                detail=f"Thread {thread_id} not found for customer {customer_id}"
            )

        return {
            "customer_id": customer_id,
            "thread_id": thread_id,
            "emails": emails,
            "total": len(emails)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving thread {thread_id} for customer {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve thread: {str(e)}")

@router.post("/schedule-direct-email")
async def schedule_direct_email(
    request: ScheduleDirectEmailRequest,
    tenant: tuple = Depends(get_tenant_connection),
) -> Dict:
    """Schedule a single direct email for future delivery via Temporal start_delay."""
    try:
        conn, user = tenant
        await check_daily_send_cap(conn)
        user_email = user.get("email")
        user_name = user.get("name", "Customer Success Manager")

        scheduled_at_dt = datetime.fromisoformat(request.scheduled_at.replace("Z", "+00:00"))
        if scheduled_at_dt.tzinfo is None:
            scheduled_at_dt = scheduled_at_dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if scheduled_at_dt <= now + timedelta(seconds=30):
            raise HTTPException(status_code=400, detail="Scheduled time must be at least 1 minute in the future")

        delay = scheduled_at_dt - now
        job_id = str(uuid.uuid4())

        # Get employee info
        try:
            row = await conn.fetchrow(
                "SELECT name FROM employee_info WHERE email = $1 LIMIT 1", user_email
            )
            if row:
                user_name = row.get("name", user_name)
        except Exception:
            pass

        # Create a lightweight campaign record for tracking
        campaign_row = await conn.fetchrow("""
            INSERT INTO campaigns (name, email_type, recipient_count, status, sent_at)
            VALUES ($1, 'direct', 1, 'scheduled', NULL)
            RETURNING id
        """, f"Direct -- {scheduled_at_dt.strftime('%b %d')} (Scheduled)")
        campaign_id = str(campaign_row["id"])

        if request.customer_id:
            await conn.execute(
                "INSERT INTO campaign_emails (campaign_id, customer_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                campaign_id, request.customer_id,
            )

        email_payload = {
            "client_id": request.customer_id,
            "to_email": request.to_email,
            "subject": request.subject,
            "body": request.body,
            "deal_id": request.deal_id,
        }

        workflow_input = PersonalizedMassEmailWorkflowInput(
            job_id=job_id,
            emails=[email_payload],
            provider=request.provider,
            user_email=user_email,
            user_name=user_name,
            modified_emails=[],
            campaign_id=campaign_id,
        )

        temporal_client = await get_temporal_client()
        await temporal_client.start_workflow(
            PersonalizedMassEmailWorkflow.run,
            workflow_input,
            id=f"{WORKFLOW_ID_PREFIX}-scheduled-direct-email-{job_id}",
            task_queue=MASS_EMAIL_TASK_QUEUE,
            start_delay=delay,
            execution_timeout=timedelta(hours=1),
        )

        logger.info(f"Scheduled direct email job {job_id} for {request.to_email} at {scheduled_at_dt}")
        return {
            "success": True,
            "job_id": job_id,
            "campaign_id": campaign_id,
            "scheduled_at": scheduled_at_dt.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scheduling direct email: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to schedule email: {str(e)}")
