"""Shared fixtures for prelude-leadgen integration tests against prelude_lead_db_dev.

Asyncpg-backed counterpart to prelude-internal-leads-db/tests/fixture/conftest.py.
Used primarily by test_13 (PowerQuery cache-miss path), which goes through
BolSearchService → internal_bol_client → async HTTP to the internal-leads-db
server. Some tests use psycopg2 directly for setup/teardown and assertions.

Isolation: every seeded row's importyeti_slug prefixes FXT_T<NN>_. Cleanup
runs before and after each test.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import AsyncIterator, Iterator

import pytest
import pytest_asyncio

# Paths: prelude-platform-new/prelude/prelude-leadgen + prelude-shared.
LEADGEN_ROOT = Path(__file__).resolve().parents[2]
PLATFORM_ROOT = LEADGEN_ROOT.parents[1]
SHARED_ROOT = PLATFORM_ROOT / "prelude" / "prelude-shared"
for entry in (LEADGEN_ROOT, SHARED_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

# Env vars for connecting to prelude_lead_db_dev. Set before any module
# that imports DB config. These match prelude-internal-leads-db settings.
# LEAD_DB_PASSWORD must come from the environment — committing live
# shared-DB credentials is not acceptable.
os.environ.setdefault("LEAD_DB_NAME", "prelude_lead_db_dev")
os.environ.setdefault("LEAD_DB_HOST", "35.193.231.128")
os.environ.setdefault("LEAD_DB_PORT", "5432")
os.environ.setdefault("LEAD_DB_USER", "postgres")

if not os.environ.get("LEAD_DB_PASSWORD"):
    # Fall back to DATABASE_PASSWORD (used by internal-leads-db conftest)
    # so a single env var satisfies both test suites.
    fallback = os.environ.get("DATABASE_PASSWORD")
    if fallback:
        os.environ["LEAD_DB_PASSWORD"] = fallback
    else:
        raise RuntimeError(
            "LEAD_DB_PASSWORD (or DATABASE_PASSWORD) is not set. "
            "tests/fixture/ integration tests need the prelude_lead_db_dev "
            "password via env var. Export it before running pytest."
        )

DEV_DB_DSN = (
    f"postgresql://{os.environ['LEAD_DB_USER']}:{os.environ['LEAD_DB_PASSWORD']}"
    f"@{os.environ['LEAD_DB_HOST']}:{os.environ['LEAD_DB_PORT']}"
    f"/{os.environ['LEAD_DB_NAME']}"
)


@pytest_asyncio.fixture
async def dev_pool() -> AsyncIterator["asyncpg.Pool"]:
    """Async asyncpg pool against prelude_lead_db_dev."""
    import asyncpg

    pool = await asyncpg.create_pool(DEV_DB_DSN, min_size=1, max_size=4)
    try:
        yield pool
    finally:
        await pool.close()


@pytest.fixture
def dev_sync_conn():
    """Sync psycopg2 connection for setup/teardown in async tests."""
    import psycopg2
    conn = psycopg2.connect(
        host=os.environ["LEAD_DB_HOST"],
        port=int(os.environ["LEAD_DB_PORT"]),
        user=os.environ["LEAD_DB_USER"],
        password=os.environ["LEAD_DB_PASSWORD"],
        database=os.environ["LEAD_DB_NAME"],
    )
    conn.autocommit = True
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def fxt_prefix(request) -> str:
    name = request.node.name
    m = re.search(r"[tT](\d+)", name)
    if m:
        return f"FXT_T{int(m.group(1)):02d}_"
    sanitized = re.sub(r"[^a-zA-Z0-9]+", "_", name)[:30].upper()
    return f"FXT_{sanitized}_"


@pytest.fixture
def cleanup_fxt(dev_sync_conn, fxt_prefix) -> Iterator[str]:
    def _clean():
        with dev_sync_conn.cursor() as cur:
            cur.execute(
                "DELETE FROM bol_companies WHERE importyeti_slug LIKE %s OR company_name LIKE %s",
                (f"{fxt_prefix}%", f"{fxt_prefix}%"),
            )
            cur.execute(
                "DELETE FROM bol_competitor_companies WHERE importyeti_slug LIKE %s OR supplier_name LIKE %s",
                (f"{fxt_prefix}%", f"{fxt_prefix}%"),
            )

    _clean()
    try:
        yield fxt_prefix
    finally:
        _clean()


# ── Fixture corpus paths (for tests that need to pass IMPORTYETI_FIXTURE_DIR) ──

COMPANIES_RAW_DIR = str(PLATFORM_ROOT / "tests" / "companies_raw")
COMPETITORS_RAW_DIR = str(PLATFORM_ROOT / "tests" / "competitors_raw")


@pytest.fixture
def companies_raw_dir() -> str:
    return COMPANIES_RAW_DIR


@pytest.fixture
def competitors_raw_dir() -> str:
    return COMPETITORS_RAW_DIR
