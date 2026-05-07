"""Initial outreach router for first-contact emails from the Buyers page.

Two-step flow: generate draft -> user edits -> send.
Uses BoL intelligence for email generation, separate from CRM's follow-up prompt builder.
"""

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Depends, Header, Request
from pydantic import BaseModel, Field

from service_core.db import get_tenant_connection
from services.send_cap import check_daily_send_cap

from email_service.outreach.bol_intelligence import build_bol_intelligence
from email_service.outreach.fetchers import (
    batch_fetch_leads,
    batch_build_email_generation_payloads,
)
from email_service.outreach.prompt_builder import build_lead_email_prompt
from email_service.data.fetchers import (
    fetch_email_samples,
    fetch_employee_writing_style,
    fetch_audience_context,
)
from email_core.generator import generate_email_with_ai
from email_core.delivery.signature_formatter import attach_signature_to_email
from email_core.delivery.send import send_email as send_email_via_provider
from email_service.delivery.provider_selector import select_provider

# Temporal workflow imports
from temporal_workflows.worker import get_temporal_client, MASS_EMAIL_TASK_QUEUE, WORKFLOW_ID_PREFIX
from temporal_workflows.workflows import (
    PersonalizedMassEmailWorkflow,
    PersonalizedMassEmailWorkflowInput,
)

logger = logging.getLogger(__name__)

router = APIRouter()

LEADGEN_SERVICE_URL = os.getenv("LEADGEN_SERVICE_URL", "http://localhost:9000")

# Always use trade advisor persona (agentic mode)
TRADE_ADVISOR_PERSONA = (
    "You are an international trade advisor helping a manufacturer "
    "communicate with North American buyers."
)


def _lead_email_identity(email: Dict) -> tuple[str | None, str]:
    lead_id = email.get("lead_id") or email.get("leadId")
    to_email = (email.get("to_email") or email.get("toEmail") or "").strip().lower()
    return (str(lead_id) if lead_id is not None else None, to_email)


def _validate_lead_email_payloads(emails: List[Dict], modified_emails: List[Dict] | None = None) -> List[Dict]:
    """Validate initial-outreach mass payloads before lead resolution/enqueue."""
    if not emails:
        raise HTTPException(status_code=400, detail="No emails provided")

    normalized = []
    for idx, email in enumerate(emails):
        if not isinstance(email, dict):
            raise HTTPException(status_code=400, detail=f"Email at index {idx} is invalid")
        item = dict(email)
        if "lead_id" not in item and item.get("leadId") is not None:
            item["lead_id"] = item.get("leadId")
        if "to_email" not in item and item.get("toEmail"):
            item["to_email"] = item.get("toEmail")
        normalized.append(item)
    identities = set()
    for idx, email in enumerate(normalized):
        lead_id, to_email = _lead_email_identity(email)
        if not lead_id:
            raise HTTPException(status_code=400, detail=f"Email at index {idx} is missing lead_id")
        if not to_email:
            raise HTTPException(status_code=400, detail=f"Email at index {idx} is missing to_email")
        if not str(email.get("subject") or "").strip():
            raise HTTPException(status_code=400, detail=f"Email at index {idx} is missing subject")
        if not str(email.get("body") or "").strip():
            raise HTTPException(status_code=400, detail=f"Email at index {idx} is missing body")
        identities.add((lead_id, to_email))

    for idx, modified in enumerate(modified_emails or []):
        if _lead_email_identity(modified) not in identities:
            raise HTTPException(
                status_code=400,
                detail=f"Modified email at index {idx} does not match any email being sent",
            )

    return normalized


# ============================================================================
# REQUEST MODELS
# ============================================================================


