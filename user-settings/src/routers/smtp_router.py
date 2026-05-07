"""
SMTP Email Configuration Router.

Allows users to save SMTP/IMAP credentials for email providers
like QQ Mail, 163 Mail, or corporate mail servers.
Passwords are encrypted at rest using Fernet symmetric encryption.
"""

import base64
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from cryptography.fernet import Fernet
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from service_core.auth import verify_auth_token
from service_core.db import get_pool_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/smtp", tags=["smtp"])

# Encryption key for SMTP passwords — generate with Fernet.generate_key()
# Falls back to a deterministic key derived from a secret if not set
_ENCRYPTION_KEY = os.getenv("SMTP_ENCRYPTION_KEY", "")
if not _ENCRYPTION_KEY:
    # Derive a key from the session DB password as fallback
    _fallback = os.getenv("SESSIONS_DB_PASSWORD", "prelude-smtp-fallback-key-32b")
    _ENCRYPTION_KEY = base64.urlsafe_b64encode(_fallback.ljust(32)[:32].encode()).decode()

_fernet = Fernet(_ENCRYPTION_KEY)


# Well-known SMTP/IMAP presets for Chinese email providers
PROVIDER_PRESETS = {
    "qq": {
        "name": "QQ Mail",
        "smtp_host": "smtp.qq.com",
        "smtp_port": 587,
        "imap_host": "imap.qq.com",
        "imap_port": 993,
    },
    "163": {
        "name": "163 Mail",
        "smtp_host": "smtp.163.com",
        "smtp_port": 465,
        "imap_host": "imap.163.com",
        "imap_port": 993,
    },
    "outlook": {
        "name": "Outlook (SMTP)",
        "smtp_host": "smtp-mail.outlook.com",
        "smtp_port": 587,
        "imap_host": "outlook.office365.com",
        "imap_port": 993,
    },
    "gmail": {
        "name": "Gmail (SMTP)",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
    },
}


# ── Models ──

class SmtpConfigRequest(BaseModel):
    provider_name: str = "custom"  # "qq", "163", "custom", etc.
    smtp_host: str
    smtp_port: int = 587
    smtp_user: str
    smtp_password: str
    imap_host: Optional[str] = None
    imap_port: int = 993
    from_name: Optional[str] = None


class SmtpConfigResponse(BaseModel):
    provider_name: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    imap_host: Optional[str]
    imap_port: int
    from_name: Optional[str]
    verified: bool


class SmtpTestResult(BaseModel):
    smtp_ok: bool
    smtp_error: Optional[str] = None
    imap_ok: bool
    imap_error: Optional[str] = None


# ── Helpers ──

def _encrypt_password(password: str) -> str:
    return _fernet.encrypt(password.encode()).decode()


def _decrypt_password(encrypted: str) -> str:
    return _fernet.decrypt(encrypted.encode()).decode()


# ── Routes ──

@router.get("/presets")
async def get_presets():
    """Return well-known SMTP/IMAP presets for common providers."""
    return PROVIDER_PRESETS


