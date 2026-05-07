"""
Embedding Sync Service - Backfill and maintain embeddings for CRM data.

Populates embedding columns for interaction_details, crm_emails, and
employee_client_notes tables using the asyncpg tenant pool manager.
"""

import re
import logging
from typing import Dict, Any, List, Optional

import asyncpg

from services.rag.embedding_service import get_embedding_service, EMBEDDING_DIM

logger = logging.getLogger(__name__)


# Patterns for email pre-cleaning before embedding
_QUOTED_REPLY_RE = re.compile(
    r'(?:^>.*$\n?)|'                                    # Lines starting with >
    r'(?:^On\s.+wrote:\s*$\n?)|'                        # "On ... wrote:" headers
    r'(?:^-{2,}\s*(?:Original Message|Forwarded).*$\n?)',  # ---- Original Message ----
    re.MULTILINE | re.IGNORECASE,
)
_GREETING_RE = re.compile(
    r'^(?:Hi|Hello|Hey|Dear|Good\s+(?:morning|afternoon|evening))\b[^.\n]{0,50}[,!]?\s*\n',
    re.MULTILINE | re.IGNORECASE,
)
_SIGNATURE_RE = re.compile(
    r'(?:^(?:Best(?:\s+regards)?|Kind\s+regards|Regards|Thanks|Thank\s+you|Cheers|Sincerely|Warm\s+regards)'
    r'[,.]?\s*$)'
    r'[\s\S]*',   # consume everything after the signature line
    re.MULTILINE | re.IGNORECASE,
)
_HTML_TAG_RE = re.compile(r'<[^>]+>')
_EXCESS_WHITESPACE_RE = re.compile(r'\n{3,}')


def clean_email_for_embedding(text: str) -> str:
    """
    Pre-clean email body before embedding generation.

    Removes quoted replies, greetings, signatures, and HTML remnants so the
    embedding captures only the substantive message content.
    """
    if not text:
        return text

    text = _HTML_TAG_RE.sub('', text)
    text = _QUOTED_REPLY_RE.sub('', text)
    text = _GREETING_RE.sub('', text)
    text = _SIGNATURE_RE.sub('', text)
    text = _EXCESS_WHITESPACE_RE.sub('\n\n', text)
    return text.strip()


async def _register_vector(conn: asyncpg.Connection):
    """Register pgvector type with asyncpg connection."""
    from pgvector.asyncpg import register_vector
    await register_vector(conn)


async def _get_pool_connection(user_email: str):
    """Get a pool manager connection for fire-and-forget background tasks."""
    from service_core.db import get_pool_manager
    pm = get_pool_manager()
    db_name = await pm.lookup_db_name(user_email)
    return pm, db_name


async def populate_interaction_embeddings(
    conn: asyncpg.Connection,
    batch_size: int = 100,
) -> Dict[str, Any]:
    """
    Backfill embeddings for interaction_details rows with NULL embedding.

    Returns stats dict with total_processed, total_embedded, errors.
    """
    embedding_service = get_embedding_service()
    stats = {"total_processed": 0, "total_embedded": 0, "errors": 0}

    await _register_vector(conn)

    offset = 0
    batch_num = 0
    while True:
        batch = await conn.fetch("""
            SELECT interaction_id, content
            FROM interaction_details
            WHERE embedding IS NULL AND content IS NOT NULL AND content != ''
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
        """, batch_size, offset)

        if not batch:
            if batch_num == 0:
                logger.info("No interaction embeddings to backfill")
            break

        batch_num += 1
        texts = [row['content'] for row in batch]
        ids = [row['interaction_id'] for row in batch]

        try:
            embeddings = await embedding_service.embed_batch(texts)

            embedded_count = 0
            for emb, row_id in zip(embeddings, ids):
                if emb is not None:
                    await conn.execute(
                        "UPDATE interaction_details SET embedding = $1 WHERE interaction_id = $2",
                        emb, row_id
                    )
                    embedded_count += 1

            stats["total_embedded"] += embedded_count
            logger.info(f"Embedded interaction batch {batch_num} ({len(batch)} rows)")
        except Exception as e:
            stats["errors"] += 1
            logger.error(f"Error embedding interaction batch: {e}")

        stats["total_processed"] += len(batch)
        offset += batch_size

    return stats


async def populate_email_embeddings(
    conn: asyncpg.Connection,
    batch_size: int = 100,
) -> Dict[str, Any]:
    """
    Backfill embeddings for crm_emails rows with NULL embedding.
    """
    embedding_service = get_embedding_service()
    stats = {"total_processed": 0, "total_embedded": 0, "errors": 0}

    await _register_vector(conn)

    offset = 0
    batch_num = 0
    while True:
        batch = await conn.fetch("""
            SELECT email_id, subject, body
            FROM crm_emails
            WHERE embedding IS NULL
            AND (subject IS NOT NULL OR body IS NOT NULL)
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
        """, batch_size, offset)

        if not batch:
            if batch_num == 0:
                logger.info("No email embeddings to backfill")
            break

        batch_num += 1
        texts = [
            f"Subject: {row.get('subject', '') or ''}\n\n{clean_email_for_embedding(row.get('body', '') or '')}".strip()
            for row in batch
        ]
        ids = [row['email_id'] for row in batch]

        try:
            embeddings = await embedding_service.embed_batch(texts)

            embedded_count = 0
            for emb, row_id in zip(embeddings, ids):
                if emb is not None:
                    await conn.execute(
                        "UPDATE crm_emails SET embedding = $1 WHERE email_id = $2",
                        emb, row_id
                    )
                    embedded_count += 1

            stats["total_embedded"] += embedded_count
        except Exception as e:
            stats["errors"] += 1
            logger.error(f"Error embedding email batch: {e}")

        stats["total_processed"] += len(batch)
        offset += batch_size

    return stats