class InitialOutreachGenerateRequest(BaseModel):
    lead_id: str  # UUID
    import_context: Optional[dict] = None
    supplier_context: Optional[dict] = None
    offer: Optional[str] = None
    ask: Optional[str] = None
    detail: Optional[str] = None
    custom_prompt: Optional[str] = None
    template_id: Optional[str] = None
    strictness_level: int = 50
    generation_mode: str = "custom"
    products: Optional[List[dict]] = None
    fob_price: Optional[str] = None
    fob_price_old: Optional[str] = None
    certifications: Optional[List[str]] = None
    moq: Optional[str] = None
    lead_time: Optional[str] = None
    sample_status: Optional[str] = None
    effective_date: Optional[str] = None


class InitialOutreachSendRequest(BaseModel):
    lead_id: str  # UUID
    subject: str
    body: str
    to_email: str
    provider: Optional[str] = None


class InitialOutreachMassGenerateRequest(BaseModel):
    lead_ids: List[str]  # UUIDs
    import_contexts: Optional[Dict[str, dict]] = None  # lead_id -> import_context
    supplier_contexts: Optional[Dict[str, dict]] = None  # lead_id -> supplier_context
    custom_prompt: Optional[str] = None
    template_id: Optional[str] = None
    strictness_level: int = 50
    generation_mode: str = "custom"
    products: Optional[List[dict]] = None
    fob_price: Optional[str] = None
    fob_price_old: Optional[str] = None
    certifications: Optional[List[str]] = None
    moq: Optional[str] = None
    lead_time: Optional[str] = None
    sample_status: Optional[str] = None
    effective_date: Optional[str] = None


class InitialOutreachMassSendRequest(BaseModel):
    emails: List[Dict]  # [{lead_id, subject, body, to_email}, ...]
    modified_emails: List[Dict] = Field(default_factory=list, description="User-edited emails for writing style update")
    provider: Optional[str] = None
    campaign_name: Optional[str] = None
    # Trade fields for campaign tracking (persisted as trade_context on the campaign row)
    products: Optional[List[dict]] = None
    fob_price: Optional[str] = None
    fob_price_old: Optional[str] = None
    certifications: Optional[List[str]] = None
    moq: Optional[str] = None
    lead_time: Optional[str] = None
    sample_status: Optional[str] = None
    effective_date: Optional[str] = None


class InitialOutreachScheduleRequest(BaseModel):
    scheduled_at: str
    lead_id: str
    subject: str
    body: str
    to_email: str
    provider: Optional[str] = None


class InitialOutreachMassScheduleRequest(BaseModel):
    scheduled_at: str
    emails: List[Dict]  # [{lead_id, subject, body, to_email}, ...]
    modified_emails: List[Dict] = Field(default_factory=list)
    provider: Optional[str] = None
    campaign_name: Optional[str] = None


# ============================================================================
# DASHBOARD METRICS
# ============================================================================


@router.get("/outreach/weekly")
async def get_outreach_weekly(
    tenant: tuple = Depends(get_tenant_connection),
) -> Dict:
    """Return last-7-days outreach + reply counts.

    Admins see tenant-wide totals; regular users see their own. Counts raw
    crm_emails so the number reflects all outreach (campaign + ad-hoc), not
    just per-campaign sends.
    """
    conn, user = tenant
    user_email = user.get("email", "")
    emp_row = await conn.fetchrow(
        "SELECT employee_id, access FROM employee_info WHERE email = $1 LIMIT 1",
        user_email,
    )
    if not emp_row:
        return {"outreachWeek": 0, "repliesWeek": 0}

    is_admin = (emp_row["access"] or "").lower() == "admin"
    if is_admin:
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE direction = 'sent') AS outreach_week,
                COUNT(*) FILTER (WHERE direction = 'received') AS replies_week
            FROM crm_emails
            WHERE created_at >= NOW() - INTERVAL '7 days'
            """
        )
    else:
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE direction = 'sent') AS outreach_week,
                COUNT(*) FILTER (WHERE direction = 'received') AS replies_week
            FROM crm_emails
            WHERE employee_id = $1
              AND created_at >= NOW() - INTERVAL '7 days'
            """,
            emp_row["employee_id"],
        )
    return {
        "outreachWeek": int(row["outreach_week"] or 0),
        "repliesWeek": int(row["replies_week"] or 0),
    }


