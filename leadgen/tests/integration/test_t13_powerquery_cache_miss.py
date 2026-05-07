"""T13 (scoped): PowerQuery cache-miss → save_to_cache → hs_metrics.

The plan originally called for BolSearchService().search_companies with
cache_only=False to trigger a live PowerQuery fetch, but that code path
is purely cache-serving today — the live PowerQuery + save_to_cache
flow lives in the two-pager source at importyeti/reports/sources.py:
`fetch_buyers_api`. T13 drives that function directly with the fixture
gate on client.power_query_buyers and a monkey-patched
internal_bol_client.save_to_cache that writes straight to
prelude_lead_db_dev via psycopg2 + merge_hs_metrics_buyer.

Asserts: the 8 fixture companies from powerquery_sample_raw.json land
in bol_companies with hs_metrics['940540'] populated. Downstream
two-pager PDF rendering, Apollo contact enrichment, and Anthropic
brief generation are explicitly out of scope.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List

import pytest
from psycopg2.extras import Json


# Relative to repo root; overridable via LEADGEN_FIXTURE_CORPUS_DIR.
FIXTURE_SRC = Path(
    os.environ.get("LEADGEN_FIXTURE_CORPUS_DIR")
    or (Path(__file__).resolve().parents[4] / "tests" / "companies_raw")
)


@pytest.fixture
def prefixed_powerquery_dir(tmp_path: Path, fxt_prefix: str) -> Path:
    """Stage a fixture dir with an FXT-prefixed powerquery_sample_raw.json.

    Rewrites every company_link so slugs in the parsed fixture land
    as FXT_T13_<slug> when fetch_buyers_api extracts them.
    """
    with open(FIXTURE_SRC / "powerquery_sample_raw.json") as f:
        raw = json.load(f)

    prefixed: List[Dict[str, Any]] = []
    for entry in raw:
        copy = dict(entry)
        link = copy.get("company_link") or ""
        if "/company/" in link:
            head, _, tail = link.partition("/company/")
            slug = tail.strip("/").split("/")[0].split("?")[0]
            copy["company_link"] = f"{head}/company/{fxt_prefix}{slug}"
        prefixed.append(copy)

    (tmp_path / "powerquery_sample_raw.json").write_text(json.dumps(prefixed))
    return tmp_path


@pytest.fixture
def importyeti_fixture_env(prefixed_powerquery_dir: Path):
    prev = os.environ.get("IMPORTYETI_FIXTURE_DIR")
    os.environ["IMPORTYETI_FIXTURE_DIR"] = str(prefixed_powerquery_dir)
    try:
        yield str(prefixed_powerquery_dir)
    finally:
        if prev is None:
            os.environ.pop("IMPORTYETI_FIXTURE_DIR", None)
        else:
            os.environ["IMPORTYETI_FIXTURE_DIR"] = prev


def _fake_save_to_cache_factory(dev_sync_conn):
    """Return an async replacement for internal_bol_client.save_to_cache
    that mirrors the 8007 /bol/cache handler + BolService.save_to_cache
    with a single INSERT ... ON CONFLICT ... DO UPDATE using
    merge_hs_metrics_buyer SQL helper.
    """
    async def _save(
        companies: List[Dict[str, Any]],
        search_results: List[Dict[str, Any]],
        auth_token: str = "",
    ) -> bool:
        # Mirror the real contract: return False if the caller's company
        # list is empty (would be a degenerate write) so the test won't
        # silently pass on an upstream parse failure.
        if not companies:
            return False
        # Group search_results by slug → {hs_code: {metric fields}}
        slug_metrics: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for sr in search_results:
            slug = sr.get("importyeti_slug")
            hs = sr.get("hs_code")
            if not slug or not hs:
                continue
            entry: Dict[str, Any] = {}
            for field in ("matching_shipments", "weight_kg", "teu", "quick_score"):
                if sr.get(field) is not None:
                    entry[field] = sr[field]
            slug_metrics.setdefault(slug, {})[hs] = entry

        with dev_sync_conn.cursor() as cur:
            for c in companies:
                slug = c.get("importyeti_slug")
                if not slug:
                    continue
                hs_metrics = slug_metrics.get(slug, {})
                cur.execute(
                    """
                    INSERT INTO bol_companies (
                        importyeti_slug, company_name, company_total_shipments,
                        address, city, state, country, hs_metrics,
                        enrichment_status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (importyeti_slug) DO UPDATE SET
                        company_name = EXCLUDED.company_name,
                        company_total_shipments = COALESCE(
                            EXCLUDED.company_total_shipments,
                            bol_companies.company_total_shipments
                        ),
                        hs_metrics = merge_hs_metrics_buyer(
                            COALESCE(bol_companies.hs_metrics, '{}'::jsonb),
                            COALESCE(EXCLUDED.hs_metrics, '{}'::jsonb)
                        ),
                        last_updated_at = NOW()
                    """,
                    (
                        slug,
                        c.get("company_name") or slug,
                        c.get("company_total_shipments"),
                        c.get("address"),
                        c.get("city"),
                        c.get("state"),
                        c.get("country", "USA"),
                        Json(hs_metrics),
                        c.get("enrichment_status", "pending"),
                    ),
                )
        return True

    return _save


@pytest.mark.asyncio
async def test_t13_powerquery_cache_miss(
    cleanup_fxt, dev_sync_conn, importyeti_fixture_env, monkeypatch,
):
    # Fresh start: every FXT_T13_ row gone (cleanup_fxt did DELETE at setup).
    with dev_sync_conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM bol_companies WHERE importyeti_slug LIKE %s",
            (f"{cleanup_fxt}%",),
        )
        pre_count = cur.fetchone()[0]
    assert pre_count == 0, f"stale FXT_T13_ rows at start: {pre_count}"

    from importyeti.clients import api_client as api_client_module
    from importyeti.clients import internal_bol_client

    monkeypatch.setattr(
        internal_bol_client, "save_to_cache",
        _fake_save_to_cache_factory(dev_sync_conn),
    )

    # sources.fetch_buyers_api is the PowerQuery → cache write path that
    # lives in the two-pager source. It calls client.power_query_buyers
    # (fixture-gated) then write_buyer_cache_batch → save_to_cache.
    from importyeti.reports.sources import fetch_buyers_api

    client = api_client_module.ImportYetiClient()
    logger = logging.getLogger("t13")
    result = await fetch_buyers_api(
        client=client, hs_code="940540", auth_token="dummy", logger=logger,
    )

    assert result["from_cache"] is False, result
    assert result["total_companies"] is not None
    assert len(result["companies"]) > 0, result

    # Verify DB state: every company from the PowerQuery fixture must
    # land with hs_metrics['940540'] populated. powerquery_sample_raw.json
    # has 9 unique companies — anything less means the parse or the
    # save_to_cache write silently dropped a row.
    fixture_json = Path(importyeti_fixture_env) / "powerquery_sample_raw.json"
    with open(fixture_json) as f:
        fixture_unique_slugs = {
            (entry.get("company_link") or "").rstrip("/").split("/")[-1]
            for entry in json.load(f)
            if entry.get("company_link")
        }
    assert fixture_unique_slugs, "fixture had no resolvable company_link slugs"

    with dev_sync_conn.cursor() as cur:
        cur.execute(
            "SELECT importyeti_slug, hs_metrics FROM bol_companies "
            "WHERE importyeti_slug LIKE %s",
            (f"{cleanup_fxt}%",),
        )
        rows = cur.fetchall()

    assert len(rows) == len(fixture_unique_slugs), (
        f"expected {len(fixture_unique_slugs)} FXT_T13_ rows "
        f"(one per fixture company), got {len(rows)}"
    )
    observed_slugs = {row[0] for row in rows}
    assert observed_slugs == fixture_unique_slugs, (
        f"slug mismatch: fixture {fixture_unique_slugs} vs DB {observed_slugs}"
    )

    for slug, hs_metrics in rows:
        if isinstance(hs_metrics, str):
            hs_metrics = json.loads(hs_metrics)
        assert "940540" in hs_metrics, f"{slug} missing hs_metrics['940540']: {hs_metrics}"
        entry = hs_metrics["940540"]
        # matching_shipments always populated from PowerQuery doc_count;
        # weight/teu may be None for some companies in the fixture.
        assert entry.get("matching_shipments") is not None, entry
