from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from importyeti.contracts.onboarding_policy import (
    buyer_overfetch_need,
)
from importyeti.contracts.subscription import (
    DEFAULT_TRIAL_DURATION_DAYS,
    get_entitlements,
    get_subscription_info,
)
from importyeti.competitors.repository import (
    get_visible_competitor_slugs,
)
from importyeti.domain.transformers import (
    apply_competitor_blur,
    apply_trial_blur,
    redact_buyer_personnel_emails,
)
from routers.importyeti_subscription_router import get_subscription


def _fake_conn(row: dict):
    """Return an asyncpg-shaped mock connection returning `row` from fetchrow."""
    record = MagicMock()
    record.__getitem__ = lambda self, k: row[k]
    record.get = lambda k, default=None: row.get(k, default)
    record.__contains__ = lambda self, k: k in row
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=record)
    conn.execute = AsyncMock()
    conn.transaction = MagicMock(return_value=MagicMock(__aenter__=AsyncMock(), __aexit__=AsyncMock()))
    return conn


def _run(coro):
    return asyncio.run(coro)


def test_buyer_overfetch_need_scales_per_hs_code() -> None:
    assert buyer_overfetch_need(max_results=100, hs_code_count=1) == 100
    assert buyer_overfetch_need(max_results=100, hs_code_count=4) == 25
    assert buyer_overfetch_need(max_results=1, hs_code_count=50) == 1


def test_subscription_entitlements_stay_tiered() -> None:
    """Paid defaults -1 (unlimited); trial/expired without overrides safe-fail to 0 (blur-all)."""
    trial = get_entitlements("trial")
    paid = get_entitlements("paid")

    # Trial without explicit visibility overrides → safe-fail blur-all.
    assert trial["buyers"]["visible_limit"] == 0
    assert trial["competitors"]["visible_limit"] == 0
    # Paid defaults to unlimited.
    assert paid["buyers"]["visible_limit"] == -1
    assert paid["competitors"]["visible_limit"] == -1

    # show_buyer_emails is the only tier-sensitive default.
    assert trial["show_buyer_emails"] is False
    assert paid["show_buyer_emails"] is True

    # Exactly four top-level keys.
    assert set(trial.keys()) == {"buyers", "competitors", "show_buyer_emails", "trial"}
    assert set(paid.keys()) == {"buyers", "competitors", "show_buyer_emails", "trial"}


def test_entitlement_overrides_shift_visible_limits() -> None:
    """Per-tenant overrides must flow into resolved entitlements for all three knobs."""
    overrides = {
        "buyers": {"visible_limit": 100},
        "competitors": {"visible_limit": 1},
        "show_buyer_emails": False,
    }
    resolved = get_entitlements("trial", overrides)

    assert resolved["buyers"]["visible_limit"] == 100
    assert resolved["competitors"]["visible_limit"] == 1
    assert resolved["show_buyer_emails"] is False

    # Non-overridden keys remain at defaults.
    assert resolved["trial"]["duration_days"] == DEFAULT_TRIAL_DURATION_DAYS

    # Paid tier with buyers override — other keys unchanged.
    paid_resolved = get_entitlements("paid", {"buyers": {"visible_limit": 50}})
    assert paid_resolved["buyers"]["visible_limit"] == 50
    assert paid_resolved["competitors"]["visible_limit"] == -1
    assert paid_resolved["show_buyer_emails"] is True

    # show_buyer_emails override works as standalone bool.
    email_override = get_entitlements("paid", {"show_buyer_emails": False})
    assert email_override["show_buyer_emails"] is False
    assert email_override["buyers"]["visible_limit"] == -1


def test_show_buyer_emails_defaults_by_tier() -> None:
    """show_buyer_emails defaults to paid-only; trial and expired tenants must opt in."""
    assert get_entitlements("trial")["show_buyer_emails"] is False
    assert get_entitlements("expired")["show_buyer_emails"] is False
    assert get_entitlements("paid")["show_buyer_emails"] is True


def test_trial_duration_days_round_trips() -> None:
    """duration_days override must survive the merge; paid default must be 10."""
    assert get_entitlements("trial", {"trial": {"duration_days": 21}})["trial"]["duration_days"] == 21
    assert get_entitlements("paid", {})["trial"]["duration_days"] == DEFAULT_TRIAL_DURATION_DAYS
    assert DEFAULT_TRIAL_DURATION_DAYS == 10


def test_unknown_override_keys_are_ignored() -> None:
    """Unknown keys in overrides must not appear in the returned dict."""
    resolved = get_entitlements("trial", {"unknown_feature": {"enabled": True}})
    assert "unknown_feature" not in resolved
    assert set(resolved.keys()) == {"buyers", "competitors", "show_buyer_emails", "trial"}


