from __future__ import annotations

from importyeti.reports.pricing import (
    extract_request_cost,
    extract_total_suppliers_from_stats,
    weight_to_containers,
)


def test_one_pager_pricing_helpers_keep_expected_values() -> None:
    assert weight_to_containers(18_000) == 1
    assert weight_to_containers(36_000) == 2


def test_one_pager_stats_helpers_handle_nested_payloads() -> None:
    assert extract_total_suppliers_from_stats({"totalSuppliers": 12}) == 12
    assert extract_total_suppliers_from_stats({"data": {"totalSuppliers": "15"}}) == 15
    assert extract_request_cost({"requestCost": "0.1"}) == 0.1
