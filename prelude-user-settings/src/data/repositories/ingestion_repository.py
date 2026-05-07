"""Ingestion Jobs Repository.

CRUD helpers for ``ingestion_jobs``. All methods take an asyncpg connection as
the first parameter (same convention as AIPreferencesRepository).
"""

import logging
import uuid
from typing import Optional

from utils.json_helpers import parse_jsonb

logger = logging.getLogger(__name__)


VALID_KINDS = {"company_profile", "product_csv", "product_pdf", "certification"}
VALID_STATUSES = {
    "queued",
    "processing",
    "ready_for_review",
    "committed",
    "failed",
    "discarded",
}


async def create_job(conn, email: str, kind: str, source_url: str) -> uuid.UUID:
    """Insert a new job row in ``queued`` status. Returns the new job_id."""
    if kind not in VALID_KINDS:
        raise ValueError(f"invalid ingestion kind: {kind!r}")
    row = await conn.fetchrow(
        """
        INSERT INTO ingestion_jobs (email, kind, source_url, status)
        VALUES ($1, $2, $3, 'queued')
        RETURNING job_id
        """,
        email, kind, source_url,
    )
    job_id = row["job_id"]
    logger.info(f"ingestion_jobs: created {job_id} kind={kind} email={email}")
    return job_id


async def get_job(conn, job_id: uuid.UUID, email: str) -> Optional[dict]:
    """Fetch a single job scoped by email. Returns ``None`` if not found."""
    row = await conn.fetchrow(
        """
        SELECT job_id, email, kind, source_url, status, draft_payload, error,
               created_at, updated_at
        FROM ingestion_jobs
        WHERE job_id = $1 AND email = $2
        """,
        job_id, email,
    )
    if not row:
        return None
    return _row_to_dict(row)


async def update_job_status(
    conn,
    job_id: uuid.UUID,
    status: str,
    *,
    draft_payload: Optional[dict] = None,
    error: Optional[str] = None,
) -> Optional[dict]:
    """Update status (and optionally draft_payload / error). Returns the new row."""
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid ingestion status: {status!r}")
    row = await conn.fetchrow(
        """
        UPDATE ingestion_jobs
        SET status = $2,
            draft_payload = COALESCE($3::jsonb, draft_payload),
            error = CASE WHEN $4::text IS NOT NULL THEN $4 ELSE error END,
            updated_at = now()
        WHERE job_id = $1
        RETURNING job_id, email, kind, source_url, status, draft_payload, error,
                  created_at, updated_at
        """,
        job_id, status, draft_payload, error,
    )
    if not row:
        return None
    logger.info(f"ingestion_jobs: updated {job_id} -> {status}")
    return _row_to_dict(row)


async def list_recent_jobs(
    conn,
    email: str,
    kind: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """List this user's recent jobs, newest first. Optionally filter by kind."""
    if kind is not None and kind not in VALID_KINDS:
        raise ValueError(f"invalid ingestion kind: {kind!r}")
    if kind:
        rows = await conn.fetch(
            """
            SELECT job_id, email, kind, source_url, status, draft_payload, error,
                   created_at, updated_at
            FROM ingestion_jobs
            WHERE email = $1 AND kind = $2
            ORDER BY created_at DESC
            LIMIT $3
            """,
            email, kind, limit,
        )
    else:
        rows = await conn.fetch(
            """
            SELECT job_id, email, kind, source_url, status, draft_payload, error,
                   created_at, updated_at
            FROM ingestion_jobs
            WHERE email = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            email, limit,
        )
    return [_row_to_dict(r) for r in rows]


async def purge_stale_jobs(conn) -> dict:
    """Retention policy (called by the M7 cron).

    - ``processing`` jobs older than 10 minutes → mark ``failed`` (stuck worker).
    - Any terminal-state row older than 30 days → delete.

    Returns a small dict of counts for observability. Does NOT delete the GCS
    blob — the cron script is responsible for that before calling this.
    """
    stuck = await conn.execute(
        """
        UPDATE ingestion_jobs
        SET status = 'failed',
            error = COALESCE(error, 'stuck in processing > 10 minutes'),
            updated_at = now()
        WHERE status = 'processing'
          AND updated_at < now() - INTERVAL '10 minutes'
        """
    )
    deleted = await conn.execute(
        """
        DELETE FROM ingestion_jobs
        WHERE status IN ('committed','failed','discarded')
          AND updated_at < now() - INTERVAL '30 days'
        """
    )
    return {"marked_failed": _affected(stuck), "deleted": _affected(deleted)}


def _row_to_dict(row) -> dict:
    return {
        "job_id": row["job_id"],
        "email": row["email"],
        "kind": row["kind"],
        "source_url": row["source_url"],
        "status": row["status"],
        "draft_payload": parse_jsonb(row["draft_payload"]),
        "error": row["error"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


def _affected(status: str) -> int:
    """asyncpg returns command tags like 'UPDATE 3' / 'DELETE 12'."""
    try:
        return int(status.split()[-1])
    except (ValueError, IndexError):
        return 0
