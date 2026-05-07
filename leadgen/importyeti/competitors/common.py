"""Pure helper functions for competitor cache rows and payload normalization."""

from __future__ import annotations

import json
from typing import Any, List, Optional


def bucket_name(name_variations: Any) -> str:
    """Extract a supplier name from ImportYeti supplier bucket variations."""
    if not name_variations:
        return ""
    first = name_variations[0]
    if isinstance(first, dict):
        best = max(
            name_variations,
            key=lambda n: (n.get("doc_count", 0) or 0) if isinstance(n, dict) else 0,
        )
        return (best.get("key") if isinstance(best, dict) else "") or ""
    return str(first or "")


def bucket_address(addr_list: Any) -> Optional[str]:
    """Extract an address string from ImportYeti supplier address buckets."""
    if not addr_list:
        return None
    first = addr_list[0]
    if isinstance(first, dict):
        return first.get("key") or None
    return str(first) or None


def extract_city_from_address(address: str) -> Optional[str]:
    """Extract a known Chinese city name from an unstructured address string."""
    if not address:
        return None
    normalized = " ".join(address.lower().split())
    cities = [
        "Changzhou", "Chongqing", "Dongguan", "Guangzhou", "Hangzhou",
        "Zhongshan", "Zhaoqing", "Shaoxing", "Shenzhen",
        "Jiangmen", "Jieyang", "Chaozhou", "Shanghai",
        "Shantou", "Quanzhou", "Wenzhou", "Taizhou",
        "Beijing", "Foshan", "Huizhou", "Ningbo", "Xiamen",
        "Qingdao", "Nantong", "Hong Kong", "Macau", "Tianjin",
        "Suzhou", "Wuxi", "Fuzhou", "Zhuhai", "Meizhou", "Heyuan",
    ]
    for city in cities:
        if city.lower() in normalized:
            return city
    return None


def extract_cached_competitor_slug(competitor: dict[str, Any]) -> Optional[str]:
    for key in ("importyeti_slug", "supplier_slug", "slug"):
        value = competitor.get(key)
        if value:
            return value
    return None


def list_or_empty(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def list_or_none(value: Any) -> Optional[List[Any]]:
    items = list_or_empty(value)
    return items or None


def merge_hs_codes(raw_hs_codes: Any, hs_code: str) -> List[str]:
    merged: List[str] = []
    for code in list_or_empty(raw_hs_codes) + [hs_code]:
        if code and code not in merged:
            merged.append(code)
    return merged


def json_or_none(value: Any) -> Optional[Any]:
    if value in (None, "", []):
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return None
    return value


def normalize_trend_yoy(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        trend = float(value)
    except (TypeError, ValueError):
        return None
    return round(trend * 100, 1) if abs(trend) < 10 else round(trend, 1)
