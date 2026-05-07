"""
Contract test for _derive_hs_metrics_from_bols.

Why this test exists
--------------------
Before 2026-04-22, the BoL deep-enrich write path dropped hs_metrics on the
floor (update_enrichment in internal-leads-db never wrote the column). 116
of 254 detail_enriched rows ended up with hs_metrics='{}', which rendered
as "—" for 年进口量 in the frontend two-pager. The fix wires a helper that
aggregates recent_bols by HS_Code into the enrichment payload. These
assertions pin the shape so future refactors can't silently regress.
"""
from importyeti.buyers.service import _derive_hs_metrics_from_bols


def _bol(hs: str, weight: float, teu: float) -> dict:
    return {"HS_Code": hs, "Weight_in_KG": str(weight), "TEU": str(teu)}


def test_empty_input_returns_empty_dict():
    assert _derive_hs_metrics_from_bols(None) == {}
    assert _derive_hs_metrics_from_bols([]) == {}


def test_single_hs_code_aggregates_one_bucket():
    result = _derive_hs_metrics_from_bols([
        _bol("940540", 1000, 1.5),
        _bol("940540", 2000, 2.5),
    ])
    assert set(result.keys()) == {"940540"}
    entry = result["940540"]
    assert entry["matching_shipments"] == 2
    assert entry["weight_kg"] == 3000.0
    assert entry["teu"] == 4.0


def test_multiple_hs_codes_produce_distinct_buckets():
    """The duplication bug pattern — same totals across HS codes — must
    not reappear. Each HS gets its OWN aggregate of matching shipments."""
    result = _derive_hs_metrics_from_bols([
        _bol("940540", 1000, 1.0),
        _bol("940540", 2000, 2.0),
        _bol("940161", 500, 0.5),
    ])
    assert result["940540"]["matching_shipments"] == 2
    assert result["940540"]["weight_kg"] == 3000.0
    assert result["940161"]["matching_shipments"] == 1
    assert result["940161"]["weight_kg"] == 500.0


def test_short_hs_codes_are_dropped():
    """HS-6 storage contract — 4-digit chapter-level keys violate the
    hs_codes array contract on the DB side. Drop them early."""
    result = _derive_hs_metrics_from_bols([
        _bol("9405", 100, 0.1),     # 4 digits — invalid
        _bol("940540", 200, 0.2),   # 6 digits — valid
    ])
    assert set(result.keys()) == {"940540"}


def test_missing_hs_code_entries_skipped():
    result = _derive_hs_metrics_from_bols([
        {"HS_Code": "", "Weight_in_KG": 100, "TEU": 1},
        {"Weight_in_KG": 100, "TEU": 1},  # no HS_Code key
        _bol("940540", 200, 0.2),
    ])
    assert set(result.keys()) == {"940540"}


def test_non_numeric_weight_teu_treated_as_zero():
    """ImportYeti occasionally returns None or malformed numeric strings.
    The helper must tolerate them without crashing or polluting sums."""
    result = _derive_hs_metrics_from_bols([
        {"HS_Code": "940540", "Weight_in_KG": None, "TEU": "abc"},
        _bol("940540", 100, 1.0),
    ])
    assert result["940540"]["matching_shipments"] == 2
    assert result["940540"]["weight_kg"] == 100.0
    assert result["940540"]["teu"] == 1.0


def test_lowercase_field_names_supported():
    """IY payloads are mostly CamelCase but the helper tolerates snake_case
    so internal test fixtures (which use snake) don't have to be special-cased."""
    result = _derive_hs_metrics_from_bols([
        {"hs_code": "940540", "weight_in_kg": 500, "teu": 0.5},
    ])
    assert result["940540"]["matching_shipments"] == 1
    assert result["940540"]["weight_kg"] == 500.0
