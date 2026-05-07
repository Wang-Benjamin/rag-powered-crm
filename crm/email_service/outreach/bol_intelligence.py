"""
Transform raw BoL data (import_context + supplier_context) from the leads table
into structured buyer intelligence for email generation prompts.

Used exclusively for cold outreach to BoL-sourced leads.
"""

import json
import logging
from datetime import date, datetime
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


def _parse_date(date_str: str) -> Optional[date]:
    """Parse date string in various formats."""
    if not date_str:
        return None
    for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def _build_personalization(import_ctx: dict) -> Optional[dict]:
    """Build personalization angle from import profile."""
    matching = import_ctx.get("matchingShipments")
    total = import_ctx.get("totalShipments")
    products = import_ctx.get("topProducts") or []
    ports = import_ctx.get("topPorts") or []
    hs_codes = import_ctx.get("hsCodes") or []

    if not matching and not total:
        return None

    # Build human-readable product description
    product_str = ", ".join(products[:2]).lower() if products else None
    port_str = "/".join(ports[:2]) if ports else None

    summary_parts = []
    if matching:
        summary_parts.append(f"~{matching} shipments/yr")
        if product_str:
            summary_parts.append(f"of {product_str}")
    elif total:
        summary_parts.append(f"{total} total shipments on record")

    if port_str:
        summary_parts.append(f"through {port_str}")

    return {
        "annualShipments": matching,
        "totalShipments": total,
        "hsCodes": hs_codes,
        "productCategories": products[:3],
        "ports": ports[:3],
        "summary": " ".join(summary_parts) if summary_parts else None,
    }


def _build_timing(import_ctx: dict) -> Optional[dict]:
    """Build timing angle from reorder cycle data."""
    most_recent = import_ctx.get("mostRecentShipment")
    avg_cycle = import_ctx.get("avgOrderCycleDays")

    if not most_recent:
        return None

    last_shipment = _parse_date(most_recent)
    if not last_shipment:
        return None

    days_since = (date.today() - last_shipment).days
    if days_since < 0:
        return None

    result = {
        "daysSinceLastShipment": days_since,
        "avgOrderCycleDays": avg_cycle,
    }

    if avg_cycle and avg_cycle > 0:
        cycle_pct = round(days_since / avg_cycle * 100)
        result["cyclePct"] = cycle_pct

        if cycle_pct >= 90:
            result["reorderWindow"] = "now"
            result["summary"] = (
                f"{days_since} days since last import, avg cycle {avg_cycle} days "
                f"— {cycle_pct}% through reorder window"
            )
        elif cycle_pct >= 70:
            result["reorderWindow"] = "approaching"
            result["summary"] = (
                f"{days_since} days since last import, avg cycle {avg_cycle} days "
                f"— approaching reorder window"
            )
        else:
            result["reorderWindow"] = "early"
            result["summary"] = (
                f"{days_since} days since last import (avg cycle: {avg_cycle} days)"
            )
    else:
        result["summary"] = f"Last import {days_since} days ago"

    return result


def _build_pricing(import_ctx: dict) -> Optional[dict]:
    """Build pricing angle from weight/TEU data."""
    weight_kg = import_ctx.get("weightKg")
    teu = import_ctx.get("teu")
    ports = import_ctx.get("topPorts") or []

    if not weight_kg and not teu:
        return None

    result = {}
    if weight_kg:
        result["weightKgPerShipment"] = weight_kg
    if teu:
        result["teuPerShipment"] = teu
    if ports:
        result["ports"] = ports[:2]

    summary_parts = []
    if weight_kg:
        summary_parts.append(f"~{weight_kg:,.0f} kg")
    if teu:
        summary_parts.append(f"{teu:.1f} TEU per shipment")
    if ports:
        summary_parts.append(f"via {'/'.join(ports[:2])}")

    result["summary"] = " / ".join(summary_parts) if summary_parts else None
    return result


