"""Smoke tests for the two-pager dual-search feature.

All external API calls (ImportYeti, Apollo, Lemlist, Perplexity, Anthropic LLM)
are mocked. Zero network calls during this test run.

TDD note: tests were written before verifying each path — some may expose real
implementation bugs, which are reported rather than silently fixed.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Path bootstrap (mirrors conftest.py) ─────────────────────────────────────
ROOT = Path(__file__).resolve().parents[4]
LEADGEN_ROOT = ROOT / "prelude" / "prelude-leadgen"
SHARED_ROOT = ROOT / "prelude" / "prelude-shared"

for _entry in (LEADGEN_ROOT, SHARED_ROOT):
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))

# ── Shared test fixtures ──────────────────────────────────────────────────────

def _make_canned_buyer(index: int, slug: str | None = None) -> Dict[str, Any]:
    """Build a minimal buyer dict that satisfies every field access in the service."""
    s = slug or f"acme-furniture-{index}"
    return {
        "importyeti_slug": s,
        "company_name": f"Acme Furniture Co {index}",
        "address": f"100 Main St, Springfield, IL 62701",
        "city": "Springfield",
        "state": "IL",
        "country": "USA",
        "weight_kg": 50_000 + index * 1000,
        "matching_shipments": 150 + index * 10,
        "teu": 200,
        "most_recent_shipment": "01/15/2024",
        "hs_codes": ["940540"],
        "hs_metrics": {
            "940540": {
                "matching_shipments": 150,
                "weight_kg": 50_000,
                "quick_score": 75,
            }
        },
        "supplier_breakdown": [
            {
                "slug": f"supplier-{index}",
                "supplier_name": f"Supplier {index}",
                "country": "CN",
                "supplier_address_country": "CN",
                "weight_kg": 45_000,
                "shipments_12m": 80,
                "shipments_12_24m": 70,
                "weight_12m": 45_000,
            }
        ],
        "time_series": {},
        "validated_email": None,
        "validated_contact_name": None,
        "validated_contact_title": None,
    }


CANNED_BUYERS_3 = [_make_canned_buyer(i, slug) for i, slug in enumerate(
    ["acme-furniture-0", "acme-furniture-1", "acme-furniture-2"]
)]


def _noop_classify_low_value(companies):
    """Passthrough: nothing is hard- or soft-blocked."""
    return {"hard": set(), "soft": set()}


# ── Helper: build a fake power_query_buyers response that returns nothing ─────

def _empty_pq_response():
    """Minimal PowerQueryCompaniesResponse-shaped mock with no companies."""
    mock = MagicMock()
    mock.data = MagicMock()
    mock.data.totalCompanies = 0
    mock.data.data = []
    return mock


# =============================================================================
# Test 1: generate_report in HS-only mode
# =============================================================================

@pytest.mark.asyncio
async def test_generate_report_hs_only_mode():
    """generate_report with hs_code only succeeds and returns TwoPagerResponse."""
    # Ensure no API key so _fetch_apollo_contacts short-circuits immediately
    env_patch = {
        "LEMLIST_API_KEY": "",
        "APOLLO_API_KEY": "",
        "REAL_COMPANY_FILTER_SHADOW": "true",  # shadow mode: keep all survivors
    }

    with (
        patch.dict(os.environ, env_patch, clear=False),
        patch(
            "importyeti.clients.internal_bol_client.search_cache",
            new=AsyncMock(return_value=CANNED_BUYERS_3),
        ),
        patch(
            "importyeti.clients.internal_bol_client.save_to_cache",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "importyeti.reports.email_generator.classify_low_value_buyers",
            new=AsyncMock(side_effect=_noop_classify_low_value),
        ),
        patch(
            "importyeti.reports.real_company_filter.classify_real_companies",
            new=AsyncMock(return_value={}),
        ),
        patch(
            "importyeti.reports.email_generator.normalize_and_fabricate_buyer_fields",
            new=AsyncMock(return_value={}),
        ),
        patch(
            "importyeti.reports.email_generator.generate_outreach_emails",
            new=AsyncMock(return_value={}),
        ),
        patch(
            "importyeti.reports.two_pager_service.generate_category_title",
            new=AsyncMock(return_value={"title_cn": None, "title_en": None}),
        ),
    ):
        from importyeti.reports.two_pager_service import TwoPagerService
        from importyeti.reports.two_pager_models import TwoPagerResponse

        svc = TwoPagerService()
        # Patch the instance's client so _fetch_category_aggregates doesn't hit IY
        svc.client.power_query_buyers = AsyncMock(return_value=_empty_pq_response())

        result = await svc.generate_report(hs_code="940540", product_description=None)

    assert result is not None
    assert isinstance(result, TwoPagerResponse)
    assert result.hs_code == "940540"
    assert result.product_description is None
    # Only 3 canned buyers supplied — result must not exceed that
    assert len(result.buyers) <= 3
    # Sub-15-survivor guard must not crash — scores must all be int in [60, 95]
    for buyer in result.buyers:
        assert isinstance(buyer.score, int)
        assert 60 <= buyer.score <= 95, f"Score {buyer.score} out of curve bounds"


# =============================================================================
# Test 2: generate_report in product-only mode
# =============================================================================

@pytest.mark.asyncio
async def test_generate_report_product_only_mode():
    """generate_report with product_description only succeeds; hs_code stays None."""
    env_patch = {
        "LEMLIST_API_KEY": "",
        "APOLLO_API_KEY": "",
        "REAL_COMPANY_FILTER_SHADOW": "true",
    }

    with (
        patch.dict(os.environ, env_patch, clear=False),
        patch(
            "importyeti.clients.internal_bol_client.search_cache",
            new=AsyncMock(return_value=CANNED_BUYERS_3),
        ),
        patch(
            "importyeti.clients.internal_bol_client.save_to_cache",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "importyeti.reports.email_generator.classify_low_value_buyers",
            new=AsyncMock(side_effect=_noop_classify_low_value),
        ),
        patch(
            "importyeti.reports.real_company_filter.classify_real_companies",
            new=AsyncMock(return_value={}),
        ),
        patch(
            "importyeti.reports.email_generator.normalize_and_fabricate_buyer_fields",
            new=AsyncMock(return_value={}),
        ),
        patch(
            "importyeti.reports.email_generator.generate_outreach_emails",
            new=AsyncMock(return_value={}),
        ),
        patch(
            "importyeti.reports.two_pager_service.generate_category_title",
            new=AsyncMock(return_value={"title_cn": None, "title_en": None}),
        ),
    ):
        from importyeti.reports.two_pager_service import TwoPagerService
        from importyeti.reports.two_pager_models import TwoPagerResponse

        svc = TwoPagerService()
        svc.client.power_query_buyers = AsyncMock(return_value=_empty_pq_response())

        result = await svc.generate_report(
            hs_code=None,
            product_description="wooden furniture",
        )

    assert result is not None
    assert isinstance(result, TwoPagerResponse)
    assert result.hs_code is None
    assert result.product_description == "wooden furniture"
    # hs_code_description is now populated from product_description for
    # display headers — used to be Phase-0-removed, then re-added.
    assert result.hs_code_description == "wooden furniture"
    assert len(result.buyers) <= 3


# =============================================================================
# Test 3: generate_report with neither param raises ValueError
# =============================================================================

@pytest.mark.asyncio
async def test_generate_report_neither_param_raises():
    """generate_report() with no hs_code and no product_description raises ValueError."""
    from importyeti.reports.two_pager_service import TwoPagerService

    svc = TwoPagerService()
    with pytest.raises(ValueError, match="at least one of hs_code or product_description"):
        await svc.generate_report()


# =============================================================================
# Test 4: synthesize_demo_contact (singular) — happy path, no external calls
# =============================================================================
# The plural `synthesize_demo_contacts` and the /two-pager/demo-fill route
# were removed 2026-04-25 in favour of inline auto-synth in two_pager_service.
# This test now covers the singular helper that the new flow calls per slot.

def test_synthesize_demo_contact_happy_path():
    """synthesize_demo_contact returns is_synthesized=True with the
    demo+<slug>@preludeos.com email format and [CONTACT NAME] / [COMPANY NAME]
    placeholders in the body. The two-pager service overrides the email with
    a corporate-style address before rendering, but the helper itself still
    emits the safe placeholder format."""
    from importyeti.reports.demo_contacts import synthesize_demo_contact, DEMO_EMAIL_RE

    contact = synthesize_demo_contact(
        buyer_slug="acme-trading",
        buyer_name="Acme Trading Corp",
        subject="wooden furniture",
        index=0,
    )

    assert contact["is_synthesized"] is True
    assert DEMO_EMAIL_RE.match(contact["email"]), (
        f"Demo email {contact['email']!r} does not match demo+<slug>@preludeos.com"
    )
    assert "[CONTACT NAME]" in contact["email_body"]
    assert "[COMPANY NAME]" in contact["email_body"]


# =============================================================================
# Test 5: TwoPagerRequest validator — four-case parametrize
# =============================================================================

@pytest.mark.parametrize("payload,should_pass", [
    ({"hs_code": "940540"}, True),
    ({"product_description": "wooden furniture"}, True),
    ({"hs_code": "940540", "product_description": "wooden furniture"}, True),
    ({}, False),
])
def test_request_validator(payload, should_pass):
    """TwoPagerRequest requires at least one of hs_code or product_description."""
    from importyeti.reports.two_pager_models import TwoPagerRequest
    from pydantic import ValidationError

    if should_pass:
        req = TwoPagerRequest(**payload)
        # Sanity: whichever field was supplied must round-trip
        for k, v in payload.items():
            assert getattr(req, k) == v
    else:
        with pytest.raises(ValidationError):
            TwoPagerRequest(**payload)


# =============================================================================
# Test 6: Apollo-primary is the default provider
# =============================================================================

def test_apollo_primary_default(monkeypatch):
    """get_apollo_service() returns ApolloLeadService when ENRICHMENT_PROVIDER is unset."""
    monkeypatch.delenv("ENRICHMENT_PROVIDER", raising=False)
    # ApolloLeadService.__init__ validates APOLLO_API_KEY on construction; provide
    # a sentinel value so the factory path can be exercised without a real key.
    monkeypatch.setenv("APOLLO_API_KEY", "test-sentinel-key")

    import apollo_io.service as svc_module
    # Reset singleton so the factory re-runs
    svc_module._apollo_service = None

    result = svc_module.get_apollo_service()
    assert type(result).__name__ == "ApolloLeadService", (
        f"Expected ApolloLeadService, got {type(result).__name__}"
    )

    # Cleanup: reset singleton so other tests are not affected
    svc_module._apollo_service = None


# =============================================================================
# Test 7: power_query_buyers guard — raises when both params missing
# =============================================================================

@pytest.mark.asyncio
async def test_power_query_buyers_guard():
    """power_query_buyers() with no hs_code and no product_description raises ValueError."""
    from importyeti.clients.api_client import ImportYetiClient

    client = ImportYetiClient()
    with pytest.raises(ValueError, match="at least one of hs_code or product_description"):
        await client.power_query_buyers()


# =============================================================================
# Test 8: Sub-15-survivor display-curve bounds
# =============================================================================

def test_display_curve_bounds():
    """_SCORE_CURVE access with min(i, len-1) guard never IndexErrors for 0-19."""
    from importyeti.reports.two_pager_service import _SCORE_CURVE

    assert len(_SCORE_CURVE) == 15, (
        f"_SCORE_CURVE should have 15 entries, found {len(_SCORE_CURVE)}"
    )
    for i in range(20):
        idx = min(i, len(_SCORE_CURVE) - 1)
        val = _SCORE_CURVE[idx]
        assert isinstance(val, int), f"Curve entry at clamped index {idx} is not int: {val!r}"
        assert 60 <= val <= 95, f"Curve value {val} outside expected [60, 95] range"


# =============================================================================
# Test 9: deep_enrich_buyers normalises supplier_breakdown shape in-memory
# =============================================================================

@pytest.mark.asyncio
async def test_deep_enrich_buyers_normalises_supplier_breakdown():
    """`deep_enrich_buyers` must convert the raw /company/{slug} suppliers_table
    into the normalised supplier_breakdown shape expected by downstream scoring
    + two-pager helpers. The raw shape uses `total_weight`, `total_shipments_company`,
    `total_teus`, `supplier_address_country`; the normalised shape uses
    `weight_kg`, `shipments`, `teu`, `supplier_name`, `country`.
    """
    from importyeti.reports.enrichment import deep_enrich_buyers

    # Raw suppliers_table exactly as ImportYeti /company/{slug} returns it.
    raw_suppliers_table = [
        {
            "supplier_name": "Jiangsu Widget Co",
            "supplier_address_country": "CN",
            "total_shipments_company": 120,
            "shipments_percents_company": 55.0,
            "shipments_12m": 40,
            "shipments_12_24m": 35,
            "total_weight": 80_000,
            "total_teus": 12.5,
            "most_recent_shipment": "01/03/2026",
            "is_new_supplier": False,
        }
    ]

    mock_detail = MagicMock()
    mock_detail.data = {
        "suppliers_table": raw_suppliers_table,
        "time_series": {"01/03/2026": {"shipments": 40, "china_shipments": 40}},
        "most_recent_shipment": "01/03/2026",
        "company_total_shipments": 120,
    }

    mock_client = MagicMock()
    mock_client.get_company_detail = AsyncMock(return_value=mock_detail)

    captured_logger = MagicMock()

    companies = [{"slug": "test-buyer", "name": "Test Buyer Inc"}]

    # auth_token="" skips the cache-write branch — test only cares about the
    # in-memory results dict, not the /bol/enrich round-trip.
    results = await deep_enrich_buyers(
        client=mock_client,
        companies=companies,
        auth_token="",
        logger=captured_logger,
    )

    assert "test-buyer" in results, f"Missing slug in results: {results.keys()}"
    sb = results["test-buyer"]["supplier_breakdown"]
    assert isinstance(sb, list) and sb, f"supplier_breakdown is empty: {sb!r}"
    entry = sb[0]

    # Normalised shape keys must be present:
    for key in ("supplier_name", "country", "shipments", "weight_kg", "teu"):
        assert key in entry, f"Normalised key '{key}' missing from entry: {entry.keys()}"

    # Values must come from the raw fields they replace:
    assert entry["supplier_name"] == "Jiangsu Widget Co"
    assert entry["country"] == "CN"              # from supplier_address_country fallback
    assert entry["shipments"] == 120             # from total_shipments_company
    assert entry["weight_kg"] == 80_000          # from total_weight
    assert entry["teu"] == 12.5                  # from total_teus

    # Raw keys must be gone — downstream code must not see the unnormalised shape:
    for raw_key in ("total_shipments_company", "total_weight", "total_teus"):
        assert raw_key not in entry, (
            f"Raw key '{raw_key}' leaked into normalised supplier_breakdown: {entry}"
        )


# =============================================================================
# Test 10: enrich_company honours update_enrichment(False) — no credit logged
# =============================================================================

@pytest.mark.asyncio
async def test_enrich_company_raises_when_cache_write_fails():
    """When `internal_bol_client.update_enrichment` returns False, `enrich_company`
    must:
      1. NOT call `log_api_call` (no /company credit logged for a write that
         didn't persist).
      2. Raise so the caller surfaces the failure instead of silently returning
         a merged "detail_enriched" dict that lies about the cache state.
    """
    from importyeti.buyers.service import BolSearchService

    svc = BolSearchService()

    cached_row = {
        "importyeti_slug": "failing-cache-buyer",
        "enrichment_status": "pending",
        "most_recent_shipment": "01/02/2026",
        "company_total_shipments": 500,
        "total_suppliers": 5,
        "hs_codes": ["940540"],
        "matching_shipments": 300,
        "weight_kg": 60_000,
        "teu": 10,
    }
    detail_payload = {
        "suppliers_table": [
            {
                "supplier_name": "Some CN Supplier",
                "supplier_address_country": "CN",
                "total_shipments_company": 100,
                "shipments_percents_company": 40.0,
                "shipments_12m": 30,
                "shipments_12_24m": 25,
                "total_weight": 40_000,
                "total_teus": 8.0,
                "most_recent_shipment": "01/02/2026",
                "is_new_supplier": False,
            }
        ],
        "time_series": {"01/02/2026": {"shipments": 30, "china_shipments": 30}},
        "recent_bols": [],
        "also_known_names": None,
        "phone_number": None,
        "website": None,
    }

    # Mock the IY detail fetch too — the test only exercises the cache-write
    # branch, not the API call.
    mock_detail = MagicMock()
    mock_detail.data = detail_payload
    svc.client.get_company_detail = AsyncMock(return_value=mock_detail)

    credit_log_calls: List[Any] = []

    def _fake_fire_tracked(name, fn, retries=1, dedupe_key=None):
        # `fire_tracked("log_api_call", lambda: log_api_call(...))` — if the
        # enrich path fires this, record it so the test can fail loudly.
        if name == "log_api_call":
            credit_log_calls.append((name, fn))

    with (
        patch(
            "importyeti.buyers.service.internal_bol_client.get_company",
            new=AsyncMock(return_value=cached_row),
        ),
        patch(
            "importyeti.buyers.service.internal_bol_client.update_enrichment",
            new=AsyncMock(return_value=False),  # cache write fails
        ),
        patch(
            "importyeti.buyers.service.fire_tracked",
            new=_fake_fire_tracked,
        ),
    ):
        with pytest.raises(RuntimeError, match="cache write failed"):
            await svc.enrich_company(
                slug="failing-cache-buyer", auth_token="test-token",
            )

    assert not credit_log_calls, (
        f"log_api_call must NOT be fired when cache write fails; "
        f"saw {credit_log_calls!r}"
    )
