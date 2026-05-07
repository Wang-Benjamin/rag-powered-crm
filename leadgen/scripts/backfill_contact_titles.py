"""
One-off: add `validated_contact_title` column to bol_companies and
backfill titles for the 12 rows seeded by seed_two_pager_contacts.py.

We don't re-query Apollo (already paid for those calls). Instead we ask
Sonnet for a plausible title given {company_name, contact_name, hs_code
hint}. Since the contact_name is real, Sonnet's title inference is
reasonable (e.g., Gary Siegal at Satco → "Vice President, Sales").

Usage:
    uv run python scripts/backfill_contact_titles.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg  # type: ignore
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

from importyeti.reports.email_generator import _extract_json


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_titles")


CHUNK_SIZE = 15


async def _infer_titles_one_batch(
    anthropic_client: AsyncAnthropic, rows: list[dict], timeout: float = 60.0,
) -> dict[str, str]:
    lines = [
        f"- id={r['id']} company={r['company_name']} "
        f"contact={r['validated_contact_name']}"
        for r in rows
    ]
    user = (
        "For each US company below and the named contact, return a "
        "plausible business title for that person at that company. Aim "
        "for senior commercial roles (VP, Director, Head of) relevant to "
        "sourcing / procurement / product / sales. Keep each title under "
        "60 chars.\n\n"
        + "\n".join(lines)
        + '\n\nReturn JSON of exact shape: {"titles": {"<id>": '
        '"Vice President, Sourcing"}}. JSON only, no prose, no code fences.'
    )
    try:
        resp = await asyncio.wait_for(
            anthropic_client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=3000,
                system=(
                    "You infer plausible B2B job titles. Return JSON only, "
                    "no prose, no markdown fences."
                ),
                messages=[{"role": "user", "content": user}],
            ),
            timeout=timeout,
        )
    except Exception as e:
        logger.warning(f"Sonnet call failed for batch of {len(rows)}: {e}")
        return {}
    raw = ""
    for block in resp.content or []:
        if getattr(block, "type", None) == "text":
            raw += getattr(block, "text", "")
    payload = _extract_json(raw)
    if not isinstance(payload, dict):
        logger.warning(f"Sonnet returned unparseable JSON (first 200 chars): {raw[:200]!r}")
        return {}
    titles = payload.get("titles")
    if not isinstance(titles, dict):
        logger.warning(f"Sonnet response missing 'titles' key: {raw[:200]!r}")
        return {}
    return {
        str(k): str(v).strip()
        for k, v in titles.items()
        if isinstance(v, str) and v.strip()
    }


async def batch_infer_titles(
    anthropic_client: AsyncAnthropic, rows: list[dict], timeout: float = 60.0,
) -> dict[str, str]:
    """Return {id: title} for each row; chunks large inputs to avoid token limits."""
    out: dict[str, str] = {}
    for i in range(0, len(rows), CHUNK_SIZE):
        chunk = rows[i : i + CHUNK_SIZE]
        logger.info(f"Inferring titles for chunk {i // CHUNK_SIZE + 1} ({len(chunk)} rows)")
        result = await _infer_titles_one_batch(anthropic_client, chunk, timeout=timeout)
        out.update(result)
    return out


async def main() -> None:
    here = Path(__file__).parent.parent
    load_dotenv(here / ".env", override=False)
    load_dotenv(here.parent / "prelude-user-settings" / ".env", override=False)

    try:
        db_user = os.environ["SESSIONS_DB_USER"]
        db_pw = os.environ["SESSIONS_DB_PASSWORD"]
        db_host = os.environ["SESSIONS_DB_HOST"]
        db_port = int(os.environ.get("SESSIONS_DB_PORT", "5432"))
        anthropic_key = os.environ["ANTHROPIC_API_KEY"]
    except KeyError as e:
        raise SystemExit(f"Missing env var: {e}") from e

    dsn = f"postgresql://{db_user}:{db_pw}@{db_host}:{db_port}/prelude_lead_db"
    conn = await asyncpg.connect(dsn)

    try:
        # 1. Ensure the column exists (idempotent).
        await conn.execute(
            """
            ALTER TABLE bol_companies
            ADD COLUMN IF NOT EXISTS validated_contact_title VARCHAR(255)
            """
        )
        logger.info("validated_contact_title column ensured")

        # 2. Find rows that need backfill.
        rows = await conn.fetch(
            """
            SELECT id::text AS id, company_name, validated_contact_name
              FROM bol_companies
             WHERE validated_email IS NOT NULL
               AND validated_contact_name IS NOT NULL
               AND (validated_contact_title IS NULL OR validated_contact_title = '')
             ORDER BY company_name
            """
        )
        logger.info(f"Rows missing title: {len(rows)}")
        if not rows:
            logger.info("Nothing to backfill.")
            return

        # 3. Sonnet call.
        anthropic_client = AsyncAnthropic(api_key=anthropic_key)
        titles = await batch_infer_titles(anthropic_client, [dict(r) for r in rows])
        logger.info(f"Got {len(titles)} titles from Sonnet")

        # 4. UPDATE each row.
        updated = 0
        for row in rows:
            title = titles.get(row["id"])
            if not title:
                logger.warning(f"No title for {row['company_name']} — leaving null")
                continue
            await conn.execute(
                """
                UPDATE bol_companies
                   SET validated_contact_title = $1
                 WHERE id = $2::uuid
                """,
                title, row["id"],
            )
            updated += 1
            logger.info(f"✅ {row['company_name']}: {row['validated_contact_name']} → {title}")
        logger.info(f"Backfilled {updated}/{len(rows)} titles.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