def _build_supplier_vulnerability(supplier_ctx: Optional[dict]) -> Optional[dict]:
    """Build supplier vulnerability angle from supplier breakdown."""
    if not supplier_ctx:
        return None

    suppliers = supplier_ctx.get("suppliers") or []
    if not suppliers:
        return None

    # Find Chinese suppliers
    cn_suppliers = [s for s in suppliers if s.get("country", "").upper() in ("CN", "CHINA")]
    if not cn_suppliers:
        return None

    # Find primary (highest share) Chinese supplier
    primary = max(cn_suppliers, key=lambda s: s.get("share", 0))

    # JSONB stores camelCase keys (shipments12M, shipments1224M); normalize on read.
    def _ship12(s: dict) -> int:
        return s.get("shipments12M", 0) or 0

    def _ship1224(s: dict) -> int:
        return s.get("shipments1224M", 0) or 0

    declining = []
    for s in cn_suppliers:
        # trend is stored as percentage (e.g., -30.0 for 30% decline)
        trend = s.get("trend", 0)
        if trend and trend < -10:
            declining.append({
                "name": s.get("name", "Unknown"),
                "share": s.get("share", 0),
                "trend": trend,
                "trendPct": round(trend),
                "shipments12m": _ship12(s),
                "shipments12_24m": _ship1224(s),
            })

    result = {
        "primarySupplier": {
            "name": primary.get("name", "Unknown"),
            "share": primary.get("share", 0),
            "trend": primary.get("trend", 0),
            "shipments12m": _ship12(primary),
            "shipments12_24m": _ship1224(primary),
        },
        "totalChineseSuppliers": len(cn_suppliers),
        "decliningSuppliers": len(declining),
    }

    # Build summary
    primary_trend = primary.get("trend", 0)
    if primary_trend and primary_trend < -10:
        decline_pct = abs(round(primary_trend))
        ship_now = _ship12(primary)
        ship_prior = _ship1224(primary)
        trend_clause = (
            f" ({ship_prior}→{ship_now} shipments)" if (ship_now or ship_prior) else ""
        )
        result["summary"] = (
            f"Primary CN supplier ({primary['share']:.0f}% share) down {decline_pct}% YoY"
            f"{trend_clause}. Potential supply gap."
        )
    elif len(declining) > 0:
        result["summary"] = (
            f"{len(declining)} of {len(cn_suppliers)} Chinese supplier(s) declining. "
            f"Supply chain may be shifting."
        )
    else:
        result["summary"] = (
            f"{len(cn_suppliers)} active Chinese supplier(s), "
            f"primary at {primary['share']:.0f}% share."
        )

    return result


def build_bol_intelligence(
    import_context: Optional[str | dict],
    supplier_context: Optional[str | dict],
    score: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Transform raw BoL JSONB data from the leads table into structured
    buyer intelligence for email generation.

    Returns None if no BoL data is available.
    Returns a dict with the 4 intelligence angles + composeSummary + score.
    """
    # Parse JSON strings if needed
    if isinstance(import_context, str):
        try:
            import_context = json.loads(import_context)
        except (json.JSONDecodeError, ValueError):
            import_context = None

    if isinstance(supplier_context, str):
        try:
            supplier_context = json.loads(supplier_context)
        except (json.JSONDecodeError, ValueError):
            supplier_context = None

    if not import_context and not supplier_context:
        return None

    import_ctx = import_context or {}
    supplier_ctx = supplier_context

    personalization = _build_personalization(import_ctx)
    timing = _build_timing(import_ctx)
    pricing = _build_pricing(import_ctx)
    vulnerability = _build_supplier_vulnerability(supplier_ctx)

    # If we have no meaningful angles, skip
    has_data = any([personalization, timing, pricing, vulnerability])
    if not has_data:
        return None

    # Determine enrichment level
    enrichment_level = "full" if supplier_ctx else "basic"

    # Build compose summary (top-line for the AI prompt)
    summary_parts = []
    if personalization and personalization.get("summary"):
        summary_parts.append(personalization["summary"].rstrip(".") + ".")
    if timing and timing.get("summary"):
        summary_parts.append(timing["summary"].rstrip(".") + ".")
    if vulnerability and vulnerability.get("summary"):
        summary_parts.append(vulnerability["summary"].rstrip(".") + ".")
    if pricing and pricing.get("summary"):
        summary_parts.append(pricing["summary"].rstrip(".") + ".")

    return {
        "hasData": True,
        "enrichmentLevel": enrichment_level,
        "score": score,
        "personalization": personalization,
        "timing": timing,
        "pricing": pricing,
        "supplierVulnerability": vulnerability,
        "composeSummary": " ".join(summary_parts) if summary_parts else None,
    }
