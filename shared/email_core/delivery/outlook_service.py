"""Outlook Email Provider — sends emails via Microsoft Graph API.

Extracted from prelude-leadgen's outlook_provider.py. More defensive error handling
than CRM version (_send_with_retry, structured 401/403/429 mapping).

Send-only + user profile. Mailbox operations (search, read, categories) stay in sync layer.
"""

import asyncio
import logging
from typing import Dict, Optional, Any
from datetime import datetime, timezone

import httpx

from email_core.config import settings
from email_core.models import EmailProvider, EmailSendResponse

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
SEND_MAIL_ENDPOINT = f"{GRAPH_API_BASE}/me/sendMail"
USER_PROFILE_ENDPOINT = f"{GRAPH_API_BASE}/me"


class OutlookEmailProvider:
    """Outlook email provider using Microsoft Graph API with automatic token refresh."""

    def __init__(self, token_manager=None):
        self.tenant_id = settings.microsoft_tenant_id
        self.client_id = settings.microsoft_client_id
        self.client_secret = settings.microsoft_client_secret
        self.redirect_uri = settings.microsoft_redirect_uri
        self.token_manager = token_manager

        self.token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        self.auth_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/authorize"

        self.scopes = [
            'openid', 'email', 'profile', 'offline_access',
            'Mail.Send', 'Mail.ReadWrite'
        ]

    def is_available(self) -> bool:
        available = bool(self.client_id and self.client_secret)
        if not available:
            logger.warning("Outlook provider not available - missing client_id or client_secret")
        return available

    async def refresh_access_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """Refresh the access token using a refresh token."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.token_url,
                    data={
                        'client_id': self.client_id,
                        'client_secret': self.client_secret,
                        'refresh_token': refresh_token,
                        'grant_type': 'refresh_token',
                        'scope': ' '.join(self.scopes)
                    },
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                )

                if response.status_code == 200:
                    token_data = response.json()
                    return {
                        'access_token': token_data.get('access_token'),
                        'refresh_token': token_data.get('refresh_token', refresh_token),
                        'expires_in': token_data.get('expires_in', 3600)
                    }
                else:
                    logger.error(f"Failed to refresh token: {response.status_code} - {response.text}")
                    return None

        except Exception as e:
            logger.error(f"Error refreshing Outlook access token: {e}")
            return None

    async def send_email(
        self,
        user_email: str,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: str,
        from_email: str,
        from_name: Optional[str] = None,
        reply_to_thread_id: Optional[str] = None,
        reply_to_rfc_message_id: Optional[str] = None
    ) -> EmailSendResponse:
        """Send email via Microsoft Graph API. Expects pre-formatted body_html."""
        try:
            if not self.token_manager:
                raise ValueError("Token manager not configured")

            access_token = await self.token_manager.get_valid_access_token(user_email, 'microsoft')

            if not access_token:
                return EmailSendResponse(
                    success=False, sent_to=to_email,
                    message="No valid Outlook token found. Please re-authenticate with Microsoft.",
                    provider=EmailProvider.OUTLOOK
                )

            message = {
                "message": {
                    "subject": subject,
                    "body": {"contentType": "HTML", "content": body_html},
                    "toRecipients": [{"emailAddress": {"address": to_email}}]
                },
                "saveToSentItems": "true"
            }

            if reply_to_rfc_message_id:
                message["message"]["internetMessageHeaders"] = [
                    {"name": "In-Reply-To", "value": reply_to_rfc_message_id},
                    {"name": "References", "value": reply_to_rfc_message_id}
                ]

            if from_name:
                message["message"]["from"] = {
                    "emailAddress": {"address": from_email, "name": from_name}
                }

            result = await self._send_with_retry(access_token, message, subject)

            if result['success']:
                return EmailSendResponse(
                    success=True, sent_to=to_email,
                    message='Email sent successfully via Outlook',
                    message_id=result.get('message_id'),
                    provider=EmailProvider.OUTLOOK,
                    sent_timestamp=result.get('sent_timestamp') or datetime.now(timezone.utc),
                    thread_id=result.get('thread_id'),
                    rfc_message_id=result.get('rfc_message_id')
                )
            else:
                return EmailSendResponse(
                    success=False, sent_to=to_email,
                    message=f"Failed to send email: {result.get('error')}",
                    provider=EmailProvider.OUTLOOK
                )

        except Exception as e:
            logger.error(f"Error sending email via Outlook: {e}")
            return EmailSendResponse(
                success=False, sent_to=to_email,
                message=f"Error sending email: {str(e)}",
                provider=EmailProvider.OUTLOOK
            )

    async def _send_with_retry(
        self, access_token: str, message: Dict[str, Any], subject: str = None
    ) -> Dict[str, Any]:
        """Send email via Microsoft Graph API with structured error handling."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    SEND_MAIL_ENDPOINT, json=message,
                    headers={
                        'Authorization': f'Bearer {access_token}',
                        'Content-Type': 'application/json'
                    }
                )

                if response.status_code in [200, 201, 202]:
                    message_id = thread_id = rfc_message_id = sent_timestamp = None

                    if subject:
                        try:
                            await asyncio.sleep(0.5)
                            escaped_subject = subject.replace("'", "''")
                            sent_response = await client.get(
                                f"{GRAPH_API_BASE}/me/mailFolders/SentItems/messages",
                                params={
                                    '$top': 1, '$orderby': 'sentDateTime desc',
                                    '$filter': f"subject eq '{escaped_subject}'",
                                    '$select': 'id,sentDateTime,conversationId,internetMessageId'
                                },
                                headers={'Authorization': f'Bearer {access_token}'}
                            )
                            if sent_response.status_code == 200:
                                msgs = sent_response.json().get('value', [])
                                if msgs:
                                    msg = msgs[0]
                                    message_id = msg.get('id')
                                    thread_id = msg.get('conversationId')
                                    rfc_message_id = msg.get('internetMessageId')
                                    sent_dt = msg.get('sentDateTime', '')
                                    if sent_dt:
                                        sent_timestamp = datetime.fromisoformat(
                                            sent_dt.replace('Z', '+00:00'))
                        except Exception as e:
                            logger.warning(f"Could not retrieve message details: {e}")

                    return {
                        'success': True,
                        'message_id': message_id or response.headers.get('request-id', 'unknown'),
                        'thread_id': thread_id,
                        'rfc_message_id': rfc_message_id,
                        'sent_timestamp': sent_timestamp
                    }

                elif response.status_code == 401:
                    return {'success': False, 'error': 'Access token expired. Please re-authenticate.'}
                elif response.status_code == 429:
                    retry_after = response.headers.get('Retry-After', '60')
                    return {'success': False, 'error': f'Rate limited. Retry after {retry_after} seconds'}
                elif response.status_code == 403:
                    return {'success': False, 'error': 'Insufficient permissions to send email'}
                else:
                    return {'success': False, 'error': f'API error {response.status_code}: {response.text[:100]}'}

        except httpx.TimeoutException:
            return {'success': False, 'error': 'Request timed out'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def get_user_profile(
        self, access_token: str, refresh_token: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get user profile from Microsoft Graph API."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    USER_PROFILE_ENDPOINT,
                    headers={'Authorization': f'Bearer {access_token}'}
                )
                if response.status_code == 200:
                    user_data = response.json()
                    return {
                        'email': user_data.get('mail') or user_data.get('userPrincipalName', ''),
                        'name': user_data.get('displayName', ''),
                        'id': user_data.get('id', '')
                    }
                elif response.status_code == 401 and refresh_token:
                    token_data = await self.refresh_access_token(refresh_token)
                    if token_data:
                        return await self.get_user_profile(token_data['access_token'])
                return None
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return None
