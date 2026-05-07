"""Shared provider selection for Gmail/Outlook/SMTP."""
import logging
from typing import Optional, Tuple, Any

logger = logging.getLogger(__name__)


async def select_provider(user_email: str, preferred: Optional[str] = None) -> Tuple[Any, Optional[str]]:
    """
    Select email provider (Gmail/Outlook/SMTP) based on user preference or email domain.

    Returns: (provider_instance, provider_hint)
    Raises: ValueError if no valid provider can be determined.
    """
    from email_core.delivery.gmail_service import GmailEmailProvider
    from email_core.delivery.outlook_service import OutlookEmailProvider
    from service_core.oauth import OAuthTokenManager
    import auth.providers

    provider = preferred
    if not provider and user_email:
        user_email_lower = user_email.lower()
        if any(domain in user_email_lower for domain in ['@outlook.com', '@hotmail.com', '@live.com']):
            provider = 'outlook'
        elif '@gmail.com' in user_email_lower:
            provider = 'gmail'

    # SMTP provider — used for QQ Mail, 163 Mail, corporate mail, etc.
    if provider == "smtp":
        smtp_provider = await _get_smtp_provider(user_email)
        if smtp_provider:
            return smtp_provider, None
        raise ValueError("No SMTP credentials configured. Go to Settings → Email to set up your mail server.")

    # SendGrid provider — for username/password and WeChat users
    if provider == "sendgrid":
        alias, display_name = await _get_sendgrid_alias(user_email)
        if not alias:
            raise ValueError("No outreach email alias found for this account. Please contact support.")
        from email_core.delivery.sendgrid_service import SendGridEmailProvider
        return SendGridEmailProvider(from_alias=alias, display_name=display_name), None

    current_auth_provider = auth.providers.auth_provider
    if not current_auth_provider:
        raise ValueError("Auth provider not initialized. Please reconnect your mailbox.")

    token_mgr = OAuthTokenManager(current_auth_provider)

    provider_hint = None
    if provider == "gmail":
        email_provider = GmailEmailProvider(token_manager=token_mgr)
    elif provider in ["outlook", "microsoft"]:
        email_provider = OutlookEmailProvider(token_manager=token_mgr)
        provider_hint = 'outlook'
    else:
        raise ValueError(f"Unsupported provider: {provider}. Please connect Gmail or Outlook, or configure SMTP in Settings.")

    return email_provider, provider_hint


async def _get_sendgrid_alias(user_email: str):
    """Load outreach alias from analytics DB. Returns (alias, display_name) or (None, None)."""
    try:
        from service_core.db import get_pool_manager
        pm = get_pool_manager()
        pool = await pm.get_analytics_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT outreach_alias, outreach_display_name FROM user_profiles WHERE email = $1",
                user_email
            )
        if row and row["outreach_alias"]:
            return row["outreach_alias"], row["outreach_display_name"] or user_email.split("@")[0]
        return None, None
    except Exception as e:
        logger.error(f"Failed to load outreach alias for {user_email}: {e}")
        return None, None


async def _get_smtp_provider(user_email: str):
    """Load SMTP credentials from DB and return a configured SMTPEmailProvider, or None."""
    try:
        from email_core.delivery.smtp import SMTPEmailProvider
        from service_core.db import get_pool_manager
        import base64
        import os
        from cryptography.fernet import Fernet

        pm = get_pool_manager()
        pool = await pm.get_analytics_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT smtp_host, smtp_port, smtp_user, smtp_password_encrypted, from_name
                   FROM smtp_credentials WHERE user_email = $1 AND verified = true""",
                user_email
            )

        if not row:
            return None

        # Decrypt password
        encryption_key = os.getenv("SMTP_ENCRYPTION_KEY", "")
        if not encryption_key:
            fallback = os.getenv("SESSIONS_DB_PASSWORD", "prelude-smtp-fallback-key-32b")
            encryption_key = base64.urlsafe_b64encode(fallback.ljust(32)[:32].encode()).decode()

        fernet = Fernet(encryption_key)
        password = fernet.decrypt(row['smtp_password_encrypted'].encode()).decode()

        # Create provider with per-user credentials
        provider = SMTPEmailProvider()
        provider.smtp_host = row['smtp_host']
        provider.smtp_port = row['smtp_port']
        provider.smtp_user = row['smtp_user']
        provider.smtp_password = password
        provider._from_name = row.get('from_name')
        return provider

    except Exception as e:
        logger.error(f"Failed to load SMTP credentials for {user_email}: {e}")
        return None