async def populate_note_embeddings(
    conn: asyncpg.Connection,
    batch_size: int = 100,
) -> Dict[str, Any]:
    """
    Backfill embeddings for employee_client_notes rows with NULL embedding.
    """
    embedding_service = get_embedding_service()
    stats = {"total_processed": 0, "total_embedded": 0, "errors": 0}

    await _register_vector(conn)

    offset = 0
    batch_num = 0
    while True:
        batch = await conn.fetch("""
            SELECT note_id, title, body
            FROM employee_client_notes
            WHERE embedding IS NULL
            AND (title IS NOT NULL OR body IS NOT NULL)
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
        """, batch_size, offset)

        if not batch:
            if batch_num == 0:
                logger.info("No note embeddings to backfill")
            break

        batch_num += 1
        texts = [
            f"{row.get('title', '') or ''}\n\n{row.get('body', '') or ''}".strip()
            for row in batch
        ]
        ids = [row['note_id'] for row in batch]

        try:
            embeddings = await embedding_service.embed_batch(texts)

            embedded_count = 0
            for emb, row_id in zip(embeddings, ids):
                if emb is not None:
                    await conn.execute(
                        "UPDATE employee_client_notes SET embedding = $1 WHERE note_id = $2",
                        emb, row_id
                    )
                    embedded_count += 1

            stats["total_embedded"] += embedded_count
        except Exception as e:
            stats["errors"] += 1
            logger.error(f"Error embedding note batch: {e}")

        stats["total_processed"] += len(batch)
        offset += batch_size

    return stats


async def get_embedding_stats(conn: asyncpg.Connection) -> Dict[str, Any]:
    """Get embedding coverage statistics for the tenant."""
    stats = {}

    # Interaction embeddings
    row = await conn.fetchrow("""
        SELECT
            COUNT(*) as total,
            COUNT(embedding) as embedded,
            COUNT(*) - COUNT(embedding) as missing
        FROM interaction_details
        WHERE content IS NOT NULL AND content != ''
    """)
    total = row['total'] or 0
    stats["interactions"] = {
        "total": total,
        "embedded": row['embedded'] or 0,
        "missing": row['missing'] or 0,
        "coverage_pct": round((row['embedded'] / total * 100) if total > 0 else 0, 1)
    }

    # Email embeddings
    row = await conn.fetchrow("""
        SELECT
            COUNT(*) as total,
            COUNT(embedding) as embedded,
            COUNT(*) - COUNT(embedding) as missing
        FROM crm_emails
        WHERE subject IS NOT NULL OR body IS NOT NULL
    """)
    total = row['total'] or 0
    stats["emails"] = {
        "total": total,
        "embedded": row['embedded'] or 0,
        "missing": row['missing'] or 0,
        "coverage_pct": round((row['embedded'] / total * 100) if total > 0 else 0, 1)
    }

    # Note embeddings
    row = await conn.fetchrow("""
        SELECT
            COUNT(*) as total,
            COUNT(embedding) as embedded,
            COUNT(*) - COUNT(embedding) as missing
        FROM employee_client_notes
        WHERE title IS NOT NULL OR body IS NOT NULL
    """)
    total = row['total'] or 0
    stats["notes"] = {
        "total": total,
        "embedded": row['embedded'] or 0,
        "missing": row['missing'] or 0,
        "coverage_pct": round((row['embedded'] / total * 100) if total > 0 else 0, 1)
    }

    return stats


async def embed_single_interaction(user_email: str, interaction_id: int, content: str):
    """Fire-and-forget: embed a single interaction after creation."""
    try:
        embedding_service = get_embedding_service()
        embedding = await embedding_service.embed(content)
        if embedding is None:
            return

        pm, db_name = await _get_pool_connection(user_email)
        async with pm.acquire(db_name) as conn:
            await _register_vector(conn)
            await conn.execute(
                "UPDATE interaction_details SET embedding = $1 WHERE interaction_id = $2",
                embedding, interaction_id
            )
    except Exception as e:
        logger.warning(f"Failed to embed interaction {interaction_id}: {e}")


async def embed_single_note(user_email: str, note_id: int, title: str, body: str):
    """Fire-and-forget: embed a single note after creation."""
    try:
        text = f"{title or ''}\n\n{body or ''}".strip()
        if not text:
            return

        embedding_service = get_embedding_service()
        embedding = await embedding_service.embed(text)
        if embedding is None:
            return

        pm, db_name = await _get_pool_connection(user_email)
        async with pm.acquire(db_name) as conn:
            await _register_vector(conn)
            await conn.execute(
                "UPDATE employee_client_notes SET embedding = $1 WHERE note_id = $2",
                embedding, note_id
            )
    except Exception as e:
        logger.warning(f"Failed to embed note {note_id}: {e}")


async def embed_single_email(user_email: str, email_id: int, subject: str, body: str):
    """Fire-and-forget: embed a single email after creation.

    The body is pre-cleaned (quotes, greetings, signatures removed) so the
    embedding captures only the substantive message content.
    """
    try:
        cleaned_body = clean_email_for_embedding(body or '')
        text = f"Subject: {subject or ''}\n\n{cleaned_body}".strip()
        if not text:
            return

        embedding_service = get_embedding_service()
        embedding = await embedding_service.embed(text)
        if embedding is None:
            return

        pm, db_name = await _get_pool_connection(user_email)
        async with pm.acquire(db_name) as conn:
            await _register_vector(conn)
            await conn.execute(
                "UPDATE crm_emails SET embedding = $1 WHERE email_id = $2",
                embedding, email_id
            )
    except Exception as e:
        logger.warning(f"Failed to embed email {email_id}: {e}")