# ============================================================================
# SINGLE ENDPOINTS
# ============================================================================


@router.post("/initial-outreach/generate")
async def generate_initial_outreach(
    request: InitialOutreachGenerateRequest,
    tenant: tuple = Depends(get_tenant_connection),
) -> Dict:
    """Generate a draft email for initial outreach to a BoL lead.

    Does NOT send or create CRM record - user may edit first.
    """
    try:
        conn, user = tenant
        user_email = user.get("email")
        user_name = user.get("name", "Customer Success Manager")

        # Get employee info
        try:
            row = await conn.fetchrow(
                "SELECT employee_id, name FROM employee_info WHERE email = $1 LIMIT 1",
                user_email,
            )
            if row:
                user_name = row.get("name", user_name)
        except Exception as e:
            logger.warning(f"Error looking up employee for {user_email}: {e}")

        # 1. Build buyer intelligence from passed BoL context
        buyer_intelligence = build_bol_intelligence(
            request.import_context,
            request.supplier_context,
        )

        # 2. Fetch lead data from leads table
        leads = await batch_fetch_leads(conn, [request.lead_id])
        lead_data = leads.get(request.lead_id)
        if not lead_data:
            raise HTTPException(status_code=404, detail="Lead not found")

        # If no BoL context passed in request, try from lead's stored data
        if not buyer_intelligence:
            buyer_intelligence = build_bol_intelligence(
                lead_data.get("import_context"),
                lead_data.get("supplier_context"),
            )

        # 3. Fetch shared data from CRM's existing fetchers
        email_samples = await fetch_email_samples(conn, user_email)
        writing_style = await fetch_employee_writing_style(conn, user_email)
        audience_context = await fetch_audience_context(conn)

        # 4. Build trade fields
        trade_fields = {}
        for field in ("products", "fob_price", "fob_price_old", "certifications", "moq", "lead_time", "sample_status", "effective_date"):
            val = getattr(request, field, None)
            if val is not None:
                trade_fields[field] = val

        # 5. Generate email with build_lead_email_prompt
        prompt = build_lead_email_prompt(
            lead_data=lead_data,
            email_history=[],  # Initial outreach = no history
            notes="",
            email_samples=email_samples,
            user_name=user_name,
            writing_style=writing_style,
            custom_prompt=request.custom_prompt,
            buyer_intelligence=buyer_intelligence,
            manufacturer_name=audience_context.get("company_name") if audience_context else None,
            **trade_fields,
        )

        # 6. Call AI generation
        result = await generate_email_with_ai(prompt, persona=TRADE_ADVISOR_PERSONA)

        # Attach signature
        try:
            result = await attach_signature_to_email(result, user_email, conn)
        except Exception as e:
            logger.warning(f"Failed to attach signature for lead {request.lead_id}: {e}")

        # 7. Return draft
        return {
            "subject": result["email_data"]["subject"],
            "body": result["email_data"]["body"],
            "to_email": lead_data.get("email", ""),
            "lead_id": request.lead_id,
            "lead_company": lead_data.get("company", "Unknown"),
            "classification": result.get("classification"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating initial outreach for lead {request.lead_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate email: {str(e)}")


@router.post("/initial-outreach/send")
async def send_initial_outreach(
    request: InitialOutreachSendRequest,
    raw_request: Request,
    tenant: tuple = Depends(get_tenant_connection),
) -> Dict:
    """Send the (possibly edited) initial outreach email.

    1. Resolves lead -> customer via leadgen's add-to-crm endpoint
    2. Sends the email via provider
    3. Logs to crm_emails
    """
    try:
        conn, user = tenant
        await check_daily_send_cap(conn)
        user_email = user.get("email")
        user_name = user.get("name", "Customer Success Manager")

        # Get employee info
        employee_id = None
        try:
            row = await conn.fetchrow(
                "SELECT employee_id, name FROM employee_info WHERE email = $1 LIMIT 1",
                user_email,
            )
            if row:
                employee_id = row["employee_id"]
                user_name = row.get("name", user_name)
        except Exception as e:
            logger.warning(f"Error looking up employee for {user_email}: {e}")

        # 1. Resolve lead -> customer via leadgen's add-to-crm endpoint
        auth_header = raw_request.headers.get("authorization", "")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{LEADGEN_SERVICE_URL}/api/leads/{request.lead_id}/add-to-crm",
                headers={"Authorization": auth_header},
                json={},
            )
            if resp.status_code != 200:
                logger.error(f"add-to-crm failed: {resp.status_code} {resp.text}")
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=f"Failed to create CRM customer: {resp.text}",
                )
            crm_result = resp.json()
            customer_id = crm_result.get("crm_customer_id")

        if not customer_id:
            raise HTTPException(status_code=500, detail="No customer_id returned from CRM integration")

        # 2. Select provider
        try:
            provider, provider_hint = await select_provider(user_email, request.provider)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # 3. Send email
        send_result = await send_email_via_provider(
            provider=provider,
            user_email=user_email,
            to_email=request.to_email,
            subject=request.subject,
            body=request.body,
            from_email=user_email,
            from_name=user_name,
            provider_hint=provider_hint,
        )

        if not send_result or not send_result.success:
            error_msg = send_result.message if send_result else "Unknown error"
            raise HTTPException(status_code=500, detail=f"Failed to send email: {error_msg}")

        # 4. Log to DB
        email_id = None
        try:
            from data.repositories.email_repository import EmailRepository

            email_repo = EmailRepository()

            message_id = send_result.message_id if hasattr(send_result, "message_id") else None
            thread_id = send_result.thread_id if hasattr(send_result, "thread_id") else None
            rfc_message_id = send_result.rfc_message_id if hasattr(send_result, "rfc_message_id") else None
            tracking_token = send_result.tracking_token if hasattr(send_result, "tracking_token") else None
            tracking_expires = send_result.tracking_expires_at if hasattr(send_result, "tracking_expires_at") else None
            sent_ts = send_result.sent_timestamp if hasattr(send_result, "sent_timestamp") and send_result.sent_timestamp else datetime.now(timezone.utc)

            email_id = await email_repo.insert_email(
                conn=conn,
                from_email=user_email,
                to_email=request.to_email,
                subject=request.subject,
                body=request.body,
                direction="sent",
                customer_id=customer_id,
                employee_id=employee_id,
                message_id=message_id,
                thread_id=thread_id,
                rfc_message_id=rfc_message_id,
                created_at=sent_ts,
                tracking_token=tracking_token,
                tracking_token_expires_at=tracking_expires,
            )
            logger.info(f"Logged outreach email: email_id={email_id}, customer_id={customer_id}")
        except Exception as e:
            logger.error(f"Failed to log outreach email to database: {e}")

        # Stage auto-progression
        if email_id and customer_id:
            try:
                from services.stage_progression_service import apply_stage_progression
                await apply_stage_progression(conn, customer_id)
            except Exception as stage_err:
                logger.debug(f"Stage progression skipped: {stage_err}")

        return {
            "email_id": email_id,
            "customer_id": customer_id,
            "success": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending initial outreach for lead {request.lead_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")


@router.post("/initial-outreach/schedule")
async def schedule_initial_outreach(
    request: InitialOutreachScheduleRequest,
    raw_request: Request,
    tenant: tuple = Depends(get_tenant_connection),
) -> Dict:
    """Schedule a single initial outreach email for future delivery."""
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

        try:
            row = await conn.fetchrow(
                "SELECT name FROM employee_info WHERE email = $1 LIMIT 1", user_email
            )
            if row:
                user_name = row.get("name", user_name)
        except Exception:
            pass

        # Resolve lead -> customer
        auth_header = raw_request.headers.get("authorization", "")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{LEADGEN_SERVICE_URL}/api/leads/{request.lead_id}/add-to-crm",
                headers={"Authorization": auth_header},
                json={},
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=f"Failed to create CRM customer: {resp.text}")
            customer_id = resp.json().get("crm_customer_id")

        if not customer_id:
            raise HTTPException(status_code=500, detail="No customer_id returned from CRM integration")

        # Create campaign record
        campaign_row = await conn.fetchrow("""
            INSERT INTO campaigns (name, email_type, recipient_count, status, sent_at)
            VALUES ($1, 'initial_outreach', 1, 'scheduled', NULL)
            RETURNING id
        """, f"Initial Outreach -- {scheduled_at_dt.strftime('%b %d')} (Scheduled)")
        campaign_id = str(campaign_row["id"])
        await conn.execute(
            "INSERT INTO campaign_emails (campaign_id, customer_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            campaign_id, customer_id,
        )

        workflow_input = PersonalizedMassEmailWorkflowInput(
            job_id=job_id,
            emails=[{"client_id": customer_id, "to_email": request.to_email, "subject": request.subject, "body": request.body}],
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
            id=f"{WORKFLOW_ID_PREFIX}-scheduled-outreach-{job_id}",
            task_queue=MASS_EMAIL_TASK_QUEUE,
            start_delay=delay,
            execution_timeout=timedelta(hours=1),
        )

        logger.info(f"Scheduled initial outreach {job_id} for {request.to_email} at {scheduled_at_dt}")
        return {"success": True, "job_id": job_id, "campaign_id": campaign_id, "scheduled_at": scheduled_at_dt.isoformat()}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scheduling initial outreach for lead {request.lead_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to schedule email: {str(e)}")


# ============================================================================
# MASS ENDPOINTS
# ============================================================================


@router.post("/initial-outreach-mass/generate")
async def generate_initial_outreach_mass(
    request: InitialOutreachMassGenerateRequest,
    tenant: tuple = Depends(get_tenant_connection),
) -> Dict:
    """Batch generate draft emails for multiple BoL leads."""
    try:
        conn, user = tenant
        user_email = user.get("email")
        user_name = user.get("name", "Customer Success Manager")

        if len(request.lead_ids) > 50:
            raise HTTPException(status_code=400, detail="Maximum 50 leads per batch")

        # Get employee info
        try:
            row = await conn.fetchrow(
                "SELECT employee_id, name FROM employee_info WHERE email = $1 LIMIT 1",
                user_email,
            )
            if row:
                user_name = row.get("name", user_name)
        except Exception:
            pass

        # Batch fetch all lead data + shared data
        payloads = await batch_build_email_generation_payloads(
            conn, request.lead_ids, user_email
        )

        # Build trade fields
        trade_fields = {}
        for field in ("products", "fob_price", "fob_price_old", "certifications", "moq", "lead_time", "sample_status", "effective_date"):
            val = getattr(request, field, None)
            if val is not None:
                trade_fields[field] = val

        import_contexts = request.import_contexts or {}
        supplier_contexts = request.supplier_contexts or {}

        # Generate emails for each lead
        import asyncio

        MAX_CONCURRENT = 5
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        async def generate_one(lead_id: str) -> Optional[Dict]:
            async with semaphore:
                payload = payloads.get(lead_id)
                if not payload:
                    return None

                lead_data = payload["lead_data"]

                # Build buyer intelligence: prefer request context, fall back to DB
                buyer_intelligence = build_bol_intelligence(
                    import_contexts.get(lead_id, lead_data.get("import_context")),
                    supplier_contexts.get(lead_id, lead_data.get("supplier_context")),
                )

                audience_context = payload.get("audience_context")
                prompt = build_lead_email_prompt(
                    lead_data=lead_data,
                    email_history=[],
                    notes="",
                    email_samples=payload.get("email_samples", []),
                    user_name=user_name,
                    writing_style=payload.get("writing_style"),
                    custom_prompt=request.custom_prompt,
                    buyer_intelligence=buyer_intelligence,
                    manufacturer_name=audience_context.get("company_name") if audience_context else None,
                    **trade_fields,
                )

                try:
                    result = await generate_email_with_ai(prompt, persona=TRADE_ADVISOR_PERSONA)
                    try:
                        # Use prefetched signature_data — concurrent fetchrow on
                        # the shared `conn` would race with sibling tasks.
                        result = await attach_signature_to_email(
                            result,
                            user_email,
                            signature_data=payload.get("signature_data"),
                        )
                    except Exception:
                        pass

                    return {
                        "lead_id": lead_id,
                        "subject": result["email_data"]["subject"],
                        "body": result["email_data"]["body"],
                        "to_email": lead_data.get("email", ""),
                        "lead_company": lead_data.get("company", "Unknown"),
                        "classification": result.get("classification"),
                    }
                except Exception as e:
                    logger.error(f"Failed to generate email for lead {lead_id}: {e}")
                    return None

        tasks = [generate_one(lid) for lid in request.lead_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        emails = []
        failed = 0
        skipped = 0
        recipient_results = []
        for idx, r in enumerate(results):
            lead_id = request.lead_ids[idx]
            recipient_id = str(lead_id)
            if isinstance(r, Exception):
                logger.error(f"Generation exception: {r}")
                failed += 1
                recipient_results.append({
                    "recipient_id": recipient_id,
                    "status": "failed",
                    "reason": f"exception: {str(r)}",
                })
            elif r is None:
                if payloads.get(lead_id) is None:
                    skipped += 1
                    recipient_results.append({
                        "recipient_id": recipient_id,
                        "status": "skipped",
                        "reason": "missing_lead_context",
                    })
                else:
                    failed += 1
                    recipient_results.append({
                        "recipient_id": recipient_id,
                        "status": "failed",
                        "reason": "generation_returned_empty",
                    })
            else:
                r["recipient_id"] = recipient_id
                emails.append(r)
                recipient_results.append({
                    "recipient_id": recipient_id,
                    "status": "generated",
                    "email": r,
                })

        return {
            "emails": emails,
            "total": len(request.lead_ids),
            "generated": len(emails),
            "failed": failed,
            "skipped": skipped,
            "recipient_results": recipient_results,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in mass outreach generation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate emails: {str(e)}")


@router.post("/initial-outreach-mass/send")
async def send_initial_outreach_mass(
    request: InitialOutreachMassSendRequest,
    raw_request: Request,
    tenant: tuple = Depends(get_tenant_connection),
) -> Dict:
    """Send batch initial outreach emails + create campaign.

    1. Resolves each lead -> customer via HTTP
    2. Creates campaign record + campaign_emails rows (status='queued')
    3. Starts Temporal PersonalizedMassEmailWorkflow with campaign_id
    """
    try:
        conn, user = tenant
        user_email = user.get("email")
        user_name = user.get("name", "Customer Success Manager")

        emails = _validate_lead_email_payloads(request.emails, request.modified_emails)
        await check_daily_send_cap(conn, pending=len(emails))

        # Get employee info
        try:
            row = await conn.fetchrow(
                "SELECT employee_id, name FROM employee_info WHERE email = $1 LIMIT 1",
                user_email,
            )
            if row:
                user_name = row.get("name", user_name)
        except Exception:
            pass

        # 1. Batch resolve leads -> customers via leadgen's bulk-add-to-crm
        auth_header = raw_request.headers.get("authorization", "")
        resolved_emails = []

        lead_ids = [e.get("lead_id") for e in emails if e.get("lead_id")]
        # Build a lookup from lead_id -> email_data for merging results
        email_by_lead = {e.get("lead_id"): e for e in emails}

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{LEADGEN_SERVICE_URL}/api/leads/bulk-add-to-crm",
                    headers={"Authorization": auth_header},
                    json={"lead_ids": lead_ids},
                )
                if resp.status_code == 200:
                    batch_result = resp.json()
                    for item in batch_result.get("results", []):
                        customer_id = item.get("customer_id")
                        lead_id = item.get("lead_id")
                        if customer_id and lead_id in email_by_lead:
                            email_data = email_by_lead[lead_id]
                            resolved_emails.append({
                                "client_id": customer_id,
                                "to_email": email_data.get("to_email", ""),
                                "subject": email_data.get("subject", ""),
                                "body": email_data.get("body", ""),
                                "client_name": email_data.get("lead_company", ""),
                            })
                        elif not customer_id:
                            logger.warning(f"No customer_id for lead {lead_id}: {item.get('message')}")
                else:
                    logger.error(f"bulk-add-to-crm failed: {resp.status_code} - {resp.text}")
        except Exception as e:
            logger.error(f"Error in batch lead resolution: {e}")

        if not resolved_emails:
            raise HTTPException(status_code=500, detail="Failed to resolve any leads to CRM customers")

        # 2. Create campaign record + campaign_emails rows
        campaign_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        customer_ids = [e["client_id"] for e in resolved_emails]

        campaign_name = request.campaign_name or f"Initial Outreach {now.strftime('%Y-%m-%d %H:%M')}"

        # Build trade context from top-level request fields (mirrors email_mass_router).
        # Pool registers JSONB codec (service_core/pool.py) — pass raw dict, NOT json.dumps
        # (double-encodes into a JSON string inside JSONB).
        _trade_keys = ("products", "fob_price", "fob_price_old", "certifications", "moq", "lead_time", "sample_status", "effective_date")
        trade_fields = {k: getattr(request, k) for k in _trade_keys if getattr(request, k, None) is not None}
        trade_ctx = trade_fields if trade_fields else None

        await conn.execute(
            """
            INSERT INTO campaigns
                (id, name, email_type, recipient_count, status, created_at, trade_context)
            VALUES ($1, $2, 'initial_outreach', $3, 'sending', $4, $5)
            """,
            campaign_id,
            campaign_name,
            len(customer_ids),
            now,
            trade_ctx,
        )

        await conn.executemany(
            """
            INSERT INTO campaign_emails (campaign_id, customer_id, status)
            VALUES ($1, $2, 'queued')
            ON CONFLICT (campaign_id, customer_id) DO NOTHING
            """,
            [(campaign_id, cid) for cid in customer_ids],
        )

        # 3. Start Temporal workflow
        try:
            temporal_client = await get_temporal_client()
            workflow_input = PersonalizedMassEmailWorkflowInput(
                job_id=job_id,
                emails=resolved_emails,
                provider=request.provider,
                user_email=user_email,
                user_name=user_name,
                modified_emails=request.modified_emails or [],
                campaign_id=campaign_id,
            )

            await temporal_client.start_workflow(
                PersonalizedMassEmailWorkflow.run,
                workflow_input,
                id=f"{WORKFLOW_ID_PREFIX}-outreach-mass-send-{job_id}",
                task_queue=MASS_EMAIL_TASK_QUEUE,
                execution_timeout=timedelta(hours=2),
            )
            logger.info(f"Started Temporal workflow for mass outreach: job_id={job_id}, campaign_id={campaign_id}")
        except Exception as e:
            logger.error(f"Failed to start Temporal workflow: {e}")
            # Roll back BOTH the campaign and the child rows. Without the
            # campaign_emails update those rows would stay 'queued' forever
            # and admin queries would show queued emails on a failed campaign.
            await conn.execute(
                "UPDATE campaigns SET status = 'failed' WHERE id = $1",
                campaign_id,
            )
            await conn.execute(
                "UPDATE campaign_emails SET status = 'failed', "
                "error_message = COALESCE(error_message, 'Workflow start failed') "
                "WHERE campaign_id = $1 AND status = 'queued'",
                campaign_id,
            )
            raise HTTPException(status_code=500, detail=f"Failed to start send workflow: {str(e)}")

        return {
            "job_id": job_id,
            "campaign_id": campaign_id,
            "workflow_id": f"{WORKFLOW_ID_PREFIX}-outreach-mass-send-{job_id}",
            "total_recipients": len(resolved_emails),
            "resolved_from_leads": len(emails),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in mass outreach send: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to send emails: {str(e)}")

@router.post("/initial-outreach-mass/schedule")
async def schedule_initial_outreach_mass(
    request: InitialOutreachMassScheduleRequest,
    raw_request: Request,
    tenant: tuple = Depends(get_tenant_connection),
) -> Dict:
    """Schedule mass initial outreach emails for future delivery."""
    try:
        conn, user = tenant
        user_email = user.get("email")
        user_name = user.get("name", "Customer Success Manager")

        emails = _validate_lead_email_payloads(request.emails, request.modified_emails)
        await check_daily_send_cap(conn, pending=len(emails))

        scheduled_at_dt = datetime.fromisoformat(request.scheduled_at.replace("Z", "+00:00"))
        if scheduled_at_dt.tzinfo is None:
            scheduled_at_dt = scheduled_at_dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if scheduled_at_dt <= now + timedelta(seconds=30):
            raise HTTPException(status_code=400, detail="Scheduled time must be at least 1 minute in the future")

        delay = scheduled_at_dt - now
        job_id = str(uuid.uuid4())

        try:
            row = await conn.fetchrow(
                "SELECT name FROM employee_info WHERE email = $1 LIMIT 1", user_email
            )
            if row:
                user_name = row.get("name", user_name)
        except Exception:
            pass

        # Resolve leads -> customers
        auth_header = raw_request.headers.get("authorization", "")
        lead_ids = [e.get("lead_id") for e in emails if e.get("lead_id")]
        email_by_lead = {e.get("lead_id"): e for e in emails}
        resolved_emails = []

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{LEADGEN_SERVICE_URL}/api/leads/bulk-add-to-crm",
                headers={"Authorization": auth_header},
                json={"lead_ids": lead_ids},
            )
            if resp.status_code == 200:
                for item in resp.json().get("results", []):
                    customer_id = item.get("customer_id")
                    lead_id = item.get("lead_id")
                    if customer_id and lead_id in email_by_lead:
                        e = email_by_lead[lead_id]
                        resolved_emails.append({
                            "client_id": customer_id,
                            "to_email": e.get("to_email", ""),
                            "subject": e.get("subject", ""),
                            "body": e.get("body", ""),
                        })

        if not resolved_emails:
            raise HTTPException(status_code=500, detail="Failed to resolve any leads to CRM customers")

        # Create campaign
        campaign_name = request.campaign_name or f"Initial Outreach -- {scheduled_at_dt.strftime('%b %d')} (Scheduled)"
        campaign_row = await conn.fetchrow("""
            INSERT INTO campaigns (name, email_type, recipient_count, status, sent_at)
            VALUES ($1, 'initial_outreach', $2, 'scheduled', NULL)
            RETURNING id
        """, campaign_name, len(resolved_emails))
        campaign_id = str(campaign_row["id"])

        customer_ids = [e["client_id"] for e in resolved_emails]
        await conn.executemany(
            "INSERT INTO campaign_emails (campaign_id, customer_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            [(campaign_id, cid) for cid in customer_ids],
        )

        workflow_input = PersonalizedMassEmailWorkflowInput(
            job_id=job_id,
            emails=resolved_emails,
            provider=request.provider,
            user_email=user_email,
            user_name=user_name,
            modified_emails=request.modified_emails or [],
            campaign_id=campaign_id,
        )

        temporal_client = await get_temporal_client()
        await temporal_client.start_workflow(
            PersonalizedMassEmailWorkflow.run,
            workflow_input,
            id=f"{WORKFLOW_ID_PREFIX}-scheduled-outreach-mass-{job_id}",
            task_queue=MASS_EMAIL_TASK_QUEUE,
            start_delay=delay,
            execution_timeout=timedelta(hours=2),
        )

        logger.info(f"Scheduled mass outreach {job_id} ({len(resolved_emails)} recipients) at {scheduled_at_dt}")
        return {
            "success": True,
            "job_id": job_id,
            "campaign_id": campaign_id,
            "scheduled_at": scheduled_at_dt.isoformat(),
            "total_recipients": len(resolved_emails),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scheduling mass outreach: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to schedule emails: {str(e)}")
