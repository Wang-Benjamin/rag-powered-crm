from __future__ import annotations

from importyeti.competitors.common import (
    bucket_address,
    bucket_name,
    merge_hs_codes,
    normalize_trend_yoy,
)
from importyeti.competitors.threat import compute_threat_level


def test_bucket_helpers_accept_dict_and_string_shapes() -> None:
    assert bucket_name([{"key": "ACME", "doc_count": 2}, {"key": "OTHER", "doc_count": 1}]) == "ACME"
    assert bucket_name(["ACME"]) == "ACME"
    assert bucket_address([{"key": "Shenzhen"}]) == "Shenzhen"
    assert bucket_address(["Shenzhen"]) == "Shenzhen"


def test_competitor_normalization_helpers_preserve_existing_contracts() -> None:
    assert merge_hs_codes(["940542"], "850440") == ["940542", "850440"]
    assert normalize_trend_yoy(0.25) == 25.0
    assert normalize_trend_yoy(25) == 25.0


def test_threat_level_helper_keeps_label_thresholds() -> None:
    score, label = compute_threat_level(
        {"overlap_count": 10, "trend_yoy": 30, "matching_shipments": 100, "specialization": 90},
        max_volume=100,
    )
    assert score >= 75
    assert label == "HIGH"


def test_threat_level_helper_clamps_score_to_zero_hundred_range() -> None:
    score, _ = compute_threat_level(
        {"overlap_count": 0, "trend_yoy": -60, "matching_shipments": 0, "specialization": 0},
        max_volume=100,
    )
    assert 0 <= score <= 100


def test_threat_level_helper_labels_growing_competitor() -> None:
    score, label = compute_threat_level(
        {"overlap_count": 5, "trend_yoy": 20, "matching_shipments": 50, "specialization": 50},
        max_volume=100,
    )
    assert score >= 50
    assert label == "GROWING"


def test_threat_level_helper_labels_declining_competitor() -> None:
    _, label = compute_threat_level(
        {"overlap_count": 3, "trend_yoy": -35, "matching_shipments": 10, "specialization": 25},
        max_volume=100,
    )
    assert label == "DECLINING"
