"""T03: Buyer deep-enrich end-to-end.

Exercises BolSearchService.enrich_company(slug, auth_token) with:
  1. Fixture gate on api_client.get_company_detail — resolves
     deep_enrich_<slug>.json under IMPORTYETI_FIXTURE_DIR.
  2. Real scoring pipeline (compute_full_score) against fixture data.
  3. DB write via monkey-patched internal_bol_client.update_enrichment
     that mirrors the /bol/enrich/{slug} HTTP handler as a direct
     psycopg2 UPDATE against prelude_lead_db_dev.

Avoids needing the 8007 server up. Scoped to pre-brief assertions —
ai_action_brief and the two-pager renderer are out of this flow.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import pytest


# Path setup for leadgen + shared packages lives in tests/fixture/conftest.py.


# Derive the fixture corpus path relative to the repo root (four levels
# above this file: tests/fixture/ → prelude-leadgen/ → prelude/ → repo).
# Overridable via LEADGEN_FIXTURE_CORPUS_DIR for non-standard layouts.
FIXTURE_SRC = Path(
    os.environ.get("LEADGEN_FIXTURE_CORPUS_DIR")
    or (Path(__file__).resolve().parents[4] / "tests" / "companies_raw")
)


@pytest.fixture
def prefixed_fixture_dir(tmp_path: Path, fxt_prefix: str) -> Path:
    """Copy the companies_raw fixtures into a tmp dir, renaming each
    `deep_enrich_<slug>.json` to `deep_enrich_<FXT_T##_>{slug}.json`
    so the fixture gate can resolve FXT-prefixed slugs.
    """
    for src in FIXTURE_SRC.iterdir():
        if src.name.startswith("deep_enrich_"):
            new_name = src.name.replace("deep_enrich_", f"deep_enrich_{fxt_prefix}")
        else:
            new_name = src.name  # powerquery_sample_raw.json, etc.
        shutil.copy(src, tmp_path / new_name)
    return tmp_path


@pytest.fixture
def importyeti_fixture_env(prefixed_fixture_dir: Path):
    prev = os.environ.get("IMPORTYETI_FIXTURE_DIR")
    os.environ["IMPORTYETI_FIXTURE_DIR"] = str(prefixed_fixture_dir)
    try:
        yield str(prefixed_fixture_dir)
    finally:
        if prev is None:
            os.environ.pop("IMPORTYETI_FIXTURE_DIR", None)
        else:
            os.environ["IMPORTYETI_FIXTURE_DIR"] = prev


def _seed_buyer_raw(dev_sync_conn, slug: str, *, hs_code: str = "940540") -> None:
    """Seed a minimal bol_companies row for enrich_company to read."""
    from psycopg2.extras import Json

    with dev_sync_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO bol_companies (
                importyeti_slug, company_name, company_total_shipments,
                country, hs_codes, hs_metrics, enrichment_status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (importyeti_slug) DO UPDATE SET
                company_name = EXCLUDED.company_name,
                hs_metrics = EXCLUDED.hs_metrics
            """,
            (
                slug,
                slug,
                11401,
                "USA",
                [hs_code],
                Json({hs_code: {
                    "matching_shipments": 2526,
                    "weight_kg": 24192651,
                    "teu": 3928,
                    "quick_score": 60,
                }}),
                "pending",
            ),
        )


def _fetch_company(dev_sync_conn, slug: str) -> Dict[str, Any]:
    """Read a buyer row as a dict (cast rows to normal dicts for clarity)."""
    with dev_sync_conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM bol_companies WHERE importyeti_slug = %s", (slug,),
        )
        colnames = [d.name for d in cur.description]
        row = cur.fetchone()
    return dict(zip(colnames, row)) if row else {}


def _make_fake_get_company(dev_sync_conn):
    """Build an async replacement for internal_bol_client.get_company that
    reads directly from dev DB + flattens the best hs_metrics entry onto
    top-level fields (mirrors server-side _flatten_best_hs).
    """
    async def _get_company(slug: str, auth_token: str = "") -> Optional[Dict[str, Any]]:
        row = _fetch_company(dev_sync_conn, slug)
        if not row:
            return None
        hs_metrics = row.get("hs_metrics") or {}
        if isinstance(hs_metrics, str):
            hs_metrics = json.loads(hs_metrics)
        if hs_metrics:
            best = max(
                hs_metrics.keys(),
                key=lambda k: (hs_metrics[k] or {}).get("quick_score") or 0,
            )
            entry = hs_metrics[best] or {}
            row["hs_code"] = best
            row["matching_shipments"] = entry.get("matching_shipments")
            row["weight_kg"] = entry.get("weight_kg")
            row["teu"] = entry.get("teu")
            row["quick_score"] = entry.get("quick_score")
        return row

    return _get_company


