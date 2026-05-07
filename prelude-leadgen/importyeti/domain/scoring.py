"""Buyer scoring algorithm for BoL pipeline.

11 signals across two tiers, both on /100:
  Preliminary (all 500 results): S2 + S4 + S6 + S7, soft-clamped at 80.
                                 S1 and S5 contribute 0 at CSV ingest
                                 (inputs NULL by design) but are live in
                                 compute_full_score post-enrichment.
  Full (top 50 deep-enriched):   S1 through S11, hard-clamped at 100.
                                 Does NOT reuse compute_preliminary_score;
                                 invokes each helper directly to avoid
                                 double-counting.

Signals use continuous curves (gaussian, logistic, log-scale) instead of
bucket thresholds for smoother score distributions.

Lockstep: S1–S7 helpers (inside LOCKSTEP-REGION markers) are byte-identical
to prelude-internal-leads-db/utils/bol_scoring.py and are enforced by CI.
"""

import math
from datetime import date, datetime
from typing import Optional


# ── Shared helpers ──────────────────────────────────────────────────


def _parse_date(date_str: str) -> Optional[date]:
    """Parse dd/mm/yyyy or mm/dd/yyyy date strings."""
    if not date_str:
        return None
    for fmt in ("%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def _days_since(date_str: str) -> Optional[int]:
    """Days between today and a date string."""
    d = _parse_date(date_str)
    return (date.today() - d).days if d else None


def _safe_float(val) -> Optional[float]:
    """Convert to float, returning None on failure."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ── Signal functions ────────────────────────────────────────────────

# LOCKSTEP-REGION-START — everything between this marker and LOCKSTEP-REGION-END
# must be byte-identical across both scoring repos. CI enforces this. Do not edit
# one side without mirroring to the other.

def _signal_1_reorder_window(company_data: dict) -> float:
    """Reorder window -- max 20pts.

    With cycle data: gaussian peaking at 80% through cycle (sigma^2=0.5).
    Without cycle data: log-logistic curve peaking at 75 days.
    """
    MAX = 20.0
    most_recent = company_data.get("most_recent_shipment")
    avg_cycle = company_data.get("avg_order_cycle_days")

    if most_recent and avg_cycle and avg_cycle > 0:
        last_shipment = _parse_date(most_recent)
        if last_shipment:
            days_since = (date.today() - last_shipment).days
            cycle_pct = days_since / avg_cycle
            distance = abs(cycle_pct - 0.80)
            score = MAX * math.exp(-(distance ** 2) / 0.5)
            return round(min(MAX, max(0, score)), 1)

    elif most_recent:
        last_shipment = _parse_date(most_recent)
        if last_shipment:
            days_since = (date.today() - last_shipment).days
            if days_since <= 0:
                return 0.0
            peak = 75.0
            k = 2.0
            x = days_since / peak
            score = MAX * (4.0 * x ** k) / (1.0 + x ** k) ** 2
            return round(min(MAX, max(0, score)), 1)

    return 0.0


def _signal_2_supplier_diversification(company_data: dict, query_data: dict) -> float:
    """Supplier diversification -- max 22pts.

    Sub-A (max 10pts): monotonic saturating curve on supplier count.
    Sub-B (max 12pts): gaussian on china concentration, peak at 55%, widened sigma.

    Sub-A is dead (returns floor 2.5) at CSV ingest; live post-enrichment.
    Sub-B fires from cn_dominated_hs_code heuristic at ingest.
    """
    total_suppliers = company_data.get("total_suppliers")
    china_pct = query_data.get("china_concentration")

    pts = 0.0

    # Sub-A: supplier count (max 10pts)
    if total_suppliers and total_suppliers > 0:
        pts += 10.0 * (1.0 - math.exp(-max(total_suppliers - 0.5, 0.0) / 3.0))
    else:
        pts += 2.5

    # Sub-B: china concentration (max 12pts) — widened sigma from 800 to 1200
    china_pct = _safe_float(china_pct)
    if china_pct is not None and math.isfinite(china_pct):
        distance = abs(china_pct - 55)
        pts += 12.0 * math.exp(-(distance ** 2) / 1200)
    else:
        cn_dominated = query_data.get("cn_dominated_hs_code", False)
        pts += 8.0 if cn_dominated else 3.5

    return round(min(22.0, pts), 1)


def _signal_4_volume_fit(company_data: dict) -> float:
    """Volume fit -- max 28pts. Logistic sigmoid in log-space.

    Saturates for large importers instead of penalizing them.
    Slope 0.55 → 0.45 widens the scoring band across volume deciles.
    """
    MAX = 28.0
    total_shipments = company_data.get("company_total_shipments")
    if not total_shipments or total_shipments <= 0:
        return 0.0

    log_val = math.log10(max(total_shipments, 1.0))
    z = (log_val - 2.0) / 0.45
    score = MAX / (1.0 + math.exp(-z))
    return round(min(MAX, max(1.0, score)), 1)


def _signal_6_hs_relevance(company_data: dict) -> float:
    """HS code relevance -- max 22pts.  [v2: walked back from v1's 30]

    Blends ratio (buyer focus) with absolute matching count (import volume).
    Formula: 11*sqrt(ratio) + 11*log2(matching+1)/log2(256).
    At CSV ingest matching==total so ratio=1.0 always; ratio_pts saturates
    at 11. Absolute component provides the remaining discrimination.
    """
    MAX = 22.0
    matching = company_data.get("matching_shipments")
    total = company_data.get("company_total_shipments")

    if not matching or not total or total <= 0 or matching < 0:
        return 0.0

    ratio = max(0, min(1.0, matching / total))
    ratio_pts = 11.0 * math.sqrt(ratio)

    abs_pts = 11.0 * min(1.0, math.log2(max(matching, 1) + 1) / math.log2(256))

    return round(min(MAX, ratio_pts + abs_pts), 1)


def _signal_7_shipment_scale(company_data: dict) -> float:
    """Shipment scale -- max 14pts. Log-scale on TEU or weight_kg.  [v2: walked back from v1's 20]"""
    MAX = 14.0
    teu = _safe_float(company_data.get("teu"))
    weight = _safe_float(company_data.get("weight_kg"))

    if teu and teu > 0:
        score = MAX * min(1.0, math.log10(teu + 1) / math.log10(21))
        return round(max(0, score), 1)

    if weight and weight > 0:
        score = MAX * min(1.0, math.log10(weight) / 5.0)
        return round(max(0, score), 1)

    return 0.0

# LOCKSTEP-REGION-END


# ── Deep-enrichment-only signals (leadgen only, not in bol_scoring.py) ──────

def _signal_3_competitive_displacement(company_data: dict, query_data: dict) -> float:
    """Competitive displacement -- max 10pts. Deep-enrichment only.

    Power-law curve on weighted decline (|yoy_change| * market_share).
    """
    MAX = 10.0
    supplier_breakdown = company_data.get("supplier_breakdown")

    if supplier_breakdown:
        total_displacement = 0.0
        for supplier in supplier_breakdown:
            country = supplier.get("country") or ""
            if country.upper() not in ("CN", "CHINA"):
                continue
            share = (supplier.get("shipments_percents_company") or 0) / 100.0
            s12 = supplier.get("shipments_12m") or 0
            s24 = supplier.get("shipments_12_24m") or 0
            if s24 <= 0:
                continue
            yoy_change = (s12 - s24) / s24
            if yoy_change < 0:
                total_displacement += abs(yoy_change) * share

        XREF = 0.85
        GAMMA = 0.70
        score = MAX * min(1.0, (total_displacement / XREF) ** GAMMA)
        return round(max(0, score), 1)

    # Proxy fallback
    yoy_proxy = query_data.get("supplier_company_yoy")
    if yoy_proxy and yoy_proxy < -0.10:
        return round(min(MAX * 0.4, abs(yoy_proxy) * 50), 1)
    return 0.0


def _signal_5_recency_activity(company_data: dict, query_data: dict) -> float:
    """Recency & activity -- max 13pts.

    Recency (max 10pts): exponential decay, half-life 200 days.
    YoY trend (max 3pts, min -1.5pts): sigmoid centered at 0.
    """
    MAX_RECENCY = 10.0
    MAX_TREND = 3.0
    pts = 0.0

    most_recent = company_data.get("most_recent_shipment")
    if most_recent:
        days = _days_since(most_recent)
        if days is not None and days > 0:
            half_life = 200.0
            pts = MAX_RECENCY * math.exp(-0.693 * days / half_life)

    yoy_trend = query_data.get("supplier_company_yoy")
    if yoy_trend is not None and yoy_trend != 0 and math.isfinite(yoy_trend):
        clamped = max(-2.0, min(2.0, yoy_trend))
        raw = MAX_TREND * (2.0 / (1.0 + math.exp(-8.0 * clamped)) - 1.0)
        pts += max(-1.5, min(MAX_TREND, raw))

    return round(min(13.0, max(0, pts)), 1)


def _signal_8_switching_velocity(company_data: dict) -> float:
    """Supplier switching velocity -- max 3pts. Deep-enrichment only.

    Counts suppliers with shipments in last 12m but not 12-24m.
    Log1p scaling for smooth gradient across 1-12 new suppliers.
    """
    MAX = 3.0
    supplier_breakdown = company_data.get("supplier_breakdown")
    if not supplier_breakdown:
        return 0.0

    new_suppliers = 0
    for s in supplier_breakdown:
        s12 = s.get("shipments_12m") or 0
        s24 = s.get("shipments_12_24m") or 0
        if s12 > 0 and s24 == 0:
            new_suppliers += 1

    if new_suppliers == 0:
        return 0.0
    score = MAX * min(1.0, math.log1p(new_suppliers) / math.log1p(8))
    return round(score, 1)


def _signal_9_buyer_growth(company_data: dict) -> float:
    """Buyer growth trajectory -- max 5pts. Deep-enrichment only.

    Sigmoid on derived_growth_12m_pct: growing buyers = opportunity.
    """
    MAX = 5.0
    growth = _safe_float(company_data.get("derived_growth_12m_pct"))
    if growth is None or not math.isfinite(growth):
        return 0.0

    growth_frac = growth / 100.0
    score = MAX / (1.0 + math.exp(-growth_frac * 6.0))
    return round(min(MAX, max(0, score)), 1)


def _signal_10_supply_chain_vulnerability(company_data: dict) -> float:
    """Supply chain vulnerability -- max 4pts. Deep-enrichment only.

    Gaussian on HHI, peak at 0.20 (moderate concentration = sweet spot).
    """
    MAX = 4.0
    hhi = _safe_float(company_data.get("derived_supplier_hhi"))
    if hhi is None or not math.isfinite(hhi):
        return 0.0

    score = MAX * math.exp(-((hhi - 0.20) ** 2) / 0.12)
    return round(min(MAX, max(0, score)), 1)


def _signal_11_order_consistency(company_data: dict) -> float:
    """Order consistency -- max 3pts. Deep-enrichment only.

    Gaussian on CV of order regularity, peak at 0.40 (steady ordering).
    """
    MAX = 3.0
    cv = _safe_float(company_data.get("derived_order_regularity_cv"))
    if cv is None or not math.isfinite(cv):
        return 0.0

    score = MAX * math.exp(-((cv - 0.40) ** 2) / 0.20)
    return round(min(MAX, max(0, score)), 1)


# ── Score aggregation ───────────────────────────────────────────────


def compute_preliminary_score(company_data: dict, query_data: dict) -> int:
    """Signals 2+4+6+7 -- raw max 86, clamped to 80 pts. All search results.

    S1 and S5 are STRUCTURALLY ZERO at CSV ingest (inputs NULL by design).
    The 80-clamp enforces the bimodal contract (prelim ≤80, enriched 80-100).
    Clamp is applied ONLY here — NOT inside compute_full_score.
    """
    score = (
        _signal_2_supplier_diversification(company_data, query_data)
        + _signal_4_volume_fit(company_data)
        + _signal_6_hs_relevance(company_data)
        + _signal_7_shipment_scale(company_data)
    )
    return min(int(score), 80)


def compute_full_score(company_data: dict, query_data: dict) -> int:
    """All 11 signals -- 100 pts max. Top 50 deep-enriched companies.

    IMPORTANT: does NOT call compute_preliminary_score. That path applies the
    80-clamp, which would cap enriched scores at 80 and collapse the
    distribution contract. compute_full_score invokes the 11 helpers
    directly and clamps ONLY at 100, reserving 80-100 for enriched rows.
    """
    score = (
        _signal_1_reorder_window(company_data)             # 0-20 at enrichment
        + _signal_2_supplier_diversification(company_data, query_data)  # 0-22
        + _signal_3_competitive_displacement(company_data, query_data)  # 0-10
        + _signal_4_volume_fit(company_data)               # 0-28
        + _signal_5_recency_activity(company_data, query_data)          # 0-13
        + _signal_6_hs_relevance(company_data)             # 0-22
        + _signal_7_shipment_scale(company_data)           # 0-14
        + _signal_8_switching_velocity(company_data)       # 0-3
        + _signal_9_buyer_growth(company_data)             # 0-5
        + _signal_10_supply_chain_vulnerability(company_data)           # 0-4
        + _signal_11_order_consistency(company_data)       # 0-3
    )
    # Raw theoretical sum = 144; in practice rows land 60-96.
    return min(int(score), 100)


# ── Normalization ───────────────────────────────────────────────────


def normalize_scores(raw_scores: list, max_score: int = 100) -> list:
    """Quality-aware normalization for a result set.

    Preserves ordering, scales with result quality (median raw score),
    and avoids inflating weak search results. Requires 20+ scores.
    All scores are /100 after v4 recalibration (preliminary soft-caps
    at 80 at the write layer; this display layer can lift toward
    anchor_max = max_score * 0.87 ≈ 87).
    """
    _finite = lambda v: isinstance(v, (int, float)) and math.isfinite(v)
    if not raw_scores or len(raw_scores) < 20:
        return [s if _finite(s) else 0.0 for s in raw_scores]

    finite = [s for s in raw_scores if _finite(s)]
    if len(finite) < 20:
        return [s if _finite(s) else 0.0 for s in raw_scores]

    raw_min = min(finite)
    raw_max = max(finite)
    raw_range = raw_max - raw_min
    raw_median = sorted(finite)[len(finite) // 2]

    if raw_range < 3:
        return [s if _finite(s) else 0.0 for s in raw_scores]

    quality_factor = min(1.0, max(0.0, (raw_median - 15) / 20))

    # Scale target anchors with max_score: /100 → 16-87
    anchor_min = max_score * 0.16
    anchor_max = max_score * 0.87
    target_min = raw_min + (anchor_min - raw_min) * quality_factor
    target_max = raw_max + (anchor_max - raw_max) * quality_factor
    target_range = target_max - target_min

    if target_range <= 0 or raw_range <= 0:
        return [s if isinstance(s, (int, float)) and math.isfinite(s) else 0.0 for s in raw_scores]

    normalized = []
    for score in raw_scores:
        if not _finite(score):
            normalized.append(0.0)
            continue
        display = target_min + (score - raw_min) / raw_range * target_range
        display = max(5, min(max_score, display))
        normalized.append(round(display, 1))

    return normalized

