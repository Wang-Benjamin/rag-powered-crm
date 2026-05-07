import logging
import uuid
import json
import asyncio
import time
import os
from datetime import datetime, timedelta, timezone
import httpx
from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Dict

from config.settings import settings

logger = logging.getLogger(__name__)

# Import auth and DB from service_core
from service_core.db import get_tenant_connection
from services.send_cap import check_daily_send_cap

from email_service.data.fetchers import (
    batch_build_email_generation_payloads,
    fetch_template_from_settings,
    fetch_clients_by_ids
)
from email_service.data.models import (
    PersonalizedMassEmailRequest,
    PersonalizedMassEmailSendRequest,
    ScheduleMassEmailRequest
)
from email_service.generation.personalized_generator import generate_single_personalized_email_crm
from temporalio.client import WorkflowFailureError
from temporalio.service import RPCError

# Temporal workflow imports
from temporal_workflows.worker import get_temporal_client, MASS_EMAIL_TASK_QUEUE, WORKFLOW_ID_PREFIX
from temporal_workflows.workflows import (
    PersonalizedMassEmailWorkflow,
    PersonalizedMassEmailWorkflowInput
)

router = APIRouter()


# ===== HELPERS =====

_TRADE_FIELDS = ("products", "fob_price", "fob_price_old", "certifications", "moq", "lead_time", "sample_status", "effective_date")


def _workflow_ids(kind: str, job_id: str) -> list[str]:
    """Return current and legacy workflow IDs for migration compatibility."""
    return [
        f"{WORKFLOW_ID_PREFIX}-{kind}-{job_id}",
        f"{kind}-{job_id}",
    ]


def _recipient_id_from_email(email: Dict) -> str | None:
    recipient_id = email.get("customer_id") or email.get("client_id")
    return str(recipient_id) if recipient_id is not None else None


def _email_identity(email: Dict) -> tuple[str | None, str]:
    to_email = (email.get("to_email") or email.get("client_email") or "").strip().lower()
    return (_recipient_id_from_email(email), to_email)


def _normalize_email_payloads(emails: list[Dict]) -> list[Dict]:
    normalized = []
    for idx, email in enumerate(emails):
        if not isinstance(email, dict):
            raise HTTPException(status_code=400, detail=f"Email at index {idx} is invalid")
        item = dict(email)
        if "client_id" not in item and item.get("clientId") is not None:
            item["client_id"] = item.get("clientId")
        if "client_id" not in item and item.get("customer_id") is not None:
            item["client_id"] = item.get("customer_id")
        if "client_id" not in item and item.get("customerId") is not None:
            item["client_id"] = item.get("customerId")
        if "to_email" not in item and item.get("client_email"):
            item["to_email"] = item.get("client_email")
        if "to_email" not in item and item.get("clientEmail"):
            item["to_email"] = item.get("clientEmail")
        if "to_email" not in item and item.get("toEmail"):
            item["to_email"] = item.get("toEmail")
        if "deal_id" not in item and item.get("dealId") is not None:
            item["deal_id"] = item.get("dealId")
        normalized.append(item)
    return normalized


def _validate_email_payloads(emails: list[Dict], modified_emails: list[Dict] | None = None) -> list[Dict]:
    """Validate mass-email payloads before campaign creation/workflow enqueue."""
    if not emails:
        raise HTTPException(status_code=400, detail="No emails provided")

    normalized = _normalize_email_payloads(emails)
    identities = set()
    for idx, email in enumerate(normalized):
        recipient_id, to_email = _email_identity(email)
        if not recipient_id:
            raise HTTPException(status_code=400, detail=f"Email at index {idx} is missing client_id/customer_id")
        if not to_email:
            raise HTTPException(status_code=400, detail=f"Email at index {idx} is missing to_email")
        if not str(email.get("subject") or "").strip():
            raise HTTPException(status_code=400, detail=f"Email at index {idx} is missing subject")
        if not str(email.get("body") or "").strip():
            raise HTTPException(status_code=400, detail=f"Email at index {idx} is missing body")
        identities.add((recipient_id, to_email))

    for idx, modified in enumerate(_normalize_email_payloads(modified_emails or [])):
        if _email_identity(modified) not in identities:
            raise HTTPException(
                status_code=400,
                detail=f"Modified email at index {idx} does not match any email being sent",
            )

    return normalized


