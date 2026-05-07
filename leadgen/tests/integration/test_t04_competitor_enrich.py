"""T04: Competitor deep-enrich — fixture gate + JSONB write.

The full BolCompetitorService._deep_enrich_all_competitors + lazy-enrich
paths both tangle with per-tenant `bol_competitors` writes and Perplexity
Chinese-name lookups. For the BoL Schema Consolidation migration what
matters is the `bol_competitor_companies` (shared internal-leads-db
cache) path:
  client.get_supplier_detail (fixture gate)
  → internal_bol_client.update_competitor_enrichment
  → BolCompetitorRepository.update_enrichment (JSONB write).

T04 drives this core path directly. The per-tenant competitor write +
Chinese-name resolution + overlap recompute are out of scope.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict

import pytest


# Derive relative to repo root, overridable via env var. Same pattern as T03.
FIXTURE_SRC = Path(
    os.environ.get("LEADGEN_COMPETITOR_FIXTURE_DIR")
    or (Path(__file__).resolve().parents[4] / "tests" / "competitors_raw")
)


@pytest.fixture
def prefixed_competitor_fixture_dir(tmp_path: Path, fxt_prefix: str) -> Path:
    """Stage competitor_enrich_*.json with an FXT_T## prefix so
    `get_supplier_detail('FXT_T04_l-tech')` resolves the fixture.
    """
    for src in FIXTURE_SRC.iterdir():
        if src.name.startswith("competitor_enrich_"):
            new_name = src.name.replace(
                "competitor_enrich_", f"competitor_enrich_{fxt_prefix}",
            )
        else:
            new_name = src.name  # competitors_raw.json, etc.
        shutil.copy(src, tmp_path / new_name)
    return tmp_path


@pytest.fixture
def importyeti_fixture_env(prefixed_competitor_fixture_dir: Path):
    prev = os.environ.get("IMPORTYETI_FIXTURE_DIR")
    os.environ["IMPORTYETI_FIXTURE_DIR"] = str(prefixed_competitor_fixture_dir)
    try:
        yield str(prefixed_competitor_fixture_dir)
    finally:
        if prev is None:
            os.environ.pop("IMPORTYETI_FIXTURE_DIR", None)
        else:
            os.environ["IMPORTYETI_FIXTURE_DIR"] = prev


def _seed_competitor_raw(dev_sync_conn, slug: str, *, hs_code: str = "940540") -> None:
    from psycopg2.extras import Json
    with dev_sync_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO bol_competitor_companies (
                importyeti_slug, supplier_name, country, country_code,
                hs_codes, hs_metrics, enrichment_status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (importyeti_slug) DO UPDATE SET
                supplier_name = EXCLUDED.supplier_name,
                hs_metrics = EXCLUDED.hs_metrics
            """,
            (
                slug,
                slug,
                "China",
                "CN",
                [hs_code],
                Json({hs_code: {"matching_shipments": 120, "weight_kg": 50000}}),
                "pending",
            ),
        )


def _fetch_competitor(dev_sync_conn, slug: str) -> Dict[str, Any]:
    with dev_sync_conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM bol_competitor_companies WHERE importyeti_slug = %s",
            (slug,),
        )
        cols = [d.name for d in cur.description]
        row = cur.fetchone()
    return dict(zip(cols, row)) if row else {}


@pytest.mark.asyncio
async def test_t04_competitor_deep_enrich(
    cleanup_fxt, dev_sync_conn, importyeti_fixture_env,
):
    slug = f"{cleanup_fxt}l-tech"  # fixture → competitor_enrich_FXT_T04_l-tech.json

    _seed_competitor_raw(dev_sync_conn, slug)

    # Exercise the fixture gate directly.
    from importyeti.clients.api_client import ImportYetiClient
    client = ImportYetiClient()
    detail = await client.get_supplier_detail(slug)

    # Raw fixture is a flat dict; api_client wraps it as {"data": {...}}.
    assert isinstance(detail, dict)
    raw = detail.get("data") if isinstance(detail.get("data"), dict) else detail
    assert raw, f"fixture returned empty data for {slug}: {detail!r}"

    # The fixture must expose the fields the plan asserts on.
    assert raw.get("companies_table") is not None, "fixture missing companies_table"
    assert raw.get("time_series") is not None, "fixture missing time_series"
    assert raw.get("recent_bols") is not None, "fixture missing recent_bols"

    # Simulate the service layer's write. We inline the UPDATE rather
    # than importing BolCompetitorRepository from the other repo — both
    # repos have a `config.settings` module with different contents, and
    # leadgen's conftest has already bound that package in sys.path. The
    # SQL below mirrors BolCompetitorRepository.update_enrichment
    # (detail_enriched branch).
    from psycopg2.extras import Json

    time_series = raw.get("time_series")
    companies_table = raw.get("companies_table")
    recent_bols = raw.get("recent_bols")
    carriers_per_country = raw.get("carriers_per_country")
    also_known_names = raw.get("also_known_names")
    supplier_name_cn = "测试光电公司"  # canned; bypasses Perplexity

    # Mirror BolCompetitorRepository.update_enrichment (detail_enriched
    # branch in competitors/service.py). trend_yoy is part of the real
    # contract alongside time_series / companies_table / recent_bols —
    # compute + pass it so the test doesn't silently lose that coverage.
    trend_yoy = None
    if isinstance(time_series, dict) and time_series:
        from importyeti.domain.transformers import compute_supplier_company_yoy
        yoy = compute_supplier_company_yoy(time_series)
        if yoy is not None:
            trend_yoy = round(yoy * 100, 1)

    with dev_sync_conn.cursor() as cur:
        cur.execute(
            """
            UPDATE bol_competitor_companies SET
                supplier_name_cn = COALESCE(%s, supplier_name_cn),
                also_known_names = COALESCE(%s, also_known_names),
                time_series = COALESCE(%s, time_series),
                trend_yoy = COALESCE(%s, trend_yoy),
                companies_table = COALESCE(%s, companies_table),
                recent_bols = COALESCE(%s, recent_bols),
                carriers_per_country = COALESCE(%s, carriers_per_country),
                enrichment_status = %s,
                enriched_at = NOW(),
                last_updated_at = NOW()
            WHERE importyeti_slug = %s
            """,
            (
                supplier_name_cn,
                also_known_names,
                Json(time_series) if time_series else None,
                trend_yoy,
                Json(companies_table) if companies_table else None,
                Json(recent_bols) if recent_bols else None,
                Json(carriers_per_country) if carriers_per_country else None,
                "detail_enriched",
                slug,
            ),
        )

    # Assert DB persisted
    row = _fetch_competitor(dev_sync_conn, slug)
    assert row["enrichment_status"] == "detail_enriched", row
    assert row["time_series"] is not None, "time_series JSONB not written"
    assert row["companies_table"] is not None, "companies_table JSONB not written"
    assert row["recent_bols"] is not None, "recent_bols JSONB not written"
    assert row["supplier_name_cn"] == "测试光电公司"
