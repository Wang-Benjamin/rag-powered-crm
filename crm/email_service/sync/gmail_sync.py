"""
Gmail Sync Service - Loads and synchronizes emails from Gmail API.
Refactored to use Google API client library instead of raw HTTP requests.

This service integrates with OAuthTokenManager for automatic token refresh.
"""

import os
import base64
import logging
import time
import random
from typing import Dict, List, Optional
from datetime import datetime, timedelta

# Google API imports
try:
    from googleapiclient.discovery import build
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    logging.warning("Google API client not available. Gmail features will be disabled.")

logger = logging.getLogger(__name__)


class GmailSyncService:
    """Gmail API service for loading and syncing emails with automatic token refresh."""

    def __init__(self, token_manager=None):
        """
        Initialize Gmail sync service.

        Args:
            token_manager: Optional OAuthTokenManager for automatic token refresh
        """
        self.client_id = os.getenv('GOOGLE_CLIENT_ID')
        self.client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        self.token_manager = token_manager
        self.scopes = [
            'https://www.googleapis.com/auth/gmail.send',
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.modify'
        ]

    def _build_service(self, access_token: str):
        """Build Gmail service with access token."""
        if not GOOGLE_API_AVAILABLE:
            raise ValueError("Google API client not available")

        credentials = Credentials(
            token=access_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=self.scopes
        )

        return build('gmail', 'v1', credentials=credentials)

    async def get_messages_list(
        self,
        user_email: str,
        query: str,
        max_results: int = 500
    ) -> List[Dict]:
        """
        Get Gmail message IDs using a query with automatic token refresh and pagination.

        Args:
            user_email: User's email address (for token lookup)
            query: Gmail search query
            max_results: Maximum number of results to return

        Returns:
            List of message objects with 'id' and 'threadId'
        """
        try:
            logger.info("🔧 [GmailSyncService] get_messages_list() called")
            logger.info(f"   User: {user_email}")
            logger.info(f"   Query length: {len(query)} chars")
            logger.info(f"   Max results: {max_results}")

            # Get fresh access token from token manager
            if not self.token_manager:
                logger.error("❌ [GmailSyncService] Token manager not configured")
                raise ValueError("Token manager not configured")

            logger.info("🔑 [GmailSyncService] Getting valid access token...")
            access_token = await self.token_manager.get_valid_access_token(user_email, 'google')

            if not access_token:
                logger.error("[GmailSyncService] No valid Gmail token found for user")
                raise ValueError(
                    "Gmail authentication failed. Please reconnect your Google account in Settings. "
                    "This may be due to an expired refresh token or network connectivity issues."
                )

            logger.info(f"[GmailSyncService] Access token obtained (length: {len(access_token)} chars)")

            logger.info("[GmailSyncService] Building Gmail service...")
            service = self._build_service(access_token)
            logger.info("✅ [GmailSyncService] Gmail service built successfully")

            messages = []
            page_token = None
            page_count = 0

            logger.info("🔄 [GmailSyncService] Starting pagination loop...")
            while True:
                page_count += 1
                logger.info(f"📄 [GmailSyncService] Fetching page {page_count}...")

                # Search for messages with pagination
                request_params = {
                    'userId': 'me',
                    'q': query,
                    'maxResults': min(max_results - len(messages), 100)
                }

                if page_token:
                    request_params['pageToken'] = page_token
                    logger.info(f"   Using page token: {page_token[:20]}...")

                logger.info(f"🌐 [GmailSyncService] Calling Gmail API list() with maxResults={request_params['maxResults']}...")
                results = service.users().messages().list(**request_params).execute()
                logger.info(f"✅ [GmailSyncService] Gmail API list() returned successfully")

                page_messages = results.get('messages', [])
                messages.extend(page_messages)
                logger.info(f"✅ [GmailSyncService] Page {page_count}: Got {len(page_messages)} messages (total: {len(messages)})")

                page_token = results.get('nextPageToken')
                if not page_token or len(messages) >= max_results:
                    logger.info(f"🏁 [GmailSyncService] Pagination complete (page_token={bool(page_token)}, messages={len(messages)}/{max_results})")
                    break

                # Log progress for large syncs
                if len(messages) % 500 == 0:
                    logger.info(f"📊 [GmailSyncService] Fetched {len(messages)} message IDs so far...")

            logger.info(f"✅ [GmailSyncService] get_messages_list completed: {len(messages)} total messages")
            return messages

        except Exception as e:
            logger.error(f"❌ [GmailSyncService] Error in get_messages_list: {e}", exc_info=True)
            raise

    async def get_message_details(
        self,
        user_email: str,
        message_id: str,
        include_body: bool = False
    ) -> Optional[Dict]:
        """
        Get Gmail message details using Google API client library.

        Args:
            user_email: User's email address (for token lookup)
            message_id: Gmail message ID
            include_body: Whether to include full message body

        Returns:
            Message object or None if retrieval fails
        """
        try:
            # Get fresh access token from token manager
            if not self.token_manager:
                raise ValueError("Token manager not configured")

            access_token = await self.token_manager.get_valid_access_token(user_email, 'google')

            if not access_token:
                logger.error("No valid Gmail token found for user")
                raise ValueError(
                    "Gmail authentication failed. Please reconnect your Google account in Settings. "
                    "This may be due to an expired refresh token or network connectivity issues."
                )

            service = self._build_service(access_token)

            # Request format - metadata is lighter than full
            format_param = 'full' if include_body else 'metadata'

            message = service.users().messages().get(
                userId='me',
                id=message_id,
                format=format_param
            ).execute()

            return message

        except Exception as e:
            logger.error(f"Error getting message {message_id}: {e}")
            return None

    def batch_get_messages(
        self,
        gmail_service,
        message_ids: List[str],
        include_body: bool = False
    ) -> List[Dict]:
        """
        Batch retrieve Gmail messages using simple sequential fetching (faster than batch API with delays).

        Args:
            gmail_service: Gmail API service object (already authenticated)
            message_ids: List of message IDs to retrieve
            include_body: Whether to include email body content

        Returns:
            List of Gmail message objects
        """
        if not message_ids:
            return []

        logger.info(f"📦 Fetching {len(message_ids)} emails using sequential API calls")

        all_messages = []
        # Always fetch 'full' format to get body for notification previews
        format_param = 'full'

        # Simple sequential fetching - faster than batch API with delays
        for idx, message_id in enumerate(message_ids):
            if (idx + 1) % 50 == 0:
                logger.info(f"📊 Progress: {idx + 1}/{len(message_ids)} messages fetched")

            try:
                message = gmail_service.users().messages().get(
                    userId='me',
                    id=message_id,
                    format=format_param
                ).execute()
                all_messages.append(message)
            except Exception as e:
                logger.warning(f"⚠️ Failed to fetch message {message_id}: {e}")
                continue

        logger.info(f"✅ Sequential fetch complete: {len(all_messages)}/{len(message_ids)} messages retrieved")
        return all_messages

    def is_available(self) -> bool:
        """Check if Gmail service is available."""
        return GOOGLE_API_AVAILABLE and self.client_id and self.client_secret

