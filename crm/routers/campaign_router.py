import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, List, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

from service_core.db import get_tenant_connection

router = APIRouter()


# ============================================================================
# REQUEST MODELS
# ============================================================================

class CreateCampaignRequest(BaseModel):
    name: str
    email_type: str
    offer: Optional[str] = None
    ask: Optional[str] = None
    detail: Optional[str] = None
    custom_prompt: Optional[str] = None
    trade_context: Optional[dict] = None
    customer_ids: List[int]


class UpdateCampaignRequest(BaseModel):
    status: Optional[str] = None


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("")
async def create_campaign(
    request: CreateCampaignRequest,
    tenant: tuple = Depends(get_tenant_connection)
) -> Dict:
    """Create a campaign record and queue campaign_emails for each recipient."""
    try:
        conn, user = tenant
        campaign_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        await conn.execute(
            """
            INSERT INTO campaigns
                (id, name, email_type, offer, ask, detail, custom_prompt, trade_context,
                 recipient_count, status, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'sending', $10)
            """,
            campaign_id,
            request.name,
            request.email_type,
            request.offer,
            request.ask,
            request.detail,
            request.custom_prompt,
            request.trade_context,
            len(request.customer_ids),
            now,
        )

        if request.customer_ids:
            await conn.executemany(
                """
                INSERT INTO campaign_emails (campaign_id, customer_id, status)
                VALUES ($1, $2, 'queued')
                ON CONFLICT (campaign_id, customer_id) DO NOTHING
                """,
                [(campaign_id, cid) for cid in request.customer_ids],
            )

        return {
            "campaignId": campaign_id,
            "createdAt": now.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating campaign: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create campaign: {str(e)}")


@router.get("")
async def list_campaigns(
    tenant: tuple = Depends(get_tenant_connection)
) -> Dict:
    """List all campaigns with aggregate metrics."""
    try:
        conn, user = tenant

        rows = await conn.fetch(
            """
            SELECT
                c.id,
                c.name,
                c.email_type,
                c.offer,
                c.ask,
                c.detail,
                c.custom_prompt,
                c.trade_context,
                c.status,
                c.created_at,
                c.sent_at,
                COUNT(DISTINCT ce.customer_id) AS recipient_count,
                COUNT(DISTINCT CASE WHEN ce.status = 'sent' THEN ce.customer_id END) AS sent,
                COUNT(DISTINCT CASE WHEN e.opened_at IS NOT NULL THEN ce.customer_id END) AS opened,
                COUNT(DISTINCT CASE WHEN EXISTS(
                    SELECT 1 FROM crm_emails r2
                    WHERE r2.customer_id = ce.customer_id
                      AND r2.direction = 'received'
                      AND r2.thread_id = e.thread_id
                      AND r2.created_at > e.created_at
                ) THEN ce.customer_id END) AS replied,
                COUNT(DISTINCT CASE WHEN ce.status = 'failed' THEN ce.customer_id END) AS failed
            FROM campaigns c
            LEFT JOIN campaign_emails ce ON ce.campaign_id = c.id
            LEFT JOIN crm_emails e ON e.email_id = ce.email_id
            GROUP BY c.id
            ORDER BY c.created_at DESC
            """
        )

        campaigns = []
        for row in rows:
            recipient_count = row["recipient_count"] or 0
            sent = row["sent"] or 0
            opened = row["opened"] or 0
            replied = row["replied"] or 0
            failed = row["failed"] or 0

            campaigns.append({
                "id": str(row["id"]),
                "name": row["name"],
                "emailType": row["email_type"],
                "offer": row["offer"],
                "ask": row["ask"],
                "detail": row["detail"],
                "customPrompt": row["custom_prompt"],
                "tradeContext": row["trade_context"],
                "status": row["status"],
                "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
                "sentAt": row["sent_at"].isoformat() if row["sent_at"] else None,
                "recipientCount": recipient_count,
                "sent": sent,
                "opened": opened,
                "replied": replied,
                "failed": failed,
                "openedPct": round(opened / sent * 100, 1) if sent > 0 else 0.0,
                "repliedPct": round(replied / sent * 100, 1) if sent > 0 else 0.0,
            })

        return {"campaigns": campaigns, "total": len(campaigns)}

    except Exception as e:
        logger.error(f"Error listing campaigns: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list campaigns: {str(e)}")


@router.get("/{campaign_id}")
async def get_campaign(
    campaign_id: str,
    status: Optional[str] = Query(None),
    tenant: tuple = Depends(get_tenant_connection)
) -> Dict:
    """
    Get campaign detail with per-recipient breakdown.

    Optional ?status= filter: not_opened, not_replied, failed, opened, replied
    """
    try:
        conn, user = tenant

        campaign_row = await conn.fetchrow(
            "SELECT * FROM campaigns WHERE id = $1",
            campaign_id,
        )
        if not campaign_row:
            raise HTTPException(status_code=404, detail="Campaign not found")

        # Aggregate metrics
        metrics_row = await conn.fetchrow(
            """
            SELECT
                COUNT(DISTINCT ce.customer_id) AS recipient_count,
                COUNT(DISTINCT CASE WHEN ce.status = 'sent' THEN ce.customer_id END) AS sent,
                COUNT(DISTINCT CASE WHEN e.opened_at IS NOT NULL THEN ce.customer_id END) AS opened,
                COUNT(DISTINCT CASE WHEN EXISTS(
                    SELECT 1 FROM crm_emails r2
                    WHERE r2.customer_id = ce.customer_id
                      AND r2.direction = 'received'
                      AND r2.thread_id = e.thread_id
                      AND r2.created_at > e.created_at
                ) THEN ce.customer_id END) AS replied,
                COUNT(DISTINCT CASE WHEN ce.status = 'failed' THEN ce.customer_id END) AS failed
            FROM campaign_emails ce
            LEFT JOIN crm_emails e ON e.email_id = ce.email_id
            WHERE ce.campaign_id = $1
            """,
            campaign_id,
        )

        m_sent = metrics_row["sent"] or 0
        m_opened = metrics_row["opened"] or 0
        m_replied = metrics_row["replied"] or 0
        m_failed = metrics_row["failed"] or 0

        metrics = {
            "recipientCount": metrics_row["recipient_count"] or 0,
            "sent": m_sent,
            "opened": m_opened,
            "replied": m_replied,
            "failed": m_failed,
            "openedPct": round(m_opened / m_sent * 100, 1) if m_sent > 0 else 0.0,
            "repliedPct": round(m_replied / m_sent * 100, 1) if m_sent > 0 else 0.0,
            "failedPct": round(m_failed / m_sent * 100, 1) if m_sent > 0 else 0.0,
        }

        # Per-recipient breakdown
        recipient_rows = await conn.fetch(
            """
            SELECT
                ce.customer_id,
                ce.email_id,
                ce.status,
                ce.sent_at,
                ce.error_message,
                e.opened_at,
                e.subject,
                e.thread_id,
                ci.name AS company,
                (SELECT p.email FROM personnel p WHERE p.client_id = ce.customer_id ORDER BY p.is_primary DESC NULLS LAST LIMIT 1) AS email,
                EXISTS(
                    SELECT 1 FROM crm_emails r2
                    WHERE r2.customer_id = ce.customer_id
                      AND r2.direction = 'received'
                      AND r2.thread_id = e.thread_id
                      AND r2.created_at > e.created_at
                ) AS has_reply,
                (
                    SELECT MIN(r2.created_at) FROM crm_emails r2
                    WHERE r2.customer_id = ce.customer_id
                      AND r2.direction = 'received'
                      AND r2.thread_id = e.thread_id
                      AND r2.created_at > e.created_at
                ) AS replied_at
            FROM campaign_emails ce
            LEFT JOIN crm_emails e ON e.email_id = ce.email_id
            LEFT JOIN clients ci ON ci.client_id = ce.customer_id
            WHERE ce.campaign_id = $1
            ORDER BY ce.customer_id
            """,
            campaign_id,
        )

        recipients = []
        for r in recipient_rows:
            opened_at = r["opened_at"]
            has_reply = r["has_reply"]
            replied_at = r["replied_at"]
            ce_status = r["status"]

            # Apply status filter
            if status:
                if status == "not_opened" and opened_at is not None:
                    continue
                elif status == "not_replied" and has_reply:
                    continue
                elif status == "failed" and ce_status != "failed":
                    continue
                elif status == "opened" and opened_at is None:
                    continue
                elif status == "replied" and not has_reply:
                    continue

            recipients.append({
                "customerId": r["customer_id"],
                "emailId": r["email_id"],
                "company": r["company"] or "",
                "email": r["email"] or "",
                "status": ce_status,
                "sentAt": r["sent_at"].isoformat() if r["sent_at"] else None,
                "openedAt": opened_at.isoformat() if opened_at else None,
                "hasReply": has_reply,
                "repliedAt": replied_at.isoformat() if replied_at else None,
                "errorMessage": r["error_message"],
                "subject": r["subject"],
            })

        return {
            "campaign": {
                "id": str(campaign_row["id"]),
                "name": campaign_row["name"],
                "emailType": campaign_row["email_type"],
                "offer": campaign_row["offer"],
                "ask": campaign_row["ask"],
                "detail": campaign_row["detail"],
                "recipientCount": metrics_row["recipient_count"] or 0,
                "status": campaign_row["status"],
                "createdAt": campaign_row["created_at"].isoformat() if campaign_row["created_at"] else None,
                "sentAt": campaign_row["sent_at"].isoformat() if campaign_row["sent_at"] else None,
                "customPrompt": campaign_row["custom_prompt"],
                "tradeContext": campaign_row["trade_context"],
            },
            "metrics": metrics,
            "recipients": recipients,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving campaign {campaign_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve campaign: {str(e)}")


@router.patch("/{campaign_id}")
async def update_campaign(
    campaign_id: str,
    request: UpdateCampaignRequest,
    tenant: tuple = Depends(get_tenant_connection)
) -> Dict:
    """
    Update campaign status. Used by Temporal workflow to finalize campaigns.

    If status not provided, calculates final status from campaign_emails:
    - All sent → 'sent'
    - All failed → 'failed'
    - Mix → 'partially_failed'
    """
    try:
        conn, user = tenant

        existing = await conn.fetchrow(
            "SELECT id FROM campaigns WHERE id = $1", campaign_id
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Campaign not found")

        if request.status:
            final_status = request.status
        else:
            counts = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(CASE WHEN status = 'sent' THEN 1 END) AS sent,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) AS failed
                FROM campaign_emails
                WHERE campaign_id = $1
                """,
                campaign_id,
            )
            total = counts["total"] or 0
            sent = counts["sent"] or 0
            failed = counts["failed"] or 0

            if total == 0 or sent == total:
                final_status = "sent"
            elif failed == total:
                final_status = "failed"
            else:
                final_status = "partially_failed"

        now = datetime.now(timezone.utc)
        await conn.execute(
            """
            UPDATE campaigns
            SET status = $1, sent_at = $2
            WHERE id = $3
            """,
            final_status,
            now,
            campaign_id,
        )

        return {
            "campaignId": campaign_id,
            "status": final_status,
            "sentAt": now.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating campaign {campaign_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update campaign: {str(e)}")
