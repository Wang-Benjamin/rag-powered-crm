"""Threat scoring helpers for competitors."""

from __future__ import annotations

from typing import Any, Dict, Tuple


async def compute_threat_levels(*, conn) -> None:
    competitors = await conn.fetch(
        """
        SELECT supplier_slug, overlap_count, trend_yoy,
               matching_shipments, specialization
        FROM bol_competitors
        """
    )

    max_volume = await conn.fetchval(
        "SELECT COALESCE(MAX(matching_shipments), 1) FROM bol_competitors"
    ) or 1

    for comp in competitors:
        score, level = compute_threat_level(dict(comp), max_volume)
        await conn.execute(
            "UPDATE bol_competitors SET threat_score = $1, threat_level = $2, last_updated_at = NOW() WHERE supplier_slug = $3",
            score,
            level,
            comp["supplier_slug"],
        )


def compute_threat_level(competitor: Dict[str, Any], max_volume: int) -> Tuple[int, str]:
    """
    Compute threat score (0-100) and label.

    Weights:
    - Buyer overlap: 30% (most important -- direct competition)
    - Growth trajectory: 25% (growing = increasing threat)
    - Volume/scale: 20% (bigger = more threat)
    - Product overlap: 15% (specialization in same HS code)
    - Recency: 10% (recently active)
    """
    score = 0

    overlap = competitor.get("overlap_count") or 0
    if overlap >= 10:
        score += 30
    elif overlap >= 5:
        score += 22
    elif overlap >= 3:
        score += 15
    elif overlap >= 1:
        score += 8

    raw_trend = competitor.get("trend_yoy")
    trend = None
    if raw_trend is not None:
        trend = float(raw_trend)
        if trend >= 30:
            score += 25
        elif trend >= 15:
            score += 20
        elif trend >= 0:
            score += 12
        elif trend >= -15:
            score += 5
        elif trend >= -40:
            score += 0
        else:
            score -= 10

    volume = competitor.get("matching_shipments") or 0
    if max_volume > 0:
        volume_ratio = volume / max_volume
        score += int(volume_ratio * 20)

    spec = float(competitor.get("specialization") or 0)
    if spec >= 80:
        score += 15
    elif spec >= 50:
        score += 10
    elif spec >= 20:
        score += 5

    if raw_trend is not None:
        score += 5

    score = max(0, min(score, 100))

    if score >= 75:
        label = "HIGH"
    elif score >= 50 and raw_trend is not None and trend > 0:
        label = "GROWING"
    elif raw_trend is not None and trend <= -30:
        label = "DECLINING"
    elif score >= 25:
        label = "MODERATE"
    else:
        label = "LOW"

    return score, label