async def _validate_explicit_deal_context(conn, emails: list[Dict]) -> None:
    """Ensure explicit deal_id context exists and belongs to the same client.

    deals.deal_id is a tenant-DB integer (alembic_postgres/models.py: Integer).
    Empty strings and non-numeric values are explicit input errors and rejected
    with 400 — silently skipping them lets a frontend bug push garbage forward.
    All deal_ids in the batch are checked in one round-trip.
    """
    indexed: list[tuple[int, int, int]] = []  # (idx, deal_id, recipient_id)
    for idx, email in enumerate(emails):
        deal_id_raw = email.get("deal_id")
        if deal_id_raw is None:
            continue
        if isinstance(deal_id_raw, str) and deal_id_raw.strip() == "":
            raise HTTPException(
                status_code=400,
                detail=f"Email at index {idx} has empty deal_id",
            )
        try:
            deal_id = int(deal_id_raw)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail=f"Email at index {idx} has invalid deal_id {deal_id_raw!r}",
            )

        recipient_raw = _recipient_id_from_email(email)
        if not recipient_raw:
            raise HTTPException(
                status_code=400,
                detail=f"Email at index {idx} has deal_id but no client_id",
            )
        try:
            recipient_id = int(recipient_raw)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail=f"Email at index {idx} has non-numeric client_id {recipient_raw!r}",
            )
        indexed.append((idx, deal_id, recipient_id))

    if not indexed:
        return

    rows = await conn.fetch(
        "SELECT deal_id, client_id FROM deals WHERE deal_id = ANY($1::int[])",
        [d for _, d, _ in indexed],
    )
    deal_to_client = {row["deal_id"]: row["client_id"] for row in rows}

    for idx, deal_id, recipient_id in indexed:
        if deal_id not in deal_to_client:
            raise HTTPException(
                status_code=400,
                detail=f"deal_id {deal_id} was not found",
            )
        if deal_to_client[deal_id] != recipient_id:
            raise HTTPException(
                status_code=400,
                detail=f"deal_id {deal_id} does not belong to client_id {recipient_id}",
            )


def _build_trade_context(request) -> dict:
    """Extract trade context fields from a request into a dict for campaign storage.

    Match outreach_router._trade_keys: keep fields explicitly set, even when
    falsy (empty list, "0", etc). Truthy filtering would diverge from the
    leadgen path the next time a field can be legitimately falsy.
    """
    return {f: getattr(request, f) for f in _TRADE_FIELDS if getattr(request, f, None) is not None}


# ===== PERSONALIZED MASS EMAIL GENERATION =====

# Configuration for concurrent email generation
MAX_CONCURRENT_GENERATIONS = settings.MAX_CONCURRENT_EMAIL_GENERATIONS


