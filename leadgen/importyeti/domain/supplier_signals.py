"""Supplier-breakdown signal helpers shared across ImportYeti domains."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


def derive_cn_supplier_change(
    buyer_cached: Dict[str, Any],
) -> Tuple[int, int]:
    """Derive (prev_cn_count, curr_cn_count) from `supplier_breakdown`.

    - prev (N): count of CN entries with `shipments_12_24m > 0`
    - curr (M): count of CN entries with `shipments_12m > 0`

    Null-safe: returns (0, 0) when breakdown is missing or malformed.
    """
    sb = (
        buyer_cached.get("supplier_breakdown")
        or buyer_cached.get("supplierBreakdown")
    )
    if not isinstance(sb, list):
        return (0, 0)

    prev = 0
    curr = 0
    for entry in sb:
        if not isinstance(entry, dict):
            continue
        country = (entry.get("country") or entry.get("supplier_address_country") or "")
        if country.upper() not in ("CN", "CHINA"):
            continue
        s12 = entry.get("shipments_12m") or 0
        s24 = entry.get("shipments_12_24m") or 0
        if s12 > 0:
            curr += 1
        if s24 > 0:
            prev += 1
    return (prev, curr)


def get_cn_supplier_subheader(prev_cn: int, curr_cn: int) -> str:
    """Deterministic CN commentary for Page-2 buyer cards.

    Every branch is reachable; prev_cn == curr_cn == 0 falls through
    to "供应链稳定" which is the correct default for "no change".
    """
    if curr_cn <= 2 and prev_cn > curr_cn:
        return "高度集中，需要备选"
    if (prev_cn - curr_cn) >= 2:
        return "正在整合供应链"
    if (prev_cn - curr_cn) >= 1:
        return "在精简供应链"
    if (curr_cn - prev_cn) >= 1:
        return "供应商池扩张中"
    return "供应链稳定"


def is_dead_buyer(comp: Dict[str, Any]) -> bool:
    """Return True if the buyer had CN suppliers but now has none."""
    prev_cn, curr_cn = derive_cn_supplier_change(comp)
    return prev_cn > 0 and curr_cn == 0


def china_concentration(comp: Dict[str, Any]) -> Optional[float]:
    """Return CN weight fraction for post-enrichment concentration filter.

    Reads `weight_kg` from supplier_breakdown entries — the normalized
    surface key (transformers.py:35). `weight_12m` does not exist on
    either the raw or normalized shape; the previous implementation
    always summed 0 and made this filter a silent no-op.

    Returns None when supplier_breakdown is unavailable — do not filter
    unknown rows.
    """
    sb = comp.get("supplier_breakdown") or []
    if not sb:
        return None
    cn_w = sum(
        e.get("weight_kg") or 0
        for e in sb
        if isinstance(e, dict) and (e.get("country") or "").upper() in ("CN", "CHINA")
    )
    total_w = sum(e.get("weight_kg") or 0 for e in sb if isinstance(e, dict))
    return cn_w / total_w if total_w > 0 else None
