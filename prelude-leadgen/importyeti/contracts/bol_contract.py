"""Shared BoL onboarding contract helpers.

Pure helpers live here so onboarding/search/cache policy stops drifting across
routers and services.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Sequence


def _get_first(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row.get(key) is not None:
            return row.get(key)
    return None


def best_score(c: dict[str, Any]) -> float:
    """Return the best available score for a company row (enriched preferred)."""
    return (c.get("enriched_score") or c.get("enrichedScore")
            or c.get("quick_score") or c.get("quickScore") or 0)


def _normalize_slug(row: dict[str, Any]) -> Optional[str]:
    slug = _get_first(row, "importyeti_slug", "importyetiSlug", "supplier_slug", "slug")
    if slug:
        return str(slug)
    return None


def _normalize_hs_list(raw_hs_codes: Any) -> list[str]:
    if not raw_hs_codes:
        return []
    if isinstance(raw_hs_codes, str):
        return [raw_hs_codes.replace(".", "").strip()] if raw_hs_codes.strip() else []
    normalized: list[str] = []
    for code in raw_hs_codes:
        if not code:
            continue
        clean = str(code).replace(".", "").strip()
        if clean:
            normalized.append(clean)
    return normalized



def select_onboarding_deep_enrich_slugs(
    rows: Sequence[dict[str, Any]],
    cap: int,
) -> list[str]:
    """Pick the top onboarding deep-enrich slugs globally across the search cohort."""
    ranked = sorted(
        rows,
        key=lambda row: (_get_first(row, "quick_score", "quickScore") or 0),
        reverse=True,
    )
    selected: list[str] = []
    seen: set[str] = set()
    for row in ranked:
        slug = _normalize_slug(row)
        if not slug or slug in seen:
            continue
        status = _get_first(row, "enrichment_status", "enrichmentStatus")
        if status == "detail_enriched":
            continue
        selected.append(slug)
        seen.add(slug)
        if len(selected) >= cap:
            break
    return selected




def row_overlaps_current_hs(row: dict[str, Any], current_hs_codes: set[str]) -> bool:
    return bool(current_hs_codes.intersection(_normalize_hs_list(row.get("hs_codes"))))


@dataclass
class CompetitorRowClassification:
    cohort_rows: list[dict[str, Any]]
    refresh_stale_rows: list[dict[str, Any]]
    out_of_cohort_rows: list[dict[str, Any]]


@dataclass(frozen=True)
class CompetitorCohortState:
    in_current_cohort: bool
    is_refresh_stale: bool


def classify_competitor_rows(
    rows: Sequence[dict[str, Any]],
    current_hs_codes: set[str],
    *,
    now: Optional[datetime] = None,
    freshness_days: int = 30,
) -> CompetitorRowClassification:
    """Partition competitors by current onboarding cohort and refresh staleness."""
    current_time = now or datetime.now(timezone.utc)
    freshness_cutoff = current_time - timedelta(days=freshness_days)

    cohort_rows: list[dict[str, Any]] = []
    refresh_stale_rows: list[dict[str, Any]] = []
    out_of_cohort_rows: list[dict[str, Any]] = []

    for row in rows:
        if not row_overlaps_current_hs(row, current_hs_codes):
            out_of_cohort_rows.append(row)
            continue

        cohort_rows.append(row)
        last_updated = row.get("last_updated_at")
        if isinstance(last_updated, str):
            try:
                last_updated = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
            except ValueError:
                last_updated = None
        if last_updated and last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=timezone.utc)
        if not last_updated or last_updated < freshness_cutoff:
            refresh_stale_rows.append(row)

    return CompetitorRowClassification(
        cohort_rows=cohort_rows,
        refresh_stale_rows=refresh_stale_rows,
        out_of_cohort_rows=out_of_cohort_rows,
    )


def classify_competitor_cohort(
    *,
    competitor_hs_codes: Sequence[str] | str | None,
    current_hs_codes: Sequence[str] | set[str],
    last_updated_at: datetime | str | None,
    now: Optional[datetime] = None,
    freshness_days: int = 30,
) -> CompetitorCohortState:
    """Classify a single competitor row for current-cohort and freshness semantics."""
    normalized_current = {
        str(code).replace(".", "").strip()
        for code in current_hs_codes or []
        if str(code).replace(".", "").strip()
    }
    row = {
        "hs_codes": list(_normalize_hs_list(competitor_hs_codes)),
        "last_updated_at": last_updated_at,
    }
    classified = classify_competitor_rows(
        [row],
        normalized_current,
        now=now,
        freshness_days=freshness_days,
    )
    return CompetitorCohortState(
        in_current_cohort=bool(classified.cohort_rows),
        is_refresh_stale=bool(classified.refresh_stale_rows),
    )

