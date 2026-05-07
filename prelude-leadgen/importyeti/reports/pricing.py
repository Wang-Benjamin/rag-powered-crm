"""Pure helper functions for one-pager pricing and formatting calculations.

The FOB-per-kg lookup that previously lived here was a hardcoded
internal price table — never sourced from real procurement data and
producing misleading "$X.XM annual import" numbers. The two-pager now
displays real ImportYeti volume signals (tons / containers / shipments)
and no longer needs landed-price math. `weight_to_containers` is kept
because it's a pure conversion useful for both per-buyer and aggregate
cards.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional

KG_PER_CONTAINER = 18_000

_DUTY_RATES: Dict[str, float] = {
    "9405": 3.9,
    "8541": 0.0,
    "8504": 1.5,
    "8536": 2.7,
    "8481": 2.0,
    "7326": 3.4,
}


def hs_prefix(hs_code: str) -> str:
    clean = hs_code.replace(".", "")
    return clean[:4]


def get_duty_rate(hs_code: str) -> Optional[float]:
    return _DUTY_RATES.get(hs_prefix(hs_code))


def weight_to_containers(weight_kg: Optional[float]) -> Optional[int]:
    if not weight_kg or weight_kg <= 0:
        return None
    return max(1, round(weight_kg / KG_PER_CONTAINER))


def coerce_int(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def extract_total_suppliers_from_stats(payload: Dict[str, Any]) -> Optional[int]:
    if not isinstance(payload, dict):
        return None
    total = coerce_int(payload.get("totalSuppliers"))
    if total is not None:
        return total
    nested = payload.get("data")
    if isinstance(nested, dict):
        return coerce_int(nested.get("totalSuppliers"))
    return None


def extract_request_cost(payload: Dict[str, Any], fallback: float = 0.0) -> float:
    if not isinstance(payload, dict):
        return fallback
    try:
        raw_cost = payload.get("requestCost", fallback)
        return float(raw_cost if raw_cost is not None else fallback)
    except (TypeError, ValueError):
        return fallback


def round_percent_value(value: Any) -> Optional[float]:
    try:
        return round(float(value), 1) if value is not None else None
    except (TypeError, ValueError):
        return None


def days_since(date_str: str) -> Optional[int]:
    for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(date_str.split(".")[0], fmt).date()
            delta = date.today() - dt
            return delta.days
        except ValueError:
            continue
    return None
