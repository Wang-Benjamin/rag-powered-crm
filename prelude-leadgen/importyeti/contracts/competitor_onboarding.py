"""Helpers for competitor onboarding cohort/freshness and warning state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

COMPETITOR_FRESHNESS_DAYS = 30
COMPETITOR_CANDIDATE_BUFFER = 15
ONBOARDING_COMPETITOR_TARGET = 30
COMPETITOR_WARNING_CODE = "competitor_target_shortfall"


def normalize_hs_code(code: str | None) -> str:
    return (code or "").replace(".", "").strip()



def is_current_cohort_competitor(
    competitor_hs_codes: Iterable[str] | None,
    current_hs_codes: set[str],
) -> bool:
    if not current_hs_codes:
        return True
    return any(normalize_hs_code(code) in current_hs_codes for code in (competitor_hs_codes or []))


def is_refresh_stale(
    last_updated_at: datetime | str | None,
    *,
    now: datetime | None = None,
) -> bool:
    if last_updated_at is None:
        return True
    if isinstance(last_updated_at, str):
        try:
            parsed = datetime.fromisoformat(last_updated_at.replace("Z", "+00:00"))
        except ValueError:
            return True
    else:
        parsed = last_updated_at
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    return current - parsed > timedelta(days=COMPETITOR_FRESHNESS_DAYS)

@dataclass(frozen=True)
class CompetitorCompletionState:
    status: str
    warning_code: Optional[str]
    warning_meta: Optional[dict[str, Any]]


def build_competitor_completion_warning(
    *,
    target: int,
    ready: int,
    candidate_pool_exhausted: bool,
) -> Optional[dict[str, Any]]:
    if ready >= target or not candidate_pool_exhausted:
        return None
    return {
        "code": COMPETITOR_WARNING_CODE,
        "meta": {
            "target": target,
            "ready": ready,
            "shortfall": max(0, target - ready),
        },
    }


def build_competitor_completion_state(
    *,
    ready_count: int,
    target: int,
    candidate_pool_exhausted: bool = True,
) -> CompetitorCompletionState:
    """Build the persisted competitor completion state for tenant_subscription."""
    warning = build_competitor_completion_warning(
        target=target,
        ready=ready_count,
        candidate_pool_exhausted=candidate_pool_exhausted,
    )
    return CompetitorCompletionState(
        status="complete",
        warning_code=warning["code"] if warning else None,
        warning_meta=warning["meta"] if warning else None,
    )

