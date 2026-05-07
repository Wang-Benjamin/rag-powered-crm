"""Contract tests for add-to-pipeline cohort integrity (T-FIX-4B)."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from importyeti.contracts.bol_contract import best_score as _best_score
from importyeti.domain.transformers import parse_city_state
from importyeti.services import lead_pipeline
from routers.importyeti_buyers_router import AddToPipelineRequest


def test_add_to_pipeline_request_requires_hs_codes_or_products() -> None:
    """Cohort reconstruction depends on submitted filters. A request without
    either hs_codes or products cannot be bound to a search the user made,
    so it must be rejected at the Pydantic layer — otherwise an unlimited
    tenant could import arbitrary cached slugs (authorization bypass)."""
    with pytest.raises(ValidationError):
        AddToPipelineRequest(slugs=["some-slug"])
    with pytest.raises(ValidationError):
        AddToPipelineRequest(slugs=["some-slug"], hs_codes=[], products=[])
    # Either alone is sufficient.
    AddToPipelineRequest(slugs=["some-slug"], hs_codes=["6405"])
    AddToPipelineRequest(slugs=["some-slug"], products=["leather boots"])


def _make_company(slug: str, score: float) -> dict:
    return {"importyeti_slug": slug, "quick_score": score, "enriched_score": None}


def _sorted_cohort(companies: list[dict], limit: int) -> set[str]:
    """Replicate the dedup+sort+slice logic from add_to_pipeline."""
    seen: dict = {}
    for c in companies:
        slug_val = c.get("importyeti_slug") or c.get("importyetiSlug") or ""
        if not slug_val:
            continue
        score = _best_score(c)
        if slug_val not in seen or score > _best_score(seen[slug_val]):
            seen[slug_val] = c
    # Secondary sort by supplier_slug for stable tie-breaking at the cutoff boundary.
    deduped = sorted(
        seen.values(),
        key=lambda r: (-_best_score(r), r.get("importyeti_slug") or r.get("importyetiSlug") or ""),
    )
    return {(c.get("importyeti_slug") or c.get("importyetiSlug")) for c in deduped[:limit]}


def test_add_to_pipeline_rejects_slug_outside_submitted_filters() -> None:
    """A slug visible only under broader filters must be rejected under narrower ones.

    Scenario: hs_codes=[A] returns companies [slug-a, slug-b]. hs_codes=[A, B]
    additionally returns slug-ab. A client submitting hs_codes=[A] and requesting
    slug-ab should be rejected because the [A]-only cohort doesn't include it.
    """
    # Cohort under hs_codes=[A]: only slug-a and slug-b
    cohort_a = [
        _make_company("slug-a", 90.0),
        _make_company("slug-b", 80.0),
    ]
    # Cohort under hs_codes=[A, B] additionally includes slug-ab
    cohort_ab = [
        _make_company("slug-a", 90.0),
        _make_company("slug-ab", 85.0),
        _make_company("slug-b", 80.0),
    ]

    visible_limit = 2

    # With hs_codes=[A] the allowed set is slug-a and slug-b
    allowed_a = _sorted_cohort(cohort_a, visible_limit)
    assert "slug-a" in allowed_a
    assert "slug-b" in allowed_a
    assert "slug-ab" not in allowed_a  # not visible under [A]-only filters

    # With hs_codes=[A, B] slug-ab is visible (ranked #2 by score)
    allowed_ab = _sorted_cohort(cohort_ab, visible_limit)
    assert "slug-ab" in allowed_ab


def test_add_to_pipeline_tie_scores_deterministic() -> None:
    """Two slugs with identical score at the cutoff must resolve deterministically.

    The slug that sorts alphabetically first must always be in the allowed set,
    regardless of the iteration order of the input list.
    """
    # "alpha-co" < "zeta-co" alphabetically, both have identical score
    companies_order1 = [
        _make_company("alpha-co", 75.0),
        _make_company("zeta-co", 75.0),
    ]
    companies_order2 = [
        _make_company("zeta-co", 75.0),
        _make_company("alpha-co", 75.0),
    ]

    limit = 1  # only one slot — tie must break deterministically

    allowed1 = _sorted_cohort(companies_order1, limit)
    allowed2 = _sorted_cohort(companies_order2, limit)

    # Both orderings must pick the same slug (alphabetically first)
    assert allowed1 == allowed2
    assert "alpha-co" in allowed1
    assert "zeta-co" not in allowed1


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        (
            (
                "8999 Palmer Street River Grove Il60171 Us, "
                "8999 Palmer Street River Grove Illinois 60171 United States, "
                "8999 Palmer Streer River Grove Il60171 Us"
            ),
            "River Grove, IL",
        ),
        (
            (
                "20 Main Street Acton Ma01720 Us Te 16177806356, "
                "0098 Distribution Center 46 Industrial Road Leominster Ma Ma01453 Us"
            ),
            "Acton, MA",
        ),
        (
            "0098 Distribution Center 46 Industrial Road Leominster Ma Ma01453 Us",
            "Leominster, MA",
        ),
        (
            (
                "6877 Goreway Drive Suite 3 Mississauga On L4V 1L9 Canada, "
                "6877 Goreway Drive Suite 3 Mississauga On L4V 1L9 Canada Teleandro Calvosa"
            ),
            "Mississauga, ON",
        ),
    ],
)
def test_parse_city_state_canonicalizes_importyeti_sample_addresses(address: str, expected: str) -> None:
    assert parse_city_state(address) == expected


def test_parse_city_state_uses_unknown_instead_of_raw_blob_for_unparseable_address() -> None:
    raw = "Warehouse One, Warehouse Two, Trailing Contact Name"

    assert parse_city_state(raw) == "Unknown"


@pytest.mark.asyncio
async def test_add_to_pipeline_location_prefers_structured_city_state_and_never_raw_blob(monkeypatch) -> None:
    captured_leads: list[dict] = []

    class FakeLeadRepository:
        async def create_lead(self, conn, lead_data, **kwargs):
            captured_leads.append(dict(lead_data))
            return f"00000000-0000-0000-0000-00000000000{len(captured_leads)}"

    class FakeConn:
        async def fetch(self, *args, **kwargs):
            return []

    monkeypatch.setattr(lead_pipeline, "LeadRepository", FakeLeadRepository)
    monkeypatch.setattr(lead_pipeline, "get_employee_id_by_email", AsyncMock(return_value=None))
    monkeypatch.setattr(lead_pipeline.ActivityLogger, "log", AsyncMock())
    monkeypatch.setattr(lead_pipeline, "fire_tracked", lambda *args, **kwargs: None)

    result = await lead_pipeline.add_slugs_to_pipeline(
        FakeConn(),
        {"email": "owner@example.com", "db_name": "tenant_test"},
        auth_token="test-token",
        slugs=["regent-products-corp", "unknown-location-co"],
        prefetched_companies={
            "regent-products-corp": {
                "company_name": "Regent Products Corp",
                "city": "River Grove",
                "state": "IL",
                "address": (
                    "8999 Palmer Street River Grove Il60171 Us, "
                    "8999 Palmer Street River Grove Illinois 60171 United States"
                ),
                "hs_codes": ["950510"],
                "quick_score": 80,
            },
            "unknown-location-co": {
                "company_name": "Unknown Location Co",
                "city": None,
                "state": None,
                "address": "Warehouse One, Warehouse Two, Trailing Contact Name",
                "hs_codes": ["950510"],
                "quick_score": 50,
            },
        },
    )

    assert result["created"] == 2
    assert captured_leads[0]["location"] == "River Grove, IL"
    assert captured_leads[1]["location"] == "Unknown"
    assert "Warehouse One" not in captured_leads[1]["location"]