def test_overriding_one_key_does_not_mutate_others() -> None:
    """Overriding buyers must not affect competitors or show_buyer_emails."""
    base = get_entitlements("paid")
    overridden = get_entitlements("paid", {"buyers": {"visible_limit": 25}})
    assert overridden["competitors"]["visible_limit"] == base["competitors"]["visible_limit"]
    assert overridden["show_buyer_emails"] == base["show_buyer_emails"]
    assert overridden["trial"]["duration_days"] == base["trial"]["duration_days"]


def test_trial_past_default_duration_becomes_expired() -> None:
    """Trial tenant 11 days in with default 10-day window → expired."""
    now = datetime.now(timezone.utc)
    row = {
        "subscription_tier": "trial",
        "trial_started_at": now - timedelta(days=11),
        "credits_used_this_month": 0,
        "last_credit_reset": None,
        "bol_onboarding_status": "complete",
        "entitlement_overrides": {},
        "bol_onboarding_phase": None, "bol_buyers_target": None, "bol_buyers_ready": None,
        "bol_competitors_target": None, "bol_competitors_ready": None,
        "bol_warning_code": None, "bol_warning_meta": None,
        "bol_last_transition_at": None, "bol_last_error_code": None,
        "bol_last_error_meta": None, "bol_attempt_count": None,
    }
    info = _run(get_subscription_info(_fake_conn(row), "test@example.com"))
    assert info["tier"] == "expired"
    assert info["entitlements"]["trial"]["duration_days"] == DEFAULT_TRIAL_DURATION_DAYS


def test_trial_past_custom_duration_becomes_expired() -> None:
    """Trial tenant 6 days in with 5-day custom window → expired."""
    now = datetime.now(timezone.utc)
    row = {
        "subscription_tier": "trial",
        "trial_started_at": now - timedelta(days=6),
        "credits_used_this_month": 0,
        "last_credit_reset": None,
        "bol_onboarding_status": "complete",
        "entitlement_overrides": {"trial": {"duration_days": 5}},
        "bol_onboarding_phase": None, "bol_buyers_target": None, "bol_buyers_ready": None,
        "bol_competitors_target": None, "bol_competitors_ready": None,
        "bol_warning_code": None, "bol_warning_meta": None,
        "bol_last_transition_at": None, "bol_last_error_code": None,
        "bol_last_error_meta": None, "bol_attempt_count": None,
    }
    info = _run(get_subscription_info(_fake_conn(row), "test@example.com"))
    assert info["tier"] == "expired"


def test_trial_within_custom_duration_stays_trial() -> None:
    """Trial tenant 5 days in with 10-day custom window → still trial."""
    now = datetime.now(timezone.utc)
    row = {
        "subscription_tier": "trial",
        "trial_started_at": now - timedelta(days=5),
        "credits_used_this_month": 0,
        "last_credit_reset": None,
        "bol_onboarding_status": "complete",
        "entitlement_overrides": {"trial": {"duration_days": 10}},
        "bol_onboarding_phase": None, "bol_buyers_target": None, "bol_buyers_ready": None,
        "bol_competitors_target": None, "bol_competitors_ready": None,
        "bol_warning_code": None, "bol_warning_meta": None,
        "bol_last_transition_at": None, "bol_last_error_code": None,
        "bol_last_error_meta": None, "bol_attempt_count": None,
    }
    info = _run(get_subscription_info(_fake_conn(row), "test@example.com"))
    assert info["tier"] == "trial"


def test_trial_missing_visibility_keys_safe_fails() -> None:
    """Trial tenant with no buyers/competitors override → visible_limit=0 (blur-all)."""
    resolved = get_entitlements("trial", {"show_buyer_emails": False})
    assert resolved["buyers"]["visible_limit"] == 0
    assert resolved["competitors"]["visible_limit"] == 0


def test_expired_missing_visibility_keys_safe_fails() -> None:
    """Expired tenant with no buyers/competitors override → visible_limit=0 (blur-all)."""
    resolved = get_entitlements("expired", {})
    assert resolved["buyers"]["visible_limit"] == 0
    assert resolved["competitors"]["visible_limit"] == 0


def test_trial_with_explicit_overrides_respects_them() -> None:
    """Trial tenant with explicit visibility overrides must NOT be clamped to 0."""
    resolved = get_entitlements("trial", {"buyers": {"visible_limit": 20}, "competitors": {"visible_limit": 5}})
    assert resolved["buyers"]["visible_limit"] == 20
    assert resolved["competitors"]["visible_limit"] == 5


def test_apply_trial_blur_unlimited_sentinel_blurs_nothing() -> None:
    """visible_limit=-1 (unlimited) must produce zero blurred rows."""
    companies = [
        {"company": "A", "score": 10},
        {"company": "B", "score": 8},
        {"company": "C", "score": 6},
    ]
    result = apply_trial_blur(companies, visible_limit=-1)
    assert all(c["is_blurred"] is False for c in result)