@router.get("/config", response_model=Optional[SmtpConfigResponse])
async def get_smtp_config(authenticated_user: dict = Depends(verify_auth_token)):
    """Get the user's saved SMTP configuration (password excluded)."""
    user_email = authenticated_user.get("email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Invalid token")

    pm = get_pool_manager()
    pool = await pm.get_analytics_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT provider_name, smtp_host, smtp_port, smtp_user,
                      imap_host, imap_port, from_name, verified
               FROM smtp_credentials WHERE user_email = $1""",
            user_email
        )

    if not row:
        return None

    return SmtpConfigResponse(
        provider_name=row['provider_name'],
        smtp_host=row['smtp_host'],
        smtp_port=row['smtp_port'],
        smtp_user=row['smtp_user'],
        imap_host=row['imap_host'],
        imap_port=row['imap_port'],
        from_name=row['from_name'],
        verified=row['verified'],
    )


@router.post("/config", response_model=SmtpConfigResponse)
async def save_smtp_config(request: SmtpConfigRequest, authenticated_user: dict = Depends(verify_auth_token)):
    """Save or update SMTP configuration for the authenticated user."""
    user_email = authenticated_user.get("email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Invalid token")

    encrypted_pw = _encrypt_password(request.smtp_password)
    now = datetime.now(timezone.utc)

    pm = get_pool_manager()
    pool = await pm.get_analytics_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO smtp_credentials
               (user_email, provider_name, smtp_host, smtp_port, smtp_user,
                smtp_password_encrypted, imap_host, imap_port, from_name, verified, created_at, updated_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, false, $10, $10)
               ON CONFLICT (user_email) DO UPDATE SET
                 provider_name = EXCLUDED.provider_name,
                 smtp_host = EXCLUDED.smtp_host,
                 smtp_port = EXCLUDED.smtp_port,
                 smtp_user = EXCLUDED.smtp_user,
                 smtp_password_encrypted = EXCLUDED.smtp_password_encrypted,
                 imap_host = EXCLUDED.imap_host,
                 imap_port = EXCLUDED.imap_port,
                 from_name = EXCLUDED.from_name,
                 verified = false,
                 updated_at = EXCLUDED.updated_at""",
            user_email, request.provider_name, request.smtp_host, request.smtp_port,
            request.smtp_user, encrypted_pw, request.imap_host, request.imap_port,
            request.from_name, now
        )

    logger.info(f"SMTP config saved for {user_email} (provider={request.provider_name})")
    return SmtpConfigResponse(
        provider_name=request.provider_name,
        smtp_host=request.smtp_host,
        smtp_port=request.smtp_port,
        smtp_user=request.smtp_user,
        imap_host=request.imap_host,
        imap_port=request.imap_port,
        from_name=request.from_name,
        verified=False,
    )


@router.post("/test", response_model=SmtpTestResult)
async def test_smtp_config(authenticated_user: dict = Depends(verify_auth_token)):
    """Test the saved SMTP/IMAP connection. Updates verified status on success."""
    user_email = authenticated_user.get("email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Invalid token")

    pm = get_pool_manager()
    pool = await pm.get_analytics_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT smtp_host, smtp_port, smtp_user, smtp_password_encrypted, imap_host, imap_port FROM smtp_credentials WHERE user_email = $1",
            user_email
        )

    if not row:
        raise HTTPException(status_code=404, detail="No SMTP configuration found. Save config first.")

    password = _decrypt_password(row['smtp_password_encrypted'])
    smtp_ok, smtp_error = False, None
    imap_ok, imap_error = False, None

    # Test SMTP — port 465 uses SSL, port 587 uses STARTTLS
    try:
        import smtplib
        if row['smtp_port'] == 465:
            with smtplib.SMTP_SSL(row['smtp_host'], row['smtp_port'], timeout=10) as server:
                server.login(row['smtp_user'], password)
        else:
            with smtplib.SMTP(row['smtp_host'], row['smtp_port'], timeout=10) as server:
                server.starttls()
                server.login(row['smtp_user'], password)
        smtp_ok = True
    except Exception as e:
        smtp_error = str(e)

    # Test IMAP (if configured)
    if row['imap_host']:
        try:
            import imaplib
            with imaplib.IMAP4_SSL(row['imap_host'], row['imap_port']) as imap:
                imap.login(row['smtp_user'], password)
            imap_ok = True
        except Exception as e:
            imap_error = str(e)
    else:
        imap_ok = True  # No IMAP configured, skip

    # Update verified status
    verified = smtp_ok and imap_ok
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE smtp_credentials SET verified = $1, updated_at = $2 WHERE user_email = $3",
            verified, datetime.now(timezone.utc), user_email
        )

    return SmtpTestResult(smtp_ok=smtp_ok, smtp_error=smtp_error, imap_ok=imap_ok, imap_error=imap_error)


@router.delete("/config")
async def delete_smtp_config(authenticated_user: dict = Depends(verify_auth_token)):
    """Delete the user's SMTP configuration."""
    user_email = authenticated_user.get("email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Invalid token")

    pm = get_pool_manager()
    pool = await pm.get_analytics_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM smtp_credentials WHERE user_email = $1", user_email)

    return {"status": "deleted"}
