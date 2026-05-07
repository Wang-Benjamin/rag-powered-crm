"""Probe: measure Apollo hit rate on Perplexity-filtered PowerQuery 45.

Validates whether `PowerQuery 45 → Perplexity filter → pick 15 → Apollo`
produces enough Apollo hits to populate Page 2. Skips deep enrichment and
score computation (4.5 IY credits + ~$1 Apollo vs ~20 credits for full).

Usage:
    cd prelude/prelude-leadgen && uv run python scripts/probe_apollo_hit_rate.py <HS_CODE>

Example:
    uv run python scripts/probe_apollo_hit_rate.py 3924
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

from apollo_io.client import ApolloClient  # noqa: E402
from apollo_io.schemas import ApolloConfig  # noqa: E402

from importyeti.clients.api_client import ImportYetiClient  # noqa: E402
from importyeti.reports.contact_adapter import _fetch_one  # noqa: E402
from importyeti.reports.real_company_filter import classify_real_companies  # noqa: E402


def _build_buyer_dict(comp: Any, client: ImportYetiClient) -> Dict[str, Any]:
    """Shape a PowerQuery row into the minimal dict Perplexity + Apollo expect."""
    slug = client.extract_slug(comp.company_link or "") or ""
    address_list = (
        [kc.model_dump() for kc in comp.company_address]
        if comp.company_address
        else None
    )
    _, city, state = client.parse_address(address_list)
    return {
        "slug": slug,
        "name": comp.key or "",
        "city": city or "",
        "state": state or "",
        "matching_shipments": comp.doc_count or 0,
        "weight_kg": comp.weight or 0,
    }


async def probe(hs_code: str, category_hint: str) -> None:
    now = datetime.now(timezone.utc)
    fmt = "%m/%d/%Y"
    start_date = (now - timedelta(days=182)).strftime(fmt)
    end_date = now.strftime(fmt)

    filter_range = "1000 TO 2000"
    cache_path = f"/tmp/probe_pq_{hs_code}_{filter_range.replace(' TO ', '_').replace(' ', '_')}.json"

    print(f"\n=== Probe: HS {hs_code} / {category_hint} ===")
    print(f"PowerQuery window: {start_date} → {end_date}")
    print(f"Filter: company_total_shipments={filter_range}")
    print(f"Cache:  {cache_path}")

    # ── Step 1: PowerQuery 45 (cached → 0 IY credits, cold → 4.5) ───────
    if os.path.exists(cache_path):
        with open(cache_path) as f:
            buyers = json.load(f)
        print(f"\n[1/4] Loading PowerQuery from cache — 0 IY credits")
        print(f"       {len(buyers)} companies")
    else:
        client = ImportYetiClient()
        print("\n[1/4] PowerQuery 45 rows (4.5 IY credits) …")
        resp = await client.power_query_buyers(
            hs_code=f"{hs_code}*",
            start_date=start_date,
            end_date=end_date,
            page_size=45,
            supplier_country="china",
            company_total_shipments=filter_range,
        )
        raw_companies = resp.data.data if resp.data else []
        raw_companies.sort(key=lambda c: c.doc_count or 0, reverse=True)
        buyers = [_build_buyer_dict(c, client) for c in raw_companies]
        buyers = [b for b in buyers if b["slug"]]
        with open(cache_path, "w") as f:
            json.dump(buyers, f, indent=2)
        print(f"       got {len(buyers)} companies with slugs, cached to {cache_path}")
    for i, b in enumerate(buyers[:10]):
        print(f"         {i+1:2d}. {b['name'][:45]:45s}  {b['city']}, {b['state']}")
    if len(buyers) > 10:
        print(f"         … {len(buyers) - 10} more")

    # ── Step 2: Perplexity classify ─────────────────────────────────────
    print(f"\n[2/4] Perplexity classifier on {len(buyers)} companies …")
    verdicts = await classify_real_companies(buyers, hs_category=category_hint)
    real_count = sum(1 for v in verdicts.values() if v == "real")
    unclear_count = sum(1 for v in verdicts.values() if v == "unclear")
    shell_count = sum(1 for v in verdicts.values() if v == "likely_shell")
    print(f"       verdicts: {real_count} real, {unclear_count} unclear, {shell_count} likely_shell")

    # ── Step 3: Pick top 15 from survivors (drop likely_shell) ──────────
    survivors = [b for b in buyers if verdicts.get(b["slug"]) != "likely_shell"]
    top_15 = survivors[:15]
    print(f"\n[3/4] Top 15 after filter:")
    for i, b in enumerate(top_15):
        cls = verdicts.get(b["slug"], "—")
        print(f"  #{i+1:2d} {b['name'][:40]:40s}  {b['city'][:20]:20s}, {b['state']:3s}  matches={b['matching_shipments']:4d}  [{cls}]")

    # ── Step 4: Apollo on each of 15 ────────────────────────────────────
    api_key = os.getenv("APOLLO_API_KEY")
    if not api_key:
        print("\n[4/4] APOLLO_API_KEY not set — skipping Apollo step")
        return
    config = ApolloConfig(
        api_key=api_key,
        base_url=os.getenv("APOLLO_BASE_URL", "https://api.apollo.io"),
        timeout_seconds=int(os.getenv("APOLLO_TIMEOUT", "30")),
    )
    # Wider Apollo search: try all 15, stop at 3 found. Found 3 will be
    # promoted to the displayed top 3 (matches production Step 5b reorder).
    MAX_APOLLO_CHAINS = 15
    STOP_AT_FOUND = 3
    print(f"\n[4/4] Apollo: cap={MAX_APOLLO_CHAINS} chains, stop at {STOP_AT_FOUND} found")
    found = 0
    failed = 0
    not_found = 0
    chains_run = 0
    details: List[Dict[str, Any]] = []
    async with ApolloClient(config) as apollo:
        for b in top_15:
            if found >= STOP_AT_FOUND:
                print(f"       → stopped: hit {STOP_AT_FOUND} found at chain #{chains_run}")
                break
            if chains_run >= MAX_APOLLO_CHAINS:
                print(f"       → stopped: hit {MAX_APOLLO_CHAINS}-chain cap")
                break
            chains_run += 1
            result = await _fetch_one(b, apollo, auth_token="")
            if result.fetch_status == "found":
                found += 1
            elif result.fetch_status == "failed":
                failed += 1
            else:
                not_found += 1
            details.append({
                "name": b["name"],
                "slug": b["slug"],
                "class": verdicts.get(b["slug"], "—"),
                "status": result.fetch_status,
                "contact": result.contact_name,
                "title": result.contact_title,
                "email": result.contact_email,
            })

    # Reorder details: found first (matches Step 5b behavior on Page 1),
    # then not_found / failed, preserving raw order within each group.
    found_details = [d for d in details if d["status"] == "found"]
    other_details = [d for d in details if d["status"] != "found"]
    details = found_details + other_details

    print("\n=== RESULTS ===")
    print(f"Apollo found:     {found}/{chains_run} (cap={MAX_APOLLO_CHAINS})")
    print(f"Apollo not_found: {not_found}/{chains_run}")
    print(f"Apollo failed:    {failed}/{chains_run}")
    print()
    for d in details:
        mark = "✓" if d["status"] == "found" else " "
        contact_str = (
            f"  {d['contact']} | {d['title']} | {d['email']}"
            if d["status"] == "found"
            else ""
        )
        print(f" {mark} [{d['class']:12s}] {d['name'][:38]:38s}  {d['status']:10s}{contact_str}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: probe_apollo_hit_rate.py <HS_CODE> [<category_hint>]")
        sys.exit(1)
    hs = sys.argv[1]
    cat = sys.argv[2] if len(sys.argv) > 2 else f"HS {hs}"
    asyncio.run(probe(hs, cat))