def test_apply_competitor_blur_unlimited_sentinel_blurs_nothing() -> None:
    """visible_limit=-1 (unlimited) must produce zero blurred competitor rows."""
    competitors = [
        {"supplier_slug": "x", "threat_score": 9},
        {"supplier_slug": "y", "threat_score": 7},
        {"supplier_slug": "z", "threat_score": 5},
    ]
    result = apply_competitor_blur(competitors, visible_limit=-1)
    assert all(c["is_blurred"] is False for c in result)


def test_get_visible_competitor_slugs_unlimited_omits_limit_clause() -> None:
    """visible_limit=-1 must fetch all rows without emitting a SQL LIMIT."""

    class FakeConn:
        def __init__(self) -> None:
            self.calls: list[tuple[str, tuple[object, ...]]] = []

        async def fetch(self, sql: str, *args):
            self.calls.append((sql, args))
            return [
                {"supplier_slug": "comp-a"},
                {"supplier_slug": "comp-b"},
                {"supplier_slug": "comp-c"},
            ]

    conn = FakeConn()

    result = _run(get_visible_competitor_slugs(conn=conn, visible_limit=-1))

    assert result == {"comp-a", "comp-b", "comp-c"}
    assert len(conn.calls) == 1
    sql, args = conn.calls[0]
    assert "LIMIT" not in sql.upper()
    assert args == ()


def test_apply_competitor_blur_strips_buyer_share_fields() -> None:
    """buyer_teu / buyer_share_pct must be blurred beyond visible_limit so
    trial tenants don't see per-buyer exposure on locked competitor rows."""
    competitors = [
        {"supplier_slug": "a", "threat_score": 9, "buyer_teu": 1190.0, "buyer_share_pct": 41.92},
        {"supplier_slug": "b", "threat_score": 7, "buyer_teu": 524.0,  "buyer_share_pct": 18.44},
        {"supplier_slug": "c", "threat_score": 5, "buyer_teu": 360.0,  "buyer_share_pct": 12.67},
    ]
    result = apply_competitor_blur(competitors, visible_limit=1)
    # Top row stays visible with fields intact.
    assert result[0]["is_blurred"] is False
    assert result[0]["buyer_teu"] == 1190.0
    assert result[0]["buyer_share_pct"] == 41.92
    # Blurred rows get both fields nulled alongside the existing blur set.
    for row in result[1:]:
        assert row["is_blurred"] is True
        assert row["buyer_teu"] is None
        assert row["buyer_share_pct"] is None


def test_redact_buyer_personnel_emails_strips_email_only() -> None:
    """Enforces show_buyer_emails=False server-side: email gone, other personnel fields intact."""
    companies = [
        {
            "company_name": "Acme",
            "personnel": [
                {"full_name": "Alice", "email": "alice@acme.com", "position": "CEO"},
                {"full_name": "Bob", "email": "bob@acme.com", "phone": "555-0100"},
            ],
        },
        {"company_name": "EmptyCo", "personnel": []},
        {"company_name": "NullCo"},
    ]
    result = redact_buyer_personnel_emails(companies)
    assert "email" not in result[0]["personnel"][0]
    assert "email" not in result[0]["personnel"][1]
    assert result[0]["personnel"][0]["full_name"] == "Alice"
    assert result[0]["personnel"][0]["position"] == "CEO"
    assert result[0]["personnel"][1]["phone"] == "555-0100"
    assert result[1]["personnel"] == []
    assert "personnel" not in result[2]


def test_subscription_router_response_keys_are_locked() -> None:
    """Frozen contract — frontend subscriptionStore + trial UI depend on these exact keys.

    Any rename or drop here breaks the UI without a type error. Pin the shape.
    """
    now = datetime.now(timezone.utc)
    row = {
        "subscription_tier": "paid",
        "trial_started_at": None,
        "credits_used_this_month": 3,
        "last_credit_reset": now,
        "bol_onboarding_status": "complete",
        "entitlement_overrides": {},
        "bol_onboarding_phase": None, "bol_buyers_target": None, "bol_buyers_ready": None,
        "bol_competitors_target": None, "bol_competitors_ready": None,
        "bol_warning_code": None, "bol_warning_meta": None,
        "bol_last_transition_at": None, "bol_last_error_code": None,
        "bol_last_error_meta": None, "bol_attempt_count": None,
    }
    conn = _fake_conn(row)
    user = {"email": "contract@example.com"}
    payload = _run(get_subscription(tenant=(conn, user)))
    assert set(payload.keys()) == {
        "tier",
        "onboardingStatus",
        "trialDaysRemaining",
        "creditsUsedThisMonth",
        "monthlyCreditsRemaining",
        "entitlements",
        "onboarding",
    }
    assert set(payload["entitlements"].keys()) == {
        "buyers",
        "competitors",
        "show_buyer_emails",
        "trial",
    }