@router.post("/generate-personalized-mass-emails")
async def generate_personalized_mass_emails(
    request: PersonalizedMassEmailRequest,
    tenant: tuple = Depends(get_tenant_connection),
    authorization: str = Header(None)
) -> Dict:
    """
    Generate individual personalized emails for up to 50 customers using async parallel generation.

    Key differences from template mode:
    - Uses each customer's interaction history for personalization
    - Generates unique emails per customer (not a template)
    - Uses asyncio.gather() for parallel generation (5-50x faster than sequential)
    - Max 50 customers - personalized mode disabled for larger batches

    Performance:
    - Sequential (old): ~2-3s per email = 50-150s for 50 customers
    - Parallel (new): ~2-5s total regardless of count (up to semaphore limit)

    Each email is fully personalized using the customer's interaction history.

    Args:
        request: Personalized mass email request with customer_ids (max 25), custom_prompt

    Returns:
        List of personalized emails with processing time
    """
    try:
        conn, user = tenant
        customer_ids = request.customer_ids
        custom_prompt = request.custom_prompt or ""
        template_id = request.template_id
        strictness_level = request.strictness_level
        generation_mode = request.generation_mode

        # Validate max 25 customers
        if len(customer_ids) > 25:
            raise HTTPException(
                status_code=400,
                detail="Personalized mode limited to 25 customers maximum."
            )

        logger.info(f"Generating personalized emails for {len(customer_ids)} customers using parallel async generation")
        logger.info(f"Generation mode: {generation_mode}, template_id: {template_id}, strictness: {strictness_level}")

        user_email = user.get('email')
        user_name = user.get('name', 'Customer Success Manager')

        if not user_email:
            raise HTTPException(status_code=400, detail="User email not found in token")

        # Get employee info for proper name
        try:
            row = await conn.fetchrow(
                "SELECT employee_id, name, role, department FROM employee_info WHERE email = $1 LIMIT 1",
                user_email
            )
            if row:
                user_name = row.get("name", user_name)
        except Exception:
            pass

        # Fetch template if template mode is selected
        template = None
        if generation_mode == "template" and template_id:
            try:
                template = await fetch_template_from_settings(template_id, user_email, authorization)
            except Exception as e:
                logger.error(f"Failed to fetch template {template_id}: {e}")
                raise HTTPException(status_code=400, detail=f"Failed to fetch template: {str(e)}")

        # Generate emails in parallel using asyncio.gather() with rate limiting
        start_time = time.time()

        # Batch prefetch all data before parallel generation (reduces DB queries from 5xN to 5)
        logger.info(f"Batch prefetching data for {len(customer_ids)} customers...")
        prefetch_start = time.time()
        prefetched_payloads = await batch_build_email_generation_payloads(
            customer_ids=customer_ids,
            conn=conn,
            employee_id=None,
            user_email=user_email,
        )
        prefetch_time = time.time() - prefetch_start
        logger.info(f"Batch prefetch completed in {prefetch_time:.2f}s for {len(prefetched_payloads)} customers")

        logger.info(f"Starting parallel generation for {len(customer_ids)} customers (max {MAX_CONCURRENT_GENERATIONS} concurrent)")

        # Create semaphore for rate limiting concurrent API calls
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_GENERATIONS)

        async def generate_with_limit(customer_id, index):
            """Wrapper to apply semaphore rate limiting"""
            async with semaphore:
                return await generate_single_personalized_email_crm(
                    client_id=customer_id,
                    custom_prompt=custom_prompt,
                    conn=None,  # Safe: prefetched_payload includes signature_data, no DB needed
                    user_email=user_email,
                    user_name=user_name,
                    employee_id=None,
                    index=index,
                    total=len(customer_ids),
                    prefetched_payload=prefetched_payloads.get(customer_id),
                    template=template,
                    strictness_level=strictness_level,
                    generation_mode=generation_mode,
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
                )

        # Create tasks for all customers
        tasks = [
            generate_with_limit(
                customer_id=customer_ids[i],
                index=i
            )
            for i in range(len(customer_ids))
        ]

        # Execute all tasks in parallel with error handling
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build ordered per-recipient accounting. Keep `emails` for backward
        # compatibility, but never make callers infer dropped recipients from
        # a shrunken emails array.
        emails = []
        failed_count = 0
        skipped_count = 0
        recipient_results = []

        for i, result in enumerate(results):
            customer_id = customer_ids[i]
            recipient_id = str(customer_id)
            if isinstance(result, Exception):
                logger.error(f"Task {i+1} failed with exception: {result}")
                failed_count += 1
                recipient_results.append({
                    "recipient_id": recipient_id,
                    "status": "failed",
                    "reason": f"exception: {str(result)}",
                })
            elif result is not None:
                result["recipient_id"] = recipient_id
                emails.append(result)
                recipient_results.append({
                    "recipient_id": recipient_id,
                    "status": "generated",
                    "email": result,
                })
            else:
                # None return indicates generation failed but was handled.
                if prefetched_payloads.get(customer_id) is None:
                    skipped_count += 1
                    recipient_results.append({
                        "recipient_id": recipient_id,
                        "status": "skipped",
                        "reason": "missing_generation_context",
                    })
                else:
                    failed_count += 1
                    recipient_results.append({
                        "recipient_id": recipient_id,
                        "status": "failed",
                        "reason": "generation_returned_empty",
                    })

        processing_time = time.time() - start_time
        avg_time = processing_time / len(emails) if emails else 0
        logger.info(f"Parallel generation completed: {len(emails)}/{len(customer_ids)} emails in {processing_time:.1f}s (~{avg_time:.1f}s per email, {failed_count} failed, {skipped_count} skipped)")

        return {
            "emails": emails,
            "total": len(emails),
            "requested_total": len(customer_ids),
            "generated": len(emails),
            "failed": failed_count,
            "skipped": skipped_count,
            "recipient_results": recipient_results,
            "processing_time_seconds": processing_time
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in generate_personalized_mass_emails: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate personalized emails: {str(e)}")


@router.post("/send-personalized-mass-emails")
async def send_personalized_mass_emails(
    request: PersonalizedMassEmailSendRequest,
    tenant: tuple = Depends(get_tenant_connection)
) -> Dict:
    """
    Queue personalized mass email sending via Temporal workflow with anti-spam delays.

    Returns immediately with job_id - emails send asynchronously via Temporal.
    No template rendering needed - emails already have actual values.

    ANTI-SPAM STRATEGY:
    - Delays: 10-30 seconds between emails
    - Rate: ~120-360 emails per hour
    - Durable: Workflow survives server restarts

    Args:
        request: Personalized mass email send request with emails and provider

    Returns:
        Job info with estimated completion time
    """
    try:
        conn, user = tenant
        job_id = str(uuid.uuid4())
        emails = _validate_email_payloads(request.emails, request.modified_emails)
        await _validate_explicit_deal_context(conn, emails)
        provider = request.provider

        if len(emails) > 50:
            raise HTTPException(status_code=400, detail="Maximum 50 recipients per mass email send")
        await check_daily_send_cap(conn, pending=len(emails))

        user_email = user.get('email')
        user_name = user.get('name', 'Customer Success Manager')

        logger.info(f"Queuing personalized mass email job {job_id} for {len(emails)} customers")

        # Create campaign record and campaign_email rows
        campaign_name = f"Personalized -- {datetime.now(timezone.utc).strftime('%b %d')}"

        trade_ctx = _build_trade_context(request)

        campaign_row = await conn.fetchrow("""
            INSERT INTO campaigns (name, email_type, offer, ask, detail, custom_prompt, trade_context, recipient_count, status, sent_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'sending', NULL)
            RETURNING id
        """, campaign_name, 'personalized', request.offer, request.ask,
            request.detail, request.custom_prompt, trade_ctx if trade_ctx else {},
            len(emails))
        campaign_id = str(campaign_row['id'])

        all_customer_ids = [e.get('customer_id') or e.get('client_id') for e in emails if e.get('customer_id') or e.get('client_id')]
        if all_customer_ids:
            await conn.executemany(
                "INSERT INTO campaign_emails (campaign_id, customer_id) VALUES ($1, $2) ON CONFLICT (campaign_id, customer_id) DO NOTHING",
                [(campaign_id, cid) for cid in all_customer_ids],
            )

        logger.info(f"Created campaign {campaign_id} with {len(all_customer_ids)} recipients")

        # Calculate estimated completion time
        avg_delay_seconds = 40  # Average of 35-45 second delays
        estimated_time_minutes = (len(emails) * avg_delay_seconds) / 60
        estimated_completion_at = datetime.now(timezone.utc) + timedelta(minutes=estimated_time_minutes)

        # Start Temporal workflow
        try:
            temporal_client = await get_temporal_client()

            workflow_input = PersonalizedMassEmailWorkflowInput(
                job_id=job_id,
                emails=emails,
                provider=provider,
                user_email=user_email,
                user_name=user_name,
                modified_emails=_normalize_email_payloads(request.modified_emails or []),
                campaign_id=campaign_id,
            )

            await temporal_client.start_workflow(
                PersonalizedMassEmailWorkflow.run,
                workflow_input,
                id=f"{WORKFLOW_ID_PREFIX}-personalized-mass-email-{job_id}",
                task_queue=MASS_EMAIL_TASK_QUEUE,
                execution_timeout=timedelta(hours=2),
            )

            logger.info(f"Temporal workflow started for personalized mass email job {job_id}")

        except Exception as e:
            logger.error(f"Failed to start Temporal workflow: {e}")
            await conn.execute(
                "UPDATE campaigns SET status = 'failed' WHERE id = $1",
                campaign_id,
            )
            raise HTTPException(status_code=500, detail="Failed to start mass email workflow. Please try again.")

        # Return immediately with job info
        return {
            "job_id": job_id,
            "campaign_id": campaign_id,
            "workflow_id": f"{WORKFLOW_ID_PREFIX}-personalized-mass-email-{job_id}",
            "status": "queued",
            "message": f"Personalized mass email queued for sending. Estimated completion: ~{estimated_time_minutes:.0f} minutes",
            "total": len(emails),
            "sent": 0,
            "failed": 0,
            "estimated_completion_minutes": estimated_time_minutes
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error queuing personalized mass emails: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to queue personalized emails: {str(e)}")


@router.get("/mass-email-job/{job_id}")
async def get_mass_email_job_status(
    job_id: str,
    workflow_id: str = None,
    tenant: tuple = Depends(get_tenant_connection)
) -> Dict:
    """Get status of a background mass email job via Temporal workflow query."""
    try:
        temporal_client = await get_temporal_client()

        # Resolve workflow ID
        if workflow_id:
            wf_id = workflow_id
        else:
            # Try current env-prefixed IDs first, then legacy IDs.
            prefixes = [
                f"{WORKFLOW_ID_PREFIX}-personalized-mass-email-",
                f"{WORKFLOW_ID_PREFIX}-scheduled-mass-email-",
                f"{WORKFLOW_ID_PREFIX}-outreach-mass-send-",
                f"{WORKFLOW_ID_PREFIX}-scheduled-direct-email-",
                "personalized-mass-email-",
                "scheduled-mass-email-",
                "outreach-mass-send-",
                "scheduled-direct-email-",
            ]
            wf_id = None
            for prefix in prefixes:
                try:
                    handle = temporal_client.get_workflow_handle(f"{prefix}{job_id}")
                    await handle.describe()
                    wf_id = f"{prefix}{job_id}"
                    break
                except RPCError:
                    continue
            if not wf_id:
                raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        handle = temporal_client.get_workflow_handle(wf_id)

        # Try live query first (running workflow)
        try:
            progress = await handle.query(PersonalizedMassEmailWorkflow.get_progress)
            return progress
        except RPCError:
            pass

        # Workflow not running — try to get result (completed workflow)
        try:
            result = await handle.result()
            result["status"] = "completed"
            result["progress_percentage"] = 100
            return result
        except WorkflowFailureError:
            # Workflow failed — construct graceful response
            desc = await handle.describe()
            return {
                "job_id": job_id,
                "status": "failed",
                "total": 0,
                "sent": 0,
                "failed": 0,
                "errors": [f"Workflow {str(desc.status)}"],
                "progress_percentage": 0,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching job status: {e}")
        raise HTTPException(status_code=500, detail="Failed to check job status")


# ============================================================================
# SCHEDULED MASS EMAIL ENDPOINTS
# ============================================================================

@router.post("/schedule-mass-email")
async def schedule_mass_email(
    request: ScheduleMassEmailRequest,
    tenant: tuple = Depends(get_tenant_connection),
    authorization: str = Header(None)
) -> Dict:
    """Schedule a mass email for future delivery using Temporal start_delay."""
    try:
        conn, user = tenant
        if not request.emails:
            raise HTTPException(status_code=400, detail="emails required for personalized type")
        emails = _validate_email_payloads(request.emails, request.modified_emails)
        await _validate_explicit_deal_context(conn, emails)
        await check_daily_send_cap(conn, pending=len(emails))
        user_email = user.get('email')
        user_name = user.get('name', 'Customer Success Manager')

        # Parse and validate scheduled_at
        scheduled_at_dt = datetime.fromisoformat(request.scheduled_at.replace('Z', '+00:00'))
        if scheduled_at_dt.tzinfo is None:
            scheduled_at_dt = scheduled_at_dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if scheduled_at_dt <= now + timedelta(seconds=30):
            raise HTTPException(status_code=400, detail="Scheduled time must be at least 1 minute in the future")

        delay = scheduled_at_dt - now
        job_id = str(uuid.uuid4())

        # Create campaign record and campaign_email rows (mirrors send_personalized_mass_emails)
        campaign_name = f"Personalized -- {scheduled_at_dt.strftime('%b %d')} (Scheduled)"

        trade_ctx = _build_trade_context(request)

        campaign_row = await conn.fetchrow("""
            INSERT INTO campaigns (name, email_type, offer, ask, detail, custom_prompt, trade_context, recipient_count, status, sent_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'scheduled', NULL)
            RETURNING id
        """, campaign_name, 'personalized', request.offer, request.ask,
            request.detail, request.custom_prompt, trade_ctx if trade_ctx else {},
            len(emails))
        campaign_id = str(campaign_row['id'])

        all_customer_ids = [e.get('customer_id') or e.get('client_id') for e in emails if e.get('customer_id') or e.get('client_id')]
        if all_customer_ids:
            await conn.executemany(
                "INSERT INTO campaign_emails (campaign_id, customer_id) VALUES ($1, $2) ON CONFLICT (campaign_id, customer_id) DO NOTHING",
                [(campaign_id, cid) for cid in all_customer_ids],
            )

        logger.info(f"Created campaign {campaign_id} with {len(all_customer_ids)} recipients for scheduled job {job_id}")

        workflow_input = PersonalizedMassEmailWorkflowInput(
            job_id=job_id,
            emails=emails,
            provider=request.provider,
            user_email=user_email,
            user_name=user_name,
            modified_emails=_normalize_email_payloads(request.modified_emails or []),
            campaign_id=campaign_id,
        )

        temporal_client = await get_temporal_client()
        await temporal_client.start_workflow(
            PersonalizedMassEmailWorkflow.run,
            workflow_input,
            id=f"{WORKFLOW_ID_PREFIX}-scheduled-mass-email-{job_id}",
            task_queue=MASS_EMAIL_TASK_QUEUE,
            start_delay=delay,
            execution_timeout=timedelta(hours=2),
        )

        total_recipients = len(emails)
        template_name = "Personalized Email"
        payload = {"emails": emails, "provider": request.provider, "modified_emails": request.modified_emails}

        # Insert into database
        await conn.execute("""
            INSERT INTO scheduled_mass_emails
                (job_id, email_type, status, scheduled_at, payload, total_recipients, template_name, provider)
            VALUES ($1, $2, 'scheduled', $3, $4, $5, $6, $7)
        """, job_id, 'personalized', scheduled_at_dt, payload,
              total_recipients, template_name, request.provider)

        return {
            "success": True,
            "job_id": job_id,
            "campaign_id": campaign_id,
            "workflow_id": f"{WORKFLOW_ID_PREFIX}-scheduled-mass-email-{job_id}",
            "scheduled_at": scheduled_at_dt.isoformat(),
            "total_recipients": total_recipients,
            "message": f"Mass email scheduled for {scheduled_at_dt.strftime('%Y-%m-%d %H:%M UTC')}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scheduling mass email: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to schedule mass email: {str(e)}")


@router.get("/scheduled-mass-emails")
async def get_scheduled_mass_emails(
    page: int = None,
    per_page: int = None,
    tenant: tuple = Depends(get_tenant_connection)
) -> Dict:
    """List all scheduled mass emails."""
    try:
        conn, user = tenant
        user_email = user.get('email')

        from models.crm_models import paginated_response as build_paginated

        # Check past-due scheduled emails and update status via Temporal
        past_due_rows = await conn.fetch("""
            SELECT id, job_id FROM scheduled_mass_emails
            WHERE status = 'scheduled' AND scheduled_at <= NOW()
        """)
        for row in past_due_rows:
            new_status = 'completed'
            try:
                temporal_client = await get_temporal_client()
                desc = None
                for workflow_id in _workflow_ids("scheduled-mass-email", row["job_id"]):
                    try:
                        handle = temporal_client.get_workflow_handle(workflow_id)
                        desc = await handle.describe()
                        break
                    except Exception:
                        continue
                if desc is None:
                    raise RuntimeError("Scheduled mass-email workflow not found")
                wf_status = str(desc.status)
                if 'FAILED' in wf_status or 'TERMINATED' in wf_status or 'TIMED_OUT' in wf_status:
                    new_status = 'failed'
            except Exception:
                pass
            await conn.execute(
                "UPDATE scheduled_mass_emails SET status = $1, completed_at = NOW() WHERE id = $2",
                new_status, row['id']
            )

        base_query = """
            SELECT id as schedule_id, job_id, email_type, status, scheduled_at,
                   created_at, total_recipients, template_name, sent, failed, payload
            FROM scheduled_mass_emails
            WHERE status IN ('scheduled', 'in_progress', 'failed')
            ORDER BY scheduled_at DESC
        """

        if page is not None and per_page is not None:
            offset = (page - 1) * per_page
            paginated_query = f"""
                SELECT *, COUNT(*) OVER() AS _total_count
                FROM ({base_query}) _sub
                LIMIT $1 OFFSET $2
            """
            rows = await conn.fetch(paginated_query, per_page, offset)
        else:
            rows = await conn.fetch(base_query)

        total_from_db = None
        if page is not None and per_page is not None and rows:
            total_from_db = rows[0].get('_total_count', 0)

        items = []
        for row in rows:
            item = dict(row)
            item.pop('_total_count', None)
            # Query Temporal for live progress on in-progress items
            if item['status'] == 'in_progress' and item.get('job_id'):
                try:
                    temporal_client = await get_temporal_client()
                    progress = None
                    for workflow_id in _workflow_ids("scheduled-mass-email", item["job_id"]):
                        try:
                            handle = temporal_client.get_workflow_handle(workflow_id)
                            progress = await handle.query(PersonalizedMassEmailWorkflow.get_progress)
                            break
                        except Exception:
                            continue
                    if progress is None:
                        raise RuntimeError("Scheduled mass-email workflow not found")
                    item['sent'] = progress.get('sent', item['sent'])
                    item['failed'] = progress.get('failed', item['failed'])
                except Exception:
                    pass  # Fall through to DB values
            # Convert timestamps to strings
            for key in ('scheduled_at', 'created_at'):
                if item.get(key) and hasattr(item[key], 'isoformat'):
                    item[key] = item[key].isoformat()
            items.append(item)

        if total_from_db is not None:
            return build_paginated(items, total_from_db, page, per_page, key="scheduled_emails")

        return {"scheduled_emails": items, "total": len(items)}

    except Exception as e:
        logger.error(f"Error listing scheduled mass emails: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list scheduled emails: {str(e)}")


@router.delete("/scheduled-mass-emails/{schedule_id}")
async def cancel_scheduled_mass_email(
    schedule_id: int,
    tenant: tuple = Depends(get_tenant_connection)
) -> Dict:
    """Cancel a scheduled mass email."""
    try:
        conn, user = tenant
        user_email = user.get('email')

        row = await conn.fetchrow(
            "SELECT * FROM scheduled_mass_emails WHERE id = $1", schedule_id
        )

        if not row:
            raise HTTPException(status_code=404, detail="Scheduled email not found")

        if row['status'] != 'scheduled':
            raise HTTPException(status_code=400, detail=f"Cannot cancel email with status '{row['status']}'")

        # Cancel Temporal workflow
        try:
            temporal_client = await get_temporal_client()
            cancelled = False
            for workflow_id in _workflow_ids("scheduled-mass-email", row["job_id"]):
                try:
                    handle = temporal_client.get_workflow_handle(workflow_id)
                    await handle.cancel()
                    cancelled = True
                    break
                except Exception:
                    continue
            if not cancelled:
                raise RuntimeError("Scheduled mass-email workflow not found")
        except Exception as e:
            logger.warning(f"Failed to cancel Temporal workflow: {e}")

        # Update database
        await conn.execute("""
            UPDATE scheduled_mass_emails
            SET status = 'cancelled', cancelled_at = NOW()
            WHERE id = $1
        """, schedule_id)

        return {"success": True, "message": "Scheduled email cancelled"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling scheduled email: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel scheduled email: {str(e)}")
