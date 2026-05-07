from __future__ import annotations

import ast
import asyncio
from pathlib import Path

from routers.crm_sync_router import router as crm_sync_router
from routers.importyeti_router import router as importyeti_router
from routers.two_pager_router import router as two_pager_router
from importyeti.reports.two_pager_models import TwoPagerBatchResponse, TwoPagerResponse


def _route_map(router):
    return {
        route.path: {
            "methods": sorted(route.methods),
            "name": route.name,
            "response_model": getattr(route, "response_model", None),
        }
        for route in router.routes
    }


def _mounted_router_aliases() -> set[str]:
    main_path = Path(__file__).resolve().parents[2] / "main.py"
    module = ast.parse(main_path.read_text())

    mounted: set[str] = set()
    for node in ast.walk(module):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "include_router":
            continue
        if not isinstance(node.func.value, ast.Name) or node.func.value.id != "app":
            continue
        if node.args and isinstance(node.args[0], ast.Name):
            mounted.add(node.args[0].id)

    return mounted


def test_importyeti_router_contract_inventory() -> None:
    routes = _route_map(importyeti_router)
    expected = {
        "/importyeti/subscription": ("GET", "get_subscription"),
        "/importyeti/trial-stats": ("GET", "get_trial_stats"),
        "/importyeti/enrichment-status": ("GET", "get_enrichment_status"),
        "/importyeti/search": ("POST", "search_buyers"),
        "/importyeti/onboarding/csv-kickoff": ("POST", "csv_onboarding_kickoff"),
        "/importyeti/add-to-pipeline": ("POST", "add_to_pipeline"),
        "/importyeti/competitors": ("GET", "get_competitors"),
        "/importyeti/competitor/{slug}": ("GET", "get_competitor_detail"),
        "/importyeti/competitor/{slug}/track": ("POST", "track_competitor"),
        "/importyeti/buyer/{lead_id}/competitors": ("GET", "get_buyer_competitor_exposure"),
    }
    assert set(routes) == set(expected)
    for path, (method, name) in expected.items():
        assert routes[path]["methods"] == [method]
        assert routes[path]["name"] == name


def test_two_pager_router_contract_inventory() -> None:
    routes = _route_map(two_pager_router)
    # /demo-fill was removed 2026-04-25 — auto-synth runs server-side inside
    # the main /two-pager response now, so no separate fill endpoint exists.
    assert set(routes) == {
        "/importyeti/two-pager",
        "/importyeti/two-pager/batch",
    }

    single = routes["/importyeti/two-pager"]
    assert single["methods"] == ["POST"]
    assert single["name"] == "generate_two_pager"
    assert single["response_model"] is TwoPagerResponse

    batch = routes["/importyeti/two-pager/batch"]
    assert batch["methods"] == ["POST"]
    assert batch["name"] == "generate_two_pager_batch"
    assert batch["response_model"] is TwoPagerBatchResponse


def test_crm_sync_router_contract_inventory() -> None:
    routes = _route_map(crm_sync_router)
    expected = {
        "/{lead_id}/add-to-crm": ("POST", "add_lead_to_crm"),
        "/bulk-add-to-crm": ("POST", "bulk_add_to_crm"),
    }
    assert set(routes) == set(expected)
    for path, (method, name) in expected.items():
        assert routes[path]["methods"] == [method]
        assert routes[path]["name"] == name


def test_main_mounts_crm_router_without_ai_router() -> None:
    mounted = _mounted_router_aliases()
    assert "crm_sync_router" in mounted
    assert "leads_ai_router" not in mounted


# --- Response-payload contract for the buyer competitor exposure endpoint -----
# Frontend (BuyerCompetitorExposure.tsx) depends on per-row `buyer_teu` and
# `buyer_share_pct`. A regression that drops or renames them would silently
# blank the overlap bar — pin the shape here.


class _FakeAsyncpgConn:
    """Minimal asyncpg-lookalike with canned fetchrow / fetch responses."""

    def __init__(self, lead_row, competitor_rows) -> None:
        self._lead_row = lead_row
        self._competitor_rows = competitor_rows

    async def fetchrow(self, *_args, **_kwargs):
        return self._lead_row

    async def fetch(self, *_args, **_kwargs):
        return self._competitor_rows


def test_buyer_competitor_exposure_returns_buyer_share_fields(monkeypatch) -> None:
    """Locks the response row shape: every competitor carries buyer_teu + buyer_share_pct."""
    from routers import importyeti_competitors_router as router_mod

    fake_lead = {"lead_id": "11111111-1111-1111-1111-111111111111", "company": "Acme Buyer"}
    # Matched row gets populated values; unmatched row is the default COALESCE(0) path.
    fake_rows = [
        {
            "supplier_slug": "dongguan-shengrong",
            "supplier_name": "Dongguan Shengrong Silicone",
            "threat_level": "HIGH",
            "threat_score": 92,
            "trend_yoy": 12.4,
            "matching_shipments": 1190,
            "is_tracked": True,
            "buyer_teu": 1190.0,
            "buyer_share_pct": 41.92,
        },
        {
            "supplier_slug": "unmatched-co",
            "supplier_name": "Unmatched Co",
            "threat_level": "LOW",
            "threat_score": 5,
            "trend_yoy": None,
            "matching_shipments": 3,
            "is_tracked": False,
            "buyer_teu": 0.0,
            "buyer_share_pct": 0.0,
        },
    ]
    tenant = (_FakeAsyncpgConn(fake_lead, fake_rows), {"email": "tester@prelude.com"})

    async def fake_sub_info(*_a, **_k):
        return {"entitlements": {"competitors": {"visible_limit": -1}}}

    monkeypatch.setattr(router_mod, "get_subscription_info", fake_sub_info)

    response = asyncio.run(
        router_mod.get_buyer_competitor_exposure(
            lead_id="11111111-1111-1111-1111-111111111111",
            tenant=tenant,
            authorization=None,
        )
    )

    assert response["total"] == 2
    matched, unmatched = response["competitors"]
    # Frontend-locked keys: must always be present on every row.
    for row in response["competitors"]:
        assert "buyer_teu" in row
        assert "buyer_share_pct" in row
    assert matched["buyer_teu"] == 1190.0
    assert matched["buyer_share_pct"] == 41.92
    assert unmatched["buyer_teu"] == 0.0
    assert unmatched["buyer_share_pct"] == 0.0
