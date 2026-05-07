from fastapi import HTTPException
from datetime import datetime, timezone

DAILY_CAP = 25


async def check_daily_send_cap(conn, pending: int = 1) -> None:
    """Raise HTTP 429 if adding `pending` sends would exceed the DAILY_CAP/24h tenant cap."""
    sent = await conn.fetchval(
        "SELECT COUNT(*) FROM crm_emails "
        "WHERE direction = 'sent' AND created_at > NOW() - INTERVAL '24 hours'"
    )
    sent = int(sent or 0)
    remaining = DAILY_CAP - sent
    if remaining <= 0:
        raise HTTPException(
            status_code=429,
            detail=f"Daily send limit reached ({DAILY_CAP}/24h). Try again tomorrow.",
        )
    if pending > remaining:
        raise HTTPException(
            status_code=429,
            detail=f"Only {remaining} send(s) remaining today (limit: {DAILY_CAP}/24h). Reduce your selection to {remaining} or fewer.",
        )
