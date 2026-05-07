"""
Outreach Email Router — Prelude-managed email aliases for manufacturers.

Users get a unique alias at signup (e.g. wanglei@outreach.prelude.app).
Emails sent via SendGrid. Replies caught via Inbound Parse webhook.
"""

import os
import re
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel

from service_core.auth import verify_auth_token
from service_core.db import get_pool_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/outreach", tags=["outreach"])

OUTREACH_DOMAIN = os.getenv("OUTREACH_DOMAIN", "outreach.preludeos.com")
SENDING_DOMAIN = os.getenv("SENDING_DOMAIN", "preludeos.com")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
DAILY_SEND_LIMIT = 50
HOURLY_SEND_LIMIT = 5


# ── Models ──

class CreateAliasRequest(BaseModel):
    username: str
    display_name: Optional[str] = None


class CreateAliasResponse(BaseModel):
    alias: str
    display_name: str


class SendEmailRequest(BaseModel):
    to_email: str
    subject: str
    body_zh: str
    body_en: Optional[str] = None
    in_reply_to: Optional[str] = None


class SendEmailResponse(BaseModel):
    success: bool
    message_id: Optional[str] = None
    alias: str


# ── Helpers ──

def generate_alias(username: str) -> str:
    """Generate a unique outreach alias."""
    clean = re.sub(r'[^a-z0-9._-]', '', username.lower().strip())
    if not clean:
        clean = 'user'
    return f"{clean}@{OUTREACH_DOMAIN}"


def html_to_plain(html: str) -> str:
    """Strip HTML tags to produce a plain-text alternative."""
    text = re.sub(r'<br\s*/?>', '\n', html)
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()


async def send_via_sendgrid(from_alias: str, display_name: str, to_email: str,
                             subject: str, body_html: str, in_reply_to: str = None) -> Optional[str]:
    """Send email via SendGrid API. Returns message_id or None on failure.

    from_alias is the user's outreach alias (e.g. wanglei@outreach.preludeos.com).
    We send FROM username@preludeos.com (authenticated domain with reputation)
    and set Reply-To to the outreach alias (for inbound parse routing).
    """
    if not SENDGRID_API_KEY:
        logger.warning("SENDGRID_API_KEY not set — email not sent")
        return None

    try:
        import httpx

        # Derive sending address: wanglei@outreach.preludeos.com → wanglei@preludeos.com
        username_part = from_alias.split('@')[0]
        sending_email = f"{username_part}@{SENDING_DOMAIN}"

        headers = {
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json",
        }
        body_plain = html_to_plain(body_html)
        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": sending_email, "name": display_name},
            "reply_to": {"email": from_alias, "name": display_name},
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": body_plain},
                {"type": "text/html", "value": body_html},
            ],
            "headers": {
                "List-Unsubscribe": f"<mailto:{from_alias}?subject=unsubscribe>",
            },
        }
        if in_reply_to:
            payload["headers"]["In-Reply-To"] = in_reply_to
            payload["headers"]["References"] = in_reply_to

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                json=payload,
                headers=headers,
                timeout=30,
            )
            if resp.status_code in (200, 201, 202):
                msg_id = resp.headers.get("X-Message-Id", "")
                logger.info(f"Email sent: {from_alias} → {to_email} (msg_id={msg_id})")
                return msg_id
            else:
                logger.error(f"SendGrid error {resp.status_code}: {resp.text}")
                return None
    except Exception as e:
        logger.error(f"SendGrid send failed: {e}")
        return None


# ── Routes ──

@router.post("/create-alias", response_model=CreateAliasResponse)
async def create_alias(request: CreateAliasRequest, authenticated_user: dict = Depends(verify_auth_token)):
    """Create an outreach email alias for the authenticated user."""
    user_email = authenticated_user.get("email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Invalid token")
    pm = get_pool_manager()

    alias = generate_alias(request.username)
    display_name = request.display_name or request.username

    pool = await pm.get_analytics_pool()
    async with pool.acquire() as conn:
        # Check if alias already taken
        existing = await conn.fetchval(
            "SELECT email FROM user_profiles WHERE outreach_alias = $1 AND email != $2",
            alias, user_email
        )
        if existing:
            # Append random suffix
            import secrets
            alias = f"{request.username}.{secrets.token_hex(2)}@{OUTREACH_DOMAIN}"

        await conn.execute(
            "UPDATE user_profiles SET outreach_alias = $1, outreach_display_name = $2 WHERE email = $3",
            alias, display_name, user_email
        )

    logger.info(f"Created outreach alias: {alias} for {user_email}")
    return CreateAliasResponse(alias=alias, display_name=display_name)


@router.get("/alias")
async def get_alias(authenticated_user: dict = Depends(verify_auth_token)):
    """Get the authenticated user's outreach alias."""
    user_email = authenticated_user.get("email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Invalid token")
    pm = get_pool_manager()

    pool = await pm.get_analytics_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT outreach_alias, outreach_display_name FROM user_profiles WHERE email = $1",
            user_email
        )

    if not row or not row['outreach_alias']:
        return {"alias": None, "display_name": None}

    return {"alias": row['outreach_alias'], "display_name": row['outreach_display_name']}


@router.post("/send", response_model=SendEmailResponse)
async def send_outreach_email(request: SendEmailRequest, authenticated_user: dict = Depends(verify_auth_token)):
    """Send an email from the user's outreach alias."""
    user_email = authenticated_user.get("email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Invalid token")
    pm = get_pool_manager()

    pool = await pm.get_analytics_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT outreach_alias, outreach_display_name FROM user_profiles WHERE email = $1",
            user_email
        )
        if not row or not row['outreach_alias']:
            raise HTTPException(status_code=400, detail="No outreach alias configured. Complete onboarding first.")

        alias = row['outreach_alias']
        display_name = row['outreach_display_name'] or alias.split('@')[0]

        # Rate limiting check
        today_count = await conn.fetchval(
            """SELECT COUNT(*) FROM outreach_messages
               WHERE from_email = $1 AND direction = 'outbound'
               AND created_at > NOW() - INTERVAL '24 hours'""",
            alias
        ) or 0

        if today_count >= DAILY_SEND_LIMIT:
            raise HTTPException(status_code=429, detail=f"Daily send limit reached ({DAILY_SEND_LIMIT}/day)")

    # Translate if only Chinese body provided
    body_en = request.body_en
    if not body_en:
        try:
            from email_core.translation import translate_to_english
            body_en = await translate_to_english(request.body_zh)
        except Exception:
            pass
        # Fallback: use Chinese body if translation failed or returned None
        if not body_en:
            body_en = request.body_zh

    # Convert to HTML
    body_html = body_en.replace('\n', '<br>')

    # Send via SendGrid
    msg_id = await send_via_sendgrid(
        from_alias=alias,
        display_name=display_name,
        to_email=request.to_email,
        subject=request.subject,
        body_html=body_html,
        in_reply_to=request.in_reply_to,
    )

    if not msg_id:
        raise HTTPException(status_code=502, detail="Failed to send email")

    # Store in database
    async with pool.acquire() as conn:
        # Find or create conversation
        conv = await conn.fetchrow(
            """SELECT id FROM outreach_conversations
               WHERE user_email = $1 AND buyer_email = $2 AND subject = $3""",
            user_email, request.to_email, request.subject
        )
        if conv:
            conv_id = conv['id']
        else:
            conv_id = await conn.fetchval(
                """INSERT INTO outreach_conversations (user_email, alias, buyer_email, subject, created_at)
                   VALUES ($1, $2, $3, $4, $5) RETURNING id""",
                user_email, alias, request.to_email, request.subject, datetime.now(timezone.utc)
            )

        await conn.execute(
            """INSERT INTO outreach_messages
               (conversation_id, direction, from_email, to_email, subject, body_en, body_zh,
                message_id, in_reply_to, sendgrid_message_id, status, created_at)
               VALUES ($1, 'outbound', $2, $3, $4, $5, $6, $7, $8, $9, 'sent', $10)""",
            conv_id, alias, request.to_email, request.subject,
            body_en, request.body_zh, msg_id, request.in_reply_to,
            msg_id, datetime.now(timezone.utc)
        )

    return SendEmailResponse(success=True, message_id=msg_id, alias=alias)


