"""Product Catalog Repository.

CRUD helpers for ``product_catalog``. First caller is the ingestion router's
commit endpoint for ``product_pdf`` (M5) and ``product_csv`` (M6); the
storefront 待上线/已上线 tabs go through ``product_catalog_router``.

All methods take an asyncpg connection as the first parameter and expect
the caller to be in a transaction when doing multi-row writes.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

# Columns selected by every read path so the router can map a row to its
# response shape without touching SQL. Kept as a module constant so the
# repo and the router agree on the projection.
SELECT_COLS = (
    "product_id, email, name, description, specs, image_url, moq, "
    "price_range, hs_code, source_job_id, status, published_at, "
    "created_at, updated_at"
)


async def bulk_insert_products(
    conn,
    *,
    email: str,
    products: Iterable[dict],
    source_job_id: Optional[uuid.UUID],
) -> list[uuid.UUID]:
    """Insert many product rows in a single transaction.

    Each ``products`` item is a dict matching :class:`ProductRecordDraft`.
    Unknown fields are ignored; required field is ``name``.

    Returns the list of newly-created ``product_id`` UUIDs.
    """
    rows_to_insert: list[tuple] = []
    for raw in products:
        name = (raw.get("name") or "").strip()
        if not name:
            # Skip rows with no name. ProductRecordDraft enforces this at the
            # pydantic layer, but the commit payload comes from the frontend
            # and the user might have cleared a name in the review table.
            continue
        rows_to_insert.append(
            (
                email,
                name[:500],
                raw.get("description") or None,
                json.dumps(raw.get("specs") or {}),
                raw.get("image_url") or None,
                _int_or_none(raw.get("moq")),
                json.dumps(raw["price_range"]) if raw.get("price_range") else None,
                _str_or_none(raw.get("hs_code_suggestion"), 16),
                source_job_id,
            )
        )

    if not rows_to_insert:
        return []

    # executemany with RETURNING isn't supported by asyncpg; use a single
    # INSERT ... SELECT from unnest() so we get all product_ids back in one
    # round-trip. Caller is responsible for wrapping this in a transaction.
    emails = [r[0] for r in rows_to_insert]
    names = [r[1] for r in rows_to_insert]
    descriptions = [r[2] for r in rows_to_insert]
    specs = [r[3] for r in rows_to_insert]
    image_urls = [r[4] for r in rows_to_insert]
    moqs = [r[5] for r in rows_to_insert]
    price_ranges = [r[6] for r in rows_to_insert]
    hs_codes = [r[7] for r in rows_to_insert]
    job_ids = [r[8] for r in rows_to_insert]

    records = await conn.fetch(
        """
        INSERT INTO product_catalog (
            email, name, description, specs, image_url, moq, price_range,
            hs_code, source_job_id
        )
        SELECT
            u.email, u.name, u.description, u.specs::jsonb,
            u.image_url, u.moq, u.price_range::jsonb, u.hs_code, u.source_job_id
        FROM UNNEST(
            $1::text[], $2::text[], $3::text[], $4::text[],
            $5::text[], $6::int[], $7::text[], $8::text[], $9::uuid[]
        ) AS u(
            email, name, description, specs, image_url, moq, price_range,
            hs_code, source_job_id
        )
        RETURNING product_id
        """,
        emails, names, descriptions, specs, image_urls, moqs,
        price_ranges, hs_codes, job_ids,
    )
    ids = [r["product_id"] for r in records]
    logger.info(
        "product_catalog: inserted %d rows email=%s source_job_id=%s",
        len(ids), email, source_job_id,
    )
    return ids


def _str_or_none(value: Any, max_len: int) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return s[:max_len]


def _int_or_none(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def list_products(
    conn,
    *,
    email: str,
    status: Optional[str] = None,
) -> list[dict]:
    """Return current user's catalog rows, newest first."""
    if status is None:
        rows = await conn.fetch(
            f"SELECT {SELECT_COLS} FROM product_catalog "
            "WHERE email = $1 ORDER BY created_at DESC",
            email,
        )
    else:
        rows = await conn.fetch(
            f"SELECT {SELECT_COLS} FROM product_catalog "
            "WHERE email = $1 AND status = $2 ORDER BY created_at DESC",
            email, status,
        )
    return [dict(r) for r in rows]


async def get_product(conn, *, product_id: uuid.UUID, email: str) -> Optional[dict]:
    """Fetch one row scoped to ``email``. Returns None if missing."""
    row = await conn.fetchrow(
        f"SELECT {SELECT_COLS} FROM product_catalog "
        "WHERE product_id = $1 AND email = $2",
        product_id, email,
    )
    return dict(row) if row else None


