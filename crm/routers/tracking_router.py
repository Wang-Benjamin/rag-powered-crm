"""Email open tracking router."""

import base64
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Query
from fastapi.responses import Response

from service_core.db import get_pool_manager

logger = logging.getLogger(__name__)
router = APIRouter()

# 1x1 transparent GIF pixel
TRACKING_PIXEL = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)


@router.get("/t/o.gif")
async def track_email_open(t: str, e: Optional[str] = Query(None)):
    """
    Record email open and return 1x1 transparent pixel.

    Args:
        t: Tracking token
        e: Base64-encoded user email for database routing
    """
    try:
        # Decode user email for database routing
        user_email = None
        if e:
            try:
                user_email = base64.urlsafe_b64decode(e.encode()).decode()
                logger.debug(f"Decoded email for tracking: {user_email}")
            except Exception as decode_error:
                logger.error(f"Failed to decode email parameter: {decode_error}")

        pm = get_pool_manager()
        if not user_email or pm is None:
            # Cannot route without email or pool manager
            return Response(
                content=TRACKING_PIXEL,
                media_type="image/gif",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )

        # Look up tenant database for this user
        db_name = await pm.lookup_db_name(user_email)

        async with pm.acquire(db_name) as conn:
            result = await conn.fetchrow("""
                SELECT email_id, opened_at, tracking_token_expires_at
                FROM crm_emails
                WHERE tracking_token = $1
            """, t)

            if result and result["tracking_token_expires_at"] > datetime.now(timezone.utc):
                if result["opened_at"] is None:
                    await conn.execute("""
                        UPDATE crm_emails
                        SET opened_at = $1
                        WHERE tracking_token = $2
                    """, datetime.now(timezone.utc), t)
                    logger.info(f"Email opened: email_id={result['email_id']}, user={user_email}")

    except Exception as e:
        logger.error(f"Tracking error: {e}")

    return Response(
        content=TRACKING_PIXEL,
        media_type="image/gif",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )
