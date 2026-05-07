"""Post-onboarding recovery script for BoL CSV tenants.

Three phases, each independently toggleable, for recovering from a partial
or failed csv-kickoff onboarding run:

  A. Deep-enrich a list of buyer slugs that failed during the first pass
     (e.g. 403'd on an invalid ImportYeti key).
  B. Apollo top-up — add N more leads by pulling cached buyers that
     product-match the tenant's target_products, running them through
     Apollo contact lookup, and piping winners into the same pipeline
     that csv_onboard uses.
  C. Deep-enrich the top competitor row in the tenant's bol_competitors
     table.

All parameters are arguments — no tenant-specific data lives in this file.

Usage:
    cd prelude/prelude-leadgen
    uv run python scripts/post_onboard_recovery.py \\
        --email user@example.com \\
        --db prelude_example \\
        --products "Tinsel Garland" "Wreath" "Christmas Tree" \\
        --failed-slugs slug-one slug-two slug-three \\
        --target-topup 24 \\
        --max-candidates 1500 \\
        --run-phase-a --run-phase-b --run-phase-c

Skip a phase by omitting its --run-phase-X flag.

Apollo is the top-up provider — set ENRICHMENT_PROVIDER=apollo in the
environment before running (or leave the default and pass --force-apollo).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_DB_NAME_PATTERN = re.compile(r'^(postgres|prelude_[a-z0-9_]+)$')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import jwt
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("recovery")


def _mint_token(email: str, db_name: str) -> str:
    secret = os.environ["JWT_SECRET"]
    now = int(time.time())
    return jwt.encode(
        {"email": email, "db_name": db_name, "sub": email, "iat": now, "exp": now + 7200},
        secret, algorithm="HS256",
    )


async def _verify_tenant_exists(email: str, db_name: str) -> None:
    import asyncpg
    db_user = os.environ["SESSIONS_DB_USER"]
    db_pw = os.environ["SESSIONS_DB_PASSWORD"]
    db_host = os.environ["SESSIONS_DB_HOST"]
    db_port = int(os.environ.get("SESSIONS_DB_PORT", "5432"))
    dsn = f"postgresql://{db_user}:{db_pw}@{db_host}:{db_port}/prelude_user_analytics"
    conn = await asyncpg.connect(dsn)
    try:
        row = await conn.fetchrow(
            "SELECT 1 FROM user_profiles WHERE email = $1 AND db_name = $2 LIMIT 1",
            email, db_name,
        )
    finally:
        await conn.close()
    if not row:
        sys.exit(f"No user_profiles row found for email={email} db_name={db_name}")


async def phase_a_deep_enrich(auth_token: str, slugs: List[str]) -> int:
    from importyeti.buyers.service import BolSearchService
    buyer_service = BolSearchService()
    sem = asyncio.Semaphore(5)

    async def _one(slug: str) -> bool:
        async with sem:
            try:
                r = await buyer_service.enrich_company(slug, auth_token)
                status = r.get("enrichment_status")
                logger.info("  deep-enrich %s: %s", slug, status)
                return status == "detail_enriched"
            except Exception as e:
                logger.warning("  deep-enrich %s FAILED: %s", slug, e)
                return False

    results = await asyncio.gather(*[_one(s) for s in slugs])
    return sum(results)


async def phase_b_apollo_topup(
    auth_token: str, *, email: str, db_name: str,
    products: List[str], target_topup: int, max_candidates: int,
) -> Dict[str, Any]:
    from importyeti.clients import internal_bol_client
    from importyeti.services.lead_enrichment import check_company_contact
    from importyeti.services.lead_pipeline import add_slugs_to_pipeline
    from service_core.db import get_pool_manager

    pm = get_pool_manager()

    async with pm.acquire(db_name) as conn:
        rows = await conn.fetch("SELECT LOWER(TRIM(company)) AS c FROM leads")
        existing_names = {r["c"] for r in rows if r["c"]}
    logger.info("existing leads in %s: %d", db_name, len(existing_names))

    candidates = await internal_bol_client.search_cache(
        hs_codes=None, products=products,
        max_results=max_candidates, auth_token=auth_token, slim=True,
    ) or []
    logger.info("cached buyer candidates for products: %d", len(candidates))

    untried: List[Dict[str, Any]] = []
    for c in candidates:
        name = (c.get("company_name") or c.get("companyName") or "").strip().lower()
        slug = c.get("importyeti_slug") or c.get("importyetiSlug")
        if slug and name and name not in existing_names:
            untried.append(c)
    untried.sort(key=lambda r: r.get("matching_shipments") or 0, reverse=True)
    logger.info("untried candidates after dedup: %d", len(untried))

    sem = asyncio.Semaphore(25)

    async def _check(c: Dict[str, Any]) -> Optional[str]:
        slug = c.get("importyeti_slug") or c.get("importyetiSlug")
        async with sem:
            try:
                r = await check_company_contact(
                    slug=slug,
                    company_name=c.get("company_name") or c.get("companyName") or "",
                    website=c.get("website"),
                    city=c.get("city"),
                    state=c.get("state"),
                    country=c.get("country"),
                    validated_email=None,
                    validated_contact_name=None,
                    auth_token=auth_token,
                )
                return slug if r.get("has_contact") else None
            except Exception as e:
                logger.warning("apollo check %s FAILED: %s", slug, e)
                return None

    winners: List[str] = []
    attempted = 0
    for batch_start in range(0, len(untried), 50):
        if len(winners) >= target_topup:
            break
        batch = untried[batch_start:batch_start + 50]
        attempted += len(batch)
        results = await asyncio.gather(*[_check(c) for c in batch])
        hit = [s for s in results if s]
        winners.extend(hit)
        logger.info(
            "  batch %d: +%d winners (total %d, attempted %d)",
            batch_start // 50 + 1, len(hit), len(winners), attempted,
        )

    winners = winners[:target_topup]
    logger.info("apollo top-up: %d winners (attempted %d)", len(winners), attempted)
    if not winners:
        return {"attempted": attempted, "winners": 0, "pipeline_created": 0}

    async with pm.acquire(db_name) as conn:
        user = {"email": email, "db_name": db_name}
        pr = await add_slugs_to_pipeline(conn=conn, user=user, auth_token=auth_token, slugs=winners)
        created = pr.get("created", 0)
        errors = pr.get("errors", [])
        logger.info("pipeline populated: %d created, %d errors", created, len(errors))
        if errors:
            for err in errors[:5]:
                logger.warning("  error: %s", err)

    return {"attempted": attempted, "winners": len(winners), "pipeline_created": created}


async def phase_c_competitor_enrich(auth_token: str, email: str, db_name: str) -> int:
    from importyeti.competitors.service import BolCompetitorService
    from service_core.db import get_pool_manager

    pm = get_pool_manager()
    comp_service = BolCompetitorService()

    async with pm.acquire(db_name) as conn:
        ready, exhausted = await comp_service._deep_enrich_all_competitors(
            conn, auth_token, email, enrich_cap=1,
        )
    logger.info("competitor deep-enrich: %d ready (pool_exhausted=%s)", ready, exhausted)
    return ready


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--email", required=True, help="Tenant user email (for JWT sub)")
    p.add_argument("--db", required=True, help="Tenant DB name (e.g. prelude_foo)")
    p.add_argument("--products", nargs="+", default=[], help="Product strings for Apollo top-up search")
    p.add_argument("--failed-slugs", nargs="*", default=[], help="Buyer slugs to deep-enrich in Phase A")
    p.add_argument("--target-topup", type=int, default=24, help="Apollo top-up target lead count")
    p.add_argument("--max-candidates", type=int, default=500, help="Max cache candidates to pull for top-up")
    p.add_argument("--run-phase-a", action="store_true", help="Run Phase A (deep-enrich failed slugs)")
    p.add_argument("--run-phase-b", action="store_true", help="Run Phase B (Apollo top-up)")
    p.add_argument("--run-phase-c", action="store_true", help="Run Phase C (deep-enrich 1 competitor)")
    p.add_argument("--force-apollo", action="store_true", help="Force ENRICHMENT_PROVIDER=apollo for this run")
    return p.parse_args()


async def main() -> None:
    args = _parse_args()

    if not _DB_NAME_PATTERN.match(args.db):
        sys.exit(f"Invalid --db: {args.db} (must match ^prelude_[a-z0-9_]+$ or 'postgres')")

    if args.force_apollo:
        os.environ["ENRICHMENT_PROVIDER"] = "apollo"

    if args.run_phase_a and not args.failed_slugs:
        sys.exit("--run-phase-a requires --failed-slugs")
    if args.run_phase_b and not args.products:
        sys.exit("--run-phase-b requires --products")

    from service_core.db import init_pool_manager
    from service_core.pool import TenantPoolManager

    init_pool_manager(TenantPoolManager())
    await _verify_tenant_exists(args.email, args.db)
    token = _mint_token(args.email, args.db)

    if args.run_phase_a:
        print("\n" + "=" * 60)
        print(f"PHASE A — deep-enrich {len(args.failed_slugs)} buyer slugs")
        print("=" * 60)
        enriched = await phase_a_deep_enrich(token, args.failed_slugs)
        print(f"\n  Deep-enrich success: {enriched}/{len(args.failed_slugs)}")

    if args.run_phase_b:
        print("\n" + "=" * 60)
        print(f"PHASE B — Apollo top-up, target +{args.target_topup} leads, max_candidates={args.max_candidates}")
        print("=" * 60)
        summary = await phase_b_apollo_topup(
            token, email=args.email, db_name=args.db,
            products=args.products, target_topup=args.target_topup,
            max_candidates=args.max_candidates,
        )
        print(f"\n  Apollo top-up: attempted={summary['attempted']}, "
              f"winners={summary['winners']}, "
              f"pipeline_created={summary['pipeline_created']}")

    if args.run_phase_c:
        print("\n" + "=" * 60)
        print("PHASE C — deep-enrich 1 competitor")
        print("=" * 60)
        ready = await phase_c_competitor_enrich(token, args.email, args.db)
        print(f"\n  Competitor deep-enrich: {ready} ready")

    print("\nDONE.")


if __name__ == "__main__":
    asyncio.run(main())