async def insert_product(
    conn,
    *,
    email: str,
    name: str,
    description: Optional[str] = None,
    specs: Optional[dict] = None,
    image_url: Optional[str] = None,
    moq: Optional[int] = None,
    price_range: Optional[dict] = None,
    hs_code: Optional[str] = None,
) -> dict:
    """Insert one row from a manual add (no ingestion job). Returns the row.

    JSONB columns are passed as Python dicts directly — the connection-level
    codec in ``service_core.pool._init_connection`` encodes via
    ``json.dumps``. Wrapping here would double-encode and produce a JSONB
    string scalar (see the gotcha in
    ``factory_profile_router.persist_factory_profile``). The legacy
    ``bulk_insert_products`` above uses a different shape (``text[]`` plus
    SQL casts) and intentionally still calls ``json.dumps``; the two paths
    are not symmetric.
    """
    row = await conn.fetchrow(
        f"""
        INSERT INTO product_catalog (
            email, name, description, specs, image_url, moq, price_range, hs_code
        ) VALUES (
            $1, $2, $3, COALESCE($4::jsonb, '{{}}'::jsonb), $5, $6, $7::jsonb, $8
        )
        RETURNING {SELECT_COLS}
        """,
        email,
        name[:500],
        description,
        specs if specs is not None else None,
        image_url,
        moq,
        price_range,
        _str_or_none(hs_code, 16),
    )
    return dict(row)


async def update_product(
    conn,
    *,
    product_id: uuid.UUID,
    email: str,
    fields: dict,
) -> Optional[dict]:
    """Partial update. Only the keys present in ``fields`` are written.

    ``status`` and ``published_at`` are intentionally not writable here —
    publish flow goes through :func:`set_status` to keep the
    ``published_at`` stamp logic in one place. Returns the updated row, or
    ``None`` if nothing matched (caller raises 404).
    """
    allowed = {
        "name", "description", "specs", "image_url",
        "moq", "price_range", "hs_code",
    }
    sets: list[str] = []
    params: list[Any] = []
    idx = 1
    for key, value in fields.items():
        if key not in allowed:
            continue
        if key in ("specs", "price_range"):
            sets.append(f"{key} = ${idx}::jsonb")
        elif key == "name":
            sets.append(f"name = ${idx}")
            value = (value or "")[:500]
        elif key == "hs_code":
            sets.append(f"hs_code = ${idx}")
            value = _str_or_none(value, 16)
        else:
            sets.append(f"{key} = ${idx}")
        params.append(value)
        idx += 1

    if not sets:
        # Nothing to write — return current row so the caller still gets a
        # consistent response shape.
        return await get_product(conn, product_id=product_id, email=email)

    sets.append("updated_at = NOW()")
    params.extend([product_id, email])
    sql = (
        f"UPDATE product_catalog SET {', '.join(sets)} "
        f"WHERE product_id = ${idx} AND email = ${idx + 1} "
        f"RETURNING {SELECT_COLS}"
    )
    row = await conn.fetchrow(sql, *params)
    return dict(row) if row else None


async def delete_product(conn, *, product_id: uuid.UUID, email: str) -> bool:
    """Delete one row scoped to ``email``. Returns True iff a row was removed."""
    result = await conn.execute(
        "DELETE FROM product_catalog WHERE product_id = $1 AND email = $2",
        product_id, email,
    )
    # asyncpg returns 'DELETE <count>'.
    try:
        return int(result.split()[-1]) > 0
    except (ValueError, IndexError):
        return False


async def set_status(
    conn,
    *,
    product_id: uuid.UUID,
    email: str,
    status: str,
) -> Optional[dict]:
    """Flip status on one row. Idempotent for the publish case.

    For ``status='live'`` the ``published_at`` stamp is set on the first
    transition (``COALESCE(published_at, NOW())``) and preserved on
    re-publish so the timestamp the buyer saw doesn't drift. For
    ``status='pending'`` we clear ``published_at``.
    """
    if status == "live":
        sql = (
            "UPDATE product_catalog SET status = 'live', "
            "published_at = COALESCE(published_at, NOW()), updated_at = NOW() "
            f"WHERE product_id = $1 AND email = $2 RETURNING {SELECT_COLS}"
        )
    elif status == "pending":
        sql = (
            "UPDATE product_catalog SET status = 'pending', "
            "published_at = NULL, updated_at = NOW() "
            f"WHERE product_id = $1 AND email = $2 RETURNING {SELECT_COLS}"
        )
    else:
        raise ValueError(f"unsupported status {status!r}")
    row = await conn.fetchrow(sql, product_id, email)
    return dict(row) if row else None


async def set_status_bulk(
    conn,
    *,
    product_ids: Iterable[uuid.UUID],
    email: str,
    status: str,
) -> list[dict]:
    """Bulk flip status for the publish-bulk endpoint.

    Returns the affected rows in their post-update form. Skips ids that
    don't belong to ``email`` (no error — the caller treats unknown ids as
    a no-op, matching the per-row endpoint's email-scoped 404 semantics
    when applied across a list).
    """
    ids = list(product_ids)
    if not ids:
        return []

    if status == "live":
        sql = (
            "UPDATE product_catalog SET status = 'live', "
            "published_at = COALESCE(published_at, NOW()), updated_at = NOW() "
            f"WHERE product_id = ANY($1::uuid[]) AND email = $2 "
            f"RETURNING {SELECT_COLS}"
        )
    elif status == "pending":
        sql = (
            "UPDATE product_catalog SET status = 'pending', "
            "published_at = NULL, updated_at = NOW() "
            f"WHERE product_id = ANY($1::uuid[]) AND email = $2 "
            f"RETURNING {SELECT_COLS}"
        )
    else:
        raise ValueError(f"unsupported status {status!r}")

    rows = await conn.fetch(sql, ids, email)
    return [dict(r) for r in rows]
