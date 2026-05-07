"""
Email Activities for Mass Email Workflows - CRM Service (asyncpg)
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List
from temporalio import activity

from service_core.pool import TenantPoolManager

logger = logging.getLogger("mass_email")

# Temporal activities run in a separate process/event loop.
# They need their own pool manager instance.
_pool_manager = None


async def _get_pool_manager() -> TenantPoolManager:
    global _pool_manager
    if _pool_manager is None:
        _pool_manager = TenantPoolManager()
    return _pool_manager


@activity.defn(name="send_single_email_activity")
async def send_single_email_activity(email_params: Dict[str, Any]) -> Dict[str, Any]:
    """Send a single email via Gmail/Outlook/SMTP."""
    to_email = email_params.get('to_email')
    subject = email_params.get('subject')
    body = email_params.get('body')
    customer_id = email_params.get('customer_id')
    deal_id = email_params.get('deal_id')
    provider = email_params.get('provider')
    user_email = email_params.get('user_email')
    user_name = email_params.get('user_name')
    tenant_db = email_params.get('tenant_db')

    try:
        from email_core.delivery.send import send_email as send_email_via_provider
        from email_service.delivery.provider_selector import select_provider

        try:
            email_provider, provider_hint = await select_provider(user_email, provider)
        except ValueError as e:
            return {"success": False, "error": str(e)}

        pm = await _get_pool_manager()

        # Resolve tenant database name
        db_name = tenant_db
        if not db_name and user_email:
            db_name = await pm.lookup_db_name(user_email)

        # Send within a connection context so OAuthTokenManager can access DB
        # (Temporal activities don't have request-scoped connections)
        from service_core.db import _current_conn
        async with pm.acquire(db_name) as conn:
            conn_token = _current_conn.set(conn)
            try:
                result = await send_email_via_provider(
                    provider=email_provider,
                    user_email=user_email,
                    to_email=to_email,
                    subject=subject,
                    body=body,
                    from_email=user_email,
                    from_name=user_name,
                    provider_hint=provider_hint,
                )
            finally:
                _current_conn.reset(conn_token)

        # Log sent email to database
        email_id = None
        if result and result.success and customer_id and db_name:
            try:
                from data.repositories.email_repository import EmailRepository

                async with pm.acquire(db_name) as conn:
                    employee_id = None
                    try:
                        row = await conn.fetchrow(
                            "SELECT employee_id FROM employee_info WHERE email = $1",
                            user_email,
                        )
                        if row:
                            employee_id = row['employee_id']
                    except Exception as e:
                        logger.warning(f"Could not look up employee_id for {user_email}: {e}")

                    email_repo = EmailRepository()
                    email_id = await email_repo.insert_email(
                        conn=conn,
                        from_email=user_email,
                        to_email=to_email,
                        subject=subject,
                        body=body,
                        direction='sent',
                        customer_id=customer_id,
                        deal_id=deal_id,
                        employee_id=employee_id,
                        message_id=getattr(result, 'message_id', None),
                        thread_id=getattr(result, 'thread_id', None),
                        rfc_message_id=getattr(result, 'rfc_message_id', None),
                        created_at=getattr(result, 'sent_timestamp', None) or datetime.now(timezone.utc),
                        tracking_token=getattr(result, 'tracking_token', None),
                        tracking_token_expires_at=getattr(result, 'tracking_expires_at', None),
                    )

                    # Fire-and-forget: generate embedding for RAG search
                    if email_id:
                        try:
                            import asyncio
                            from services.rag.embedding_sync_service import embed_single_email
                            asyncio.ensure_future(embed_single_email(user_email, email_id, subject, body))
                        except Exception as embed_err:
                            logger.debug(f"Email embedding skipped: {embed_err}")
            except Exception as e:
                logger.error(f"DB logging error: {e}")

        if result and result.success:
            return {
                "success": True,
                "message": "Email sent successfully",
                "email_id": email_id if email_id else None,
                "db_logged": email_id is not None,
            }
        else:
            return {"success": False, "error": result.message if result else "Unknown error"}

    except Exception as e:
        logger.error(f"Send failed to {to_email}: {e}")
        return {"success": False, "error": str(e)}


@activity.defn(name="update_campaign_email_status_activity")
async def update_campaign_email_status_activity(params: Dict[str, Any]) -> Dict[str, Any]:
    """Update a single campaign_email row status after send attempt."""
    campaign_id = params['campaign_id']
    customer_id = params['customer_id']
    status = params['status']  # 'sent' or 'failed'
    email_id = params.get('email_id')
    error_message = params.get('error_message')
    user_email = params['user_email']

    pm = await _get_pool_manager()
    db_name = await pm.lookup_db_name(user_email)
    async with pm.acquire(db_name) as conn:
        if status == 'sent':
            await conn.execute("""
                UPDATE campaign_emails
                SET email_id = $1, status = 'sent', sent_at = NOW()
                WHERE campaign_id = $2 AND customer_id = $3
            """, email_id, campaign_id, customer_id)
        else:
            await conn.execute("""
                UPDATE campaign_emails
                SET status = 'failed', error_message = $1
                WHERE campaign_id = $2 AND customer_id = $3
            """, error_message, campaign_id, customer_id)

    return {"success": True}


@activity.defn(name="finalize_campaign_status_activity")
async def finalize_campaign_status_activity(params: Dict[str, Any]) -> Dict[str, Any]:
    """Finalize campaign status based on campaign_emails results."""
    campaign_id = params['campaign_id']
    user_email = params['user_email']

    pm = await _get_pool_manager()
    db_name = await pm.lookup_db_name(user_email)
    async with pm.acquire(db_name) as conn:
        row = await conn.fetchrow("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE status = 'sent') AS sent,
                COUNT(*) FILTER (WHERE status = 'failed') AS failed
            FROM campaign_emails WHERE campaign_id = $1
        """, campaign_id)

        total = row['total']
        sent = row['sent']
        failed = row['failed']

        if failed == 0:
            final_status = 'sent'
        elif sent == 0:
            final_status = 'failed'
        else:
            final_status = 'partially_failed'

        await conn.execute("""
            UPDATE campaigns SET status = $1, sent_at = NOW() WHERE id = $2
        """, final_status, campaign_id)

    return {"success": True, "status": final_status}


@activity.defn(name="update_writing_style_activity")
async def update_writing_style_activity(
    user_email: str,
    email_samples: List[Dict[str, str]],
    tenant_db: str = None,
) -> bool:
    """Update employee writing style based on sent emails."""
    try:
        from email_service.data.fetchers import update_employee_writing_style_after_send

        pm = await _get_pool_manager()
        db_name = tenant_db
        if not db_name:
            db_name = await pm.lookup_db_name(user_email)

        async with pm.acquire(db_name) as conn:
            await update_employee_writing_style_after_send(conn, user_email, email_samples)
        return True

    except Exception as e:
        logger.error(f"Writing style update failed: {e}")
        return False
