from __future__ import annotations

from datetime import datetime, timezone

from importyeti.contracts.competitor_onboarding import (
    build_competitor_completion_state,
    is_current_cohort_competitor,
    is_refresh_stale,
)


def test_competitor_cohort_membership_uses_normalized_hs_codes() -> None:
    current = {"940542", "851220"}
    assert is_current_cohort_competitor(["9405.42"], current) is True
    assert is_current_cohort_competitor(["851220"], current) is True
    assert is_current_cohort_competitor(["000000"], current) is False


def test_competitor_refresh_staleness_uses_30_day_window() -> None:
    now = datetime(2026, 4, 16, tzinfo=timezone.utc)
    assert is_refresh_stale("2026-04-10T00:00:00+00:00", now=now) is False
    assert is_refresh_stale("2026-03-01T00:00:00+00:00", now=now) is True
    assert is_refresh_stale(None, now=now) is True


def test_competitor_completion_state_exposes_warning_metadata_on_shortfall() -> None:
    state = build_competitor_completion_state(ready_count=12, target=30, candidate_pool_exhausted=True)
    assert state.status == "complete"
    assert state.warning_code == "competitor_target_shortfall"
    assert state.warning_meta == {"target": 30, "ready": 12, "shortfall": 18}