def _make_fake_update_enrichment(dev_sync_conn):
    """Build an async update_enrichment that mirrors what the 8007 handler
    does: write every field BolSearchService.enrich_company puts on the
    enrichment payload — time_series, supplier_breakdown, recent_bols,
    also_known_names, phone_number, website, most_recent_shipment,
    scoring_signals, enriched_score, enrichment_status, derived_* — via
    a single UPDATE. Captures the payload for assertion too.
    """
    captured: Dict[str, Any] = {}

    async def _update(slug: str, data: Dict[str, Any], auth_token: str = "") -> bool:
        from psycopg2.extras import Json

        captured["slug"] = slug
        captured["data"] = dict(data)
        with dev_sync_conn.cursor() as cur:
            cur.execute(
                """
                UPDATE bol_companies SET
                    time_series = COALESCE(%s, time_series),
                    supplier_breakdown = COALESCE(%s, supplier_breakdown),
                    recent_bols = COALESCE(%s, recent_bols),
                    also_known_names = COALESCE(%s, also_known_names),
                    phone_number = COALESCE(%s, phone_number),
                    website = COALESCE(%s, website),
                    most_recent_shipment = COALESCE(%s, most_recent_shipment),
                    scoring_signals = COALESCE(%s, scoring_signals),
                    enriched_score = COALESCE(%s, enriched_score),
                    enrichment_status = COALESCE(%s, enrichment_status),
                    derived_china_concentration = COALESCE(%s, derived_china_concentration),
                    derived_growth_12m_pct = COALESCE(%s, derived_growth_12m_pct),
                    derived_china_concentration_12m = COALESCE(%s, derived_china_concentration_12m),
                    last_updated_at = NOW()
                WHERE importyeti_slug = %s
                """,
                (
                    Json(data["time_series"]) if data.get("time_series") else None,
                    Json(data["supplier_breakdown"]) if data.get("supplier_breakdown") else None,
                    Json(data["recent_bols"]) if data.get("recent_bols") else None,
                    data.get("also_known_names"),
                    data.get("phone_number"),
                    data.get("website"),
                    data.get("most_recent_shipment"),
                    Json(data["scoring_signals"]) if data.get("scoring_signals") else None,
                    data.get("enriched_score"),
                    data.get("enrichment_status"),
                    data.get("derived_china_concentration"),
                    data.get("derived_growth_12m_pct"),
                    data.get("derived_china_concentration_12m"),
                    slug,
                ),
            )
        return True

    _update.captured = captured  # type: ignore[attr-defined]
    return _update


@pytest.mark.asyncio
async def test_t03_buyer_deep_enrich_end_to_end(
    cleanup_fxt, dev_sync_conn, importyeti_fixture_env, monkeypatch,
):
    slug = f"{cleanup_fxt}satco-products"  # matches deep_enrich_FXT_T03_satco-products.json

    _seed_buyer_raw(dev_sync_conn, slug)

    from importyeti.clients import internal_bol_client

    monkeypatch.setattr(
        internal_bol_client, "get_company", _make_fake_get_company(dev_sync_conn),
    )
    fake_update = _make_fake_update_enrichment(dev_sync_conn)
    monkeypatch.setattr(internal_bol_client, "update_enrichment", fake_update)

    async def _noop_log(*args, **kwargs):
        return None
    monkeypatch.setattr(internal_bol_client, "log_api_call", _noop_log)

    from importyeti.buyers.service import BolSearchService

    result = await BolSearchService().enrich_company(slug=slug, auth_token="dummy")

    # Assert the return payload — enrich_company composes a merged dict.
    assert result["enrichment_status"] == "detail_enriched"
    assert isinstance(result.get("enriched_score"), (int, float))
    assert result.get("enriched_score") is not None
    assert isinstance(result.get("scoring_signals"), dict)
    assert "reorderWindow" in result["scoring_signals"]

    # Assert the payload BolSearchService.enrich_company sent to
    # update_enrichment carries every migration-relevant field — proves
    # the fake writer mirrors the real contract and that the service
    # didn't silently drop a field.
    captured = fake_update.captured["data"]  # type: ignore[attr-defined]
    for field in (
        "time_series", "supplier_breakdown", "recent_bols",
        "most_recent_shipment", "scoring_signals", "enriched_score",
        "enrichment_status",
    ):
        assert captured.get(field) is not None, f"enrich payload missing {field}: {captured.keys()}"

    # Assert DB state persisted via the monkey-patched update path.
    row = _fetch_company(dev_sync_conn, slug)
    assert row["enrichment_status"] == "detail_enriched", row
    assert row["enriched_score"] is not None, "enriched_score not written"
    assert row["time_series"] is not None, "time_series JSONB not written"
    assert row["recent_bols"] is not None, "recent_bols JSONB not written"
    assert row["supplier_breakdown"] is not None, "supplier_breakdown JSONB not written"
    assert row["scoring_signals"] is not None, "scoring_signals JSONB not written"
    assert row["most_recent_shipment"] is not None, "most_recent_shipment not written"

    # Fixture asserted: sample_raw has time_series + suppliers_table for Satco.
    # Coerce JSONB to Python types (psycopg2 default: dicts/lists on JSONB).
    ts = row["time_series"]
    if isinstance(ts, str):
        ts = json.loads(ts)
    assert isinstance(ts, (dict, list)), f"time_series shape: {type(ts)}"
