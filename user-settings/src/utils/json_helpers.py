"""Shared JSON/JSONB helpers for asyncpg compatibility."""

import json


def parse_jsonb(val):
    """Parse JSONB values that asyncpg may return as string or dict/list."""
    if val is None:
        return None
    return json.loads(val) if isinstance(val, str) else val
