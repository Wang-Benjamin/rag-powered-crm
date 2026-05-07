"""Email signature service (asyncpg).

All writes to employee_info.signature_fields go through _set_signature_fields —
enforced by CI grep (test_signature_fields_writes_only_via_helper). Bypassing
the helper stores a JSON-string-scalar instead of a dict (asyncpg JSONB gotcha).
"""

import json
import logging
from typing import Optional

import asyncpg

from utils.json_helpers import parse_jsonb

logger = logging.getLogger(__name__)


async def _set_signature_fields(
    conn: asyncpg.Connection,
    employee_email: str,
    fields_dict: dict,
) -> None:
    """Mandatory write helper. Wraps json.dumps once.

    All writes to signature_fields go through this — enforced by CI grep
    (test_signature_fields_writes_only_via_helper). Skipping json.dumps
    stores a JSON-string-scalar instead of a dict (asyncpg gotcha).

    NOTE: do NOT add a ``::jsonb`` cast on the bind param. asyncpg's JSONB
    codec already encodes the value once; combining ``json.dumps`` with the
    cast double-encodes and stores a quoted string scalar instead of an
    object. See writing_style_router.py:51-52 for the canonical pattern."""
    await conn.execute(
        """
        UPDATE employee_info
        SET signature_fields = $1,
            updated_at = CURRENT_TIMESTAMP
        WHERE email = $2
        """,
        json.dumps(fields_dict),
        employee_email,
    )


async def get_email_signature_service(
    conn: asyncpg.Connection,
    employee_email: str,
) -> Optional[dict]:
    """Returns the signature_fields dict + updated_at, or None if not set."""
    row = await conn.fetchrow(
        """
        SELECT signature_fields, updated_at
        FROM employee_info
        WHERE email = $1
        """,
        employee_email,
    )
    if not row or not row['signature_fields']:
        return None
    # asyncpg returns JSONB as either a dict or a string depending on how it was
    # written; parse_jsonb normalizes both forms (project convention).
    try:
        fields = parse_jsonb(row['signature_fields'])
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(
            f"signature.read.malformed_jsonb for {employee_email}: {e}"
        )
        return None
    if not isinstance(fields, dict):
        logger.error(
            f"signature.read.malformed_jsonb for {employee_email}: type={type(fields)}"
        )
        return None
    return {
        'signature_fields': fields,
        'updated_at': row['updated_at'],
    }


async def upsert_email_signature_service(
    conn: asyncpg.Connection,
    employee_email: str,
    fields_dict: dict,
) -> dict:
    """PUT semantics — full replace. Caller's responsibility to pass the full intended state."""
    # Verify the employee exists; raise to let the route translate to 404.
    exists = await conn.fetchval(
        "SELECT 1 FROM employee_info WHERE email = $1",
        employee_email,
    )
    if not exists:
        raise ValueError(f"Employee not found: {employee_email}")
    await _set_signature_fields(conn, employee_email, fields_dict)
    result = await get_email_signature_service(conn, employee_email)
    assert result is not None  # we just wrote it
    return result


async def partial_update_email_signature_service(
    conn: asyncpg.Connection,
    employee_email: str,
    partial_fields: dict,
) -> dict:
    """PATCH semantics — merge with existing. Only provided fields update."""
    existing = await get_email_signature_service(conn, employee_email)
    current_fields = (existing['signature_fields'] if existing else {}) or {}
    # Router uses model_dump(exclude_unset=True), so a key in partial_fields
    # means the caller explicitly set it. Explicit None means "clear this
    # field"; absent means "don't change". Drop None entries from the merged
    # result so the JSONB stays compact.
    merged = {**current_fields, **partial_fields}
    merged = {k: v for k, v in merged.items() if v is not None}
    await _set_signature_fields(conn, employee_email, merged)
    result = await get_email_signature_service(conn, employee_email)
    assert result is not None
    return result


async def delete_email_signature_service(
    conn: asyncpg.Connection,
    employee_email: str,
) -> bool:
    """Clear the signature. Sets signature_fields to NULL."""
    result = await conn.execute(
        """
        UPDATE employee_info
        SET signature_fields = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE email = $1
        """,
        employee_email,
    )
    # asyncpg returns "UPDATE N" — extract N.
    return int(result.split()[-1]) > 0