@router.post("/inbound")
async def handle_inbound_email(req: Request):
    """
    SendGrid Inbound Parse webhook.
    Receives replies to outreach aliases and stores them.
    """
    form = await req.form()
    to_email = form.get("to", "")
    from_email = form.get("from", "")
    subject = form.get("subject", "")
    body_text = form.get("text", "")
    body_html = form.get("html", "")
    in_reply_to = form.get("In-Reply-To", "") or form.get("in-reply-to", "")

    # Extract alias from To field
    alias_match = re.search(r'[\w.-]+@' + re.escape(OUTREACH_DOMAIN), to_email)
    if not alias_match:
        logger.warning(f"Inbound email to unknown address: {to_email}")
        return {"status": "ignored"}

    alias = alias_match.group(0)

    pm = get_pool_manager()
    pool = await pm.get_analytics_pool()
    async with pool.acquire() as conn:
        # Find user by alias
        user = await conn.fetchrow(
            "SELECT email FROM user_profiles WHERE outreach_alias = $1", alias
        )
        if not user:
            logger.warning(f"No user found for alias: {alias}")
            return {"status": "no_user"}

        user_email = user['email']
        body_content = body_text or body_html or ""

        # Extract sender email
        sender_match = re.search(r'[\w.-]+@[\w.-]+', from_email)
        sender = sender_match.group(0) if sender_match else from_email

        # Find or create conversation
        conv = await conn.fetchrow(
            """SELECT id FROM outreach_conversations
               WHERE user_email = $1 AND buyer_email = $2
               ORDER BY created_at DESC LIMIT 1""",
            user_email, sender
        )
        if conv:
            conv_id = conv['id']
        else:
            conv_id = await conn.fetchval(
                """INSERT INTO outreach_conversations (user_email, alias, buyer_email, subject, created_at)
                   VALUES ($1, $2, $3, $4, $5) RETURNING id""",
                user_email, alias, sender, subject, datetime.now(timezone.utc)
            )

        # Translate reply to Chinese
        body_zh = None
        try:
            from email_core.translation import translate_to_chinese
            body_zh = await translate_to_chinese(body_content)
        except Exception:
            pass

        # Generate a stable message_id from inbound parse data
        import hashlib
        raw_id = f"{sender}:{alias}:{subject}:{in_reply_to or body_content[:50]}"
        message_id = hashlib.sha1(raw_id.encode()).hexdigest()

        await conn.execute(
            """INSERT INTO outreach_messages
               (conversation_id, direction, from_email, to_email, subject, body_en, body_zh,
                message_id, in_reply_to, status, created_at)
               VALUES ($1, 'inbound', $2, $3, $4, $5, $6, $7, $8, 'received', $9)
               ON CONFLICT DO NOTHING""",
            conv_id, sender, alias, subject,
            body_content, body_zh, message_id, in_reply_to,
            datetime.now(timezone.utc)
        )

        # Also write to tenant crm_emails so replies show up in CRM thread view
        user_full = await conn.fetchrow(
            "SELECT db_name FROM user_profiles WHERE email = $1", user_email
        )

    if user_full and user_full["db_name"]:
        try:
            tenant_pool = await pm.get_tenant_pool(user_full["db_name"])
            async with tenant_pool.acquire() as tc:
                emp = await tc.fetchrow(
                    "SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1", user_email
                )
                employee_id = emp["employee_id"] if emp else None

                customer = await tc.fetchrow(
                    "SELECT customer_id FROM personnel WHERE email = $1 LIMIT 1", sender
                )
                customer_id = customer["customer_id"] if customer else None

                if customer_id:
                    await tc.execute(
                        """INSERT INTO crm_emails
                           (customer_id, employee_id, from_email, to_email, subject, body,
                            direction, message_id, in_reply_to, created_at)
                           VALUES ($1,$2,$3,$4,$5,$6,'received',$7,$8,NOW())
                           ON CONFLICT (message_id) DO NOTHING""",
                        customer_id, employee_id, sender, user_email,
                        subject, body_content, message_id, in_reply_to or None,
                    )
                    logger.info(f"Inbound synced to crm_emails: customer_id={customer_id}")
        except Exception as e:
            logger.warning(f"Failed to sync inbound to crm_emails: {e}")

    logger.info(f"Inbound email: {sender} → {alias} (user: {user_email})")

    # TODO: Send WeChat notification to manufacturer

    return {"status": "processed"}


@router.get("/conversations")
async def list_conversations(authenticated_user: dict = Depends(verify_auth_token)):
    """List all conversations for the authenticated user."""
    user_email = authenticated_user.get("email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Invalid token")
    pm = get_pool_manager()

    pool = await pm.get_analytics_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT c.id, c.buyer_email, c.subject, c.created_at,
                      (SELECT COUNT(*) FROM outreach_messages WHERE conversation_id = c.id) as message_count,
                      (SELECT MAX(created_at) FROM outreach_messages WHERE conversation_id = c.id) as last_message_at
               FROM outreach_conversations c
               WHERE c.user_email = $1
               ORDER BY last_message_at DESC NULLS LAST
               LIMIT 50""",
            user_email
        )

    return [
        {
            "id": r['id'],
            "buyer_email": r['buyer_email'],
            "subject": r['subject'],
            "message_count": r['message_count'],
            "last_message_at": str(r['last_message_at'] or r['created_at']),
        }
        for r in rows
    ]


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: int, authenticated_user: dict = Depends(verify_auth_token)):
    """Get all messages in a conversation."""
    user_email = authenticated_user.get("email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Invalid token")
    pm = get_pool_manager()

    pool = await pm.get_analytics_pool()
    async with pool.acquire() as conn:
        # Verify ownership
        conv = await conn.fetchrow(
            "SELECT id FROM outreach_conversations WHERE id = $1 AND user_email = $2",
            conversation_id, user_email
        )
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        messages = await conn.fetch(
            """SELECT id, direction, from_email, to_email, subject, body_en, body_zh,
                      status, created_at
               FROM outreach_messages
               WHERE conversation_id = $1
               ORDER BY created_at ASC""",
            conversation_id
        )

    return [
        {
            "id": m['id'],
            "direction": m['direction'],
            "from_email": m['from_email'],
            "to_email": m['to_email'],
            "subject": m['subject'],
            "body_en": m['body_en'],
            "body_zh": m['body_zh'],
            "status": m['status'],
            "created_at": str(m['created_at']),
        }
        for m in messages
    ]
