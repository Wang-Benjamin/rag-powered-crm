"""
Outlook Sync Service - Loads and synchronizes emails from Microsoft Graph API.
Matches the architecture of GmailSyncService for consistency.

This service integrates with OAuthTokenManager for automatic token refresh.
"""

import os
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)


class OutlookSyncService:
    """Outlook API service for loading and syncing emails with automatic token refresh."""

    GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"

    def __init__(self, token_manager=None):
        """
        Initialize Outlook sync service.

        Args:
            token_manager: Optional OAuthTokenManager for automatic token refresh
        """
        self.token_manager = token_manager

    async def get_messages_list(
        self,
        user_email: str,
        query_params: Dict,
        max_results: int = 5000
    ) -> List[Dict]:
        """
        Get Outlook message list using Microsoft Graph API with automatic token refresh and pagination.

        Args:
            user_email: User's email address (for token lookup)
            query_params: Query parameters including $filter, $top, $select, $orderby, etc.
            max_results: Maximum number of results to return

        Returns:
            List of message objects
        """
        try:
            logger.info("🔧 [OutlookSyncService] get_messages_list() called")
            logger.info(f"   User: {user_email}")
            logger.info(f"   Max results: {max_results}")

            # Get fresh access token from token manager
            if not self.token_manager:
                logger.error("❌ [OutlookSyncService] Token manager not configured")
                raise ValueError("Token manager not configured")

            logger.info("🔑 [OutlookSyncService] Getting valid access token...")
            access_token = await self.token_manager.get_valid_access_token(user_email, 'microsoft')

            if not access_token:
                logger.error("❌ [OutlookSyncService] No valid Outlook token found for user")
                raise ValueError(
                    "Outlook authentication failed. Please reconnect your Microsoft account in Settings. "
                    "This may be due to an expired refresh token or network connectivity issues."
                )

            logger.info(f"✅ [OutlookSyncService] Access token obtained (length: {len(access_token)} chars)")

            messages = []
            url = f"{self.GRAPH_API_BASE}/me/messages"
            page_count = 0
            max_pages = 20  # Safety limit

            logger.info("🔄 [OutlookSyncService] Starting pagination loop...")

            async with httpx.AsyncClient(timeout=60.0) as client:
                while url:
                    page_count += 1
                    logger.info(f"📄 [OutlookSyncService] Fetching page {page_count}...")

                    response = await client.get(
                        url,
                        params=query_params if page_count == 1 else None,  # Only use params on first request
                        headers={'Authorization': f'Bearer {access_token}'}
                    )

                    if response.status_code != 200:
                        logger.error(f"❌ Microsoft Graph API error: {response.status_code} - {response.text}")
                        if response.status_code == 401:
                            raise ValueError("Outlook access token expired or invalid")
                        break

                    data = response.json()
                    batch_messages = data.get('value', [])
                    messages.extend(batch_messages)
                    logger.info(f"✅ [OutlookSyncService] Page {page_count}: Got {len(batch_messages)} messages (total: {len(messages)})")

                    url = data.get('@odata.nextLink')
                    if not url or len(messages) >= max_results:
                        logger.info(f"🏁 [OutlookSyncService] Pagination complete (next_link={bool(url)}, messages={len(messages)}/{max_results})")
                        break

                    if page_count >= max_pages:
                        logger.warning(f"⚠️ [OutlookSyncService] Reached max_pages limit ({max_pages})")
                        break

                    # Log progress for large syncs
                    if len(messages) % 500 == 0:
                        logger.info(f"📊 [OutlookSyncService] Fetched {len(messages)} messages so far...")

            logger.info(f"✅ [OutlookSyncService] get_messages_list completed: {len(messages)} total messages")
            return messages

        except Exception as e:
            logger.error(f"❌ [OutlookSyncService] Error in get_messages_list: {e}", exc_info=True)
            raise

    async def get_message_details(
        self,
        user_email: str,
        message_id: str,
        include_body: bool = False
    ) -> Optional[Dict]:
        """
        Get Outlook message details using Microsoft Graph API.

        Args:
            user_email: User's email address (for token lookup)
            message_id: Outlook message ID
            include_body: Whether to include full message body

        Returns:
            Message object or None if retrieval fails
        """
        try:
            # Get fresh access token from token manager
            if not self.token_manager:
                raise ValueError("Token manager not configured")

            access_token = await self.token_manager.get_valid_access_token(user_email, 'microsoft')

            if not access_token:
                logger.error("No valid Outlook token found for user")
                raise ValueError(
                    "Outlook authentication failed. Please reconnect your Microsoft account in Settings. "
                    "This may be due to an expired refresh token or network connectivity issues."
                )

            # Build select parameter - always include bodyPreview for notification snippets
            select_fields = 'id,subject,from,toRecipients,ccRecipients,receivedDateTime,bodyPreview'
            if include_body:
                select_fields += ',body'

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.GRAPH_API_BASE}/me/messages/{message_id}",
                    params={'$select': select_fields},
                    headers={'Authorization': f'Bearer {access_token}'}
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Error getting message {message_id}: {response.status_code} - {response.text}")
                    return None

        except Exception as e:
            logger.error(f"Error getting message {message_id}: {e}")
            return None

    def batch_get_messages(
        self,
        access_token: str,
        message_ids: List[str],
        include_body: bool = False
    ) -> List[Dict]:
        """
        Batch retrieve Outlook messages using Microsoft Graph API $batch endpoint.

        Args:
            access_token: Valid Microsoft Graph API access token
            message_ids: List of message IDs to retrieve
            include_body: Whether to include email body content

        Returns:
            List of Outlook message objects
        """
        if not message_ids:
            return []

        logger.info(f"📦 Fetching {len(message_ids)} emails using Microsoft Graph $batch API")

        all_messages = []
        batch_size = 20  # Microsoft Graph allows max 20 requests per batch

        # Build select parameter - always include bodyPreview for notification snippets
        select_fields = 'id,subject,from,toRecipients,ccRecipients,receivedDateTime,bodyPreview'
        if include_body:
            select_fields += ',body'

        # Process in batches of 20
        for i in range(0, len(message_ids), batch_size):
            batch_ids = message_ids[i:i + batch_size]

            if (i + batch_size) % 100 == 0 or i + batch_size >= len(message_ids):
                logger.info(f"📊 Progress: {min(i + batch_size, len(message_ids))}/{len(message_ids)} messages fetched")

            # Build batch request
            batch_requests = []
            for idx, msg_id in enumerate(batch_ids):
                batch_requests.append({
                    "id": str(idx + 1),
                    "method": "GET",
                    "url": f"/me/messages/{msg_id}?$select={select_fields}"
                })

            batch_payload = {"requests": batch_requests}

            try:
                import requests
                response = requests.post(
                    f"{self.GRAPH_API_BASE}/$batch",
                    headers={
                        'Authorization': f'Bearer {access_token}',
                        'Content-Type': 'application/json'
                    },
                    json=batch_payload,
                    timeout=30
                )

                if response.status_code == 200:
                    batch_response = response.json()
                    for resp in batch_response.get('responses', []):
                        if resp.get('status') == 200:
                            all_messages.append(resp['body'])
                        else:
                            logger.warning(f"⚠️ Failed to fetch message in batch: {resp.get('status')}")
                else:
                    logger.error(f"❌ Batch request failed: {response.status_code} - {response.text}")

            except Exception as e:
                logger.error(f"⚠️ Batch request error: {e}")
                continue

        logger.info(f"✅ Batch fetch complete: {len(all_messages)}/{len(message_ids)} messages retrieved")
        return all_messages

    def is_available(self) -> bool:
        """Check if Outlook service is available."""
        return True  # Service is always available if configured
