"""BoL subscription state — single source of truth for credit/tier constants and helpers.

All subscription state lives in `tenant_subscription` (one row per tenant DB).
User-level preferences stay in `user_preferences`.
"""

import json
import logging
from decimal import Decimal
from datetime import datetime, timezone
from typing import Any, Dict

import asyncpg

from importyeti.contracts.competitor_onboarding import ONBOARDING_COMPETITOR_TARGET
from importyeti.contracts.onboarding_policy import (
    ONBOARDING_BUYER_RESULT_TARGET,
)

logger = logging.getLogger(__name__)

DEFAULT_TRIAL_DURATION_DAYS = 10

# Paid gating
PAID_MONTHLY_CAP = 50

# Onboarding (both tiers — Prelude pays, not charged to user)
ONBOARDING_BUYER_RESULT_LIMIT = ONBOARDING_BUYER_RESULT_TARGET
ONBOARDING_BUYER_SEARCH_API_BUDGET = 75
ONBOARDING_COMPETITOR_FETCH = ONBOARDING_COMPETITOR_TARGET
ONBOARDING_AUTO_ENRICH_CAP = 10

# Stuck onboarding recovery: if status is enriching/competitors for >10 min, treat as failed
ONBOARDING_STUCK_MINUTES = 10
ONBOARDING_WARMING_MESSAGE = "Onboarding is already running. Results are warming in the background; retry in a moment."

_TABLE = "tenant_subscription"


def get_entitlements(tier: str, overrides: dict = None) -> dict:
    """Return feature entitlements merged on top of paid defaults, regardless of tier.

    Tier only affects the monthly credit cap (trial=0, paid=50).
    Visibility and email access are controlled exclusively by overrides.
    Trial/expired tenants with no buyers/competitors override key default to
    visible_limit=0 (blur-all safe-fail) rather than -1 (unlimited).
    """
    base = {
        "buyers":      {"visible_limit": -1},
        "competitors": {"visible_limit": -1},
        "show_buyer_emails": (tier == "paid"),
        "trial":       {"duration_days": DEFAULT_TRIAL_DURATION_DAYS},
    }
    if overrides:
        for key, val in overrides.items():
            if key in base and isinstance(val, dict):
                base[key].update(val)
            elif key == "show_buyer_emails" and isinstance(val, bool):
                base[key] = val

    # Safe-fail: trial/expired tenants without explicit visibility overrides
    # must not fall through to unlimited (-1). Default to blur-all (0).
    if tier in ("trial", "expired"):
        has_buyers_override = overrides and "buyers" in overrides and "visible_limit" in overrides["buyers"]
        has_competitors_override = overrides and "competitors" in overrides and "visible_limit" in overrides["competitors"]
        if not has_buyers_override:
            logger.warning(
                "tier=%s has no buyers.visible_limit override — defaulting to 0 (blur-all). "
                "Set entitlement_overrides.buyers.visible_limit to configure.",
                tier,
            )
            base["buyers"]["visible_limit"] = 0
        if not has_competitors_override:
            logger.warning(
                "tier=%s has no competitors.visible_limit override — defaulting to 0 (blur-all). "
                "Set entitlement_overrides.competitors.visible_limit to configure.",
                tier,
            )
            base["competitors"]["visible_limit"] = 0

    return base


async def _ensure_tenant_row(conn) -> None:
    """Bootstrap the singleton tenant_subscription row if it doesn't exist."""
    try:
        await conn.execute(
            f"INSERT INTO {_TABLE} (id) VALUES (TRUE) ON CONFLICT DO NOTHING",
        )
    except Exception as e:
        logger.warning(f"Failed to bootstrap tenant_subscription row: {e}")


async def get_subscription_info(conn, user_email: str = "") -> Dict[str, Any]:
    """
    Fetch subscription tier, credit usage, onboarding status, and trial expiry
    from tenant_subscription (company-level, one row).

    Auto-bootstraps the row if missing.
    Performs monthly reset if last_credit_reset is in a previous month.
    Computes real trial_days_remaining from trial_started_at.
    """
    try:
        row = await conn.fetchrow(f"SELECT * FROM {_TABLE} LIMIT 1")
    except Exception as e:
        logger.warning(f"Subscription lookup failed: {e}")
        row = None

    # Auto-bootstrap if row missing (new tenant or table just created)
    if row is None:
        await _ensure_tenant_row(conn)
        try:
            row = await conn.fetchrow(f"SELECT * FROM {_TABLE} LIMIT 1")
        except Exception:
            pass

    tier = (row["subscription_tier"] if row and row.get("subscription_tier") else "trial")
    credits_used = float(row["credits_used_this_month"]) if row and row.get("credits_used_this_month") is not None else 0.0
    last_reset = row["last_credit_reset"] if row and row.get("last_credit_reset") else None
    onboarding_status = row["bol_onboarding_status"] if row and row.get("bol_onboarding_status") else "pending"
    trial_started_at = row["trial_started_at"] if row and row.get("trial_started_at") else None
    try:
        entitlement_overrides = row["entitlement_overrides"] if row else None
        if isinstance(entitlement_overrides, str):
            entitlement_overrides = json.loads(entitlement_overrides)
    except Exception:
        entitlement_overrides = None

    # Monthly reset: if last_credit_reset is in a previous month, reset counter
    now = datetime.now(timezone.utc)
    if last_reset and (last_reset.month != now.month or last_reset.year != now.year):
        try:
            await conn.execute(
                f"UPDATE {_TABLE} SET credits_used_this_month = 0, last_credit_reset = $1",
                now,
            )
            credits_used = 0.0
            logger.info("Monthly credit reset")
        except Exception as e:
            logger.warning(f"Monthly credit reset failed: {e}")

    # Resolve entitlements first so duration_days override is available for expiry check.
    entitlements = get_entitlements(tier, entitlement_overrides)

    # Trial expiry: compute real remaining days from trial_started_at
    trial_days_remaining = None
    if tier == "trial":
        duration = entitlements["trial"]["duration_days"]
        if trial_started_at:
            elapsed = (now - trial_started_at).days
            trial_days_remaining = max(0, duration - elapsed)
            if trial_days_remaining <= 0:
                tier = "expired"
                logger.debug(
                    "tier=expired tenant trial_started_at=%s duration_days=%s",
                    trial_started_at,
                    duration,
                )
        else:
            trial_days_remaining = duration

    monthly_cap = PAID_MONTHLY_CAP if tier == "paid" else 0
    monthly_remaining = max(0, monthly_cap - credits_used)

    return {
        "tier": tier,
        "trialDaysRemaining": trial_days_remaining,
        "creditsUsedThisMonth": credits_used,
        "monthlyCreditsRemaining": monthly_remaining,
        "onboardingStatus": onboarding_status,
        "entitlements": entitlements,
        "onboarding": {
            "phase": row.get("bol_onboarding_phase") if row else None,
            "buyersTarget": row.get("bol_buyers_target") if row else None,
            "buyersReady": row.get("bol_buyers_ready") if row else None,
            "competitorsTarget": row.get("bol_competitors_target") if row else None,
            "competitorsReady": row.get("bol_competitors_ready") if row else None,
            "warningCode": row.get("bol_warning_code") if row else None,
            "warningMeta": row.get("bol_warning_meta") if row else None,
            "lastTransitionAt": row.get("bol_last_transition_at") if row else None,
            "lastErrorCode": row.get("bol_last_error_code") if row else None,
            "lastErrorMeta": row.get("bol_last_error_meta") if row else None,
            "attemptCount": row.get("bol_attempt_count") if row else None,
        },
    }


# TODO(manual-enrich): record_credits_used / reserve_monthly_credits / release_monthly_credits
# are only called when the admin-manual-enrich feature lands. They are dead in live paths after
# the trial-gating-cleanup PR.

async def record_credits_used(conn, credits: float) -> None:
    """Increment credits_used_this_month on tenant_subscription."""
    await reserve_monthly_credits(conn, credits, allow_partial=False)


async def reserve_monthly_credits(
    conn,
    credits: float,
    *,
    allow_partial: bool = False,
) -> float:
    if credits <= 0:
        return 0.0
    requested = Decimal(str(credits))
    try:
        async with conn.transaction():
            row = await conn.fetchrow(
                f"SELECT subscription_tier, credits_used_this_month "
                f"FROM {_TABLE} LIMIT 1 FOR UPDATE"
            )
            if not row:
                return 0.0
            cap = Decimal(str(PAID_MONTHLY_CAP if row["subscription_tier"] == "paid" else 0))
            used = Decimal(str(row["credits_used_this_month"] or 0))
            remaining = max(Decimal("0"), cap - used)
            granted = requested if requested <= remaining else (remaining if allow_partial else Decimal("0"))
            if granted <= 0:
                return 0.0
            await conn.execute(
                f"UPDATE {_TABLE} "
                f"SET credits_used_this_month = credits_used_this_month + $1, updated_at = NOW()",
                granted,
            )
            return float(granted)
    except Exception as e:
        logger.warning(f"Failed to reserve {credits} credits: {e}")
        return 0.0


async def release_monthly_credits(conn, credits: float) -> None:
    if credits <= 0:
        return
    try:
        await conn.execute(
            f"UPDATE {_TABLE} "
            f"SET credits_used_this_month = GREATEST(0, credits_used_this_month - $1), updated_at = NOW()",
            credits,
        )
    except Exception as e:
        logger.warning(f"Failed to release {credits} credits: {e}")


async def reserve_onboarding_buyer_ready_slots(conn, requested: int) -> int:
    if requested <= 0:
        return 0
    try:
        async with conn.transaction():
            row = await conn.fetchrow(
                f"SELECT bol_onboarding_deep_enrich_reserved FROM {_TABLE} LIMIT 1 FOR UPDATE"
            )
            current = int(row["bol_onboarding_deep_enrich_reserved"] or 0) if row else 0
            remaining = max(0, ONBOARDING_AUTO_ENRICH_CAP - current)
            granted = min(requested, remaining)
            if granted <= 0:
                return 0
            await conn.execute(
                f"UPDATE {_TABLE} "
                f"SET bol_onboarding_deep_enrich_reserved = COALESCE(bol_onboarding_deep_enrich_reserved, 0) + $1, "
                f"    bol_buyers_target = COALESCE(bol_buyers_target, $2), "
                f"    bol_last_transition_at = NOW(), "
                f"    updated_at = NOW()",
                granted,
                ONBOARDING_BUYER_RESULT_LIMIT,
            )
            return granted
    except Exception as e:
        logger.warning(f"Failed to reserve onboarding buyer slots: {e}")
        return 0


async def reserve_onboarding_auto_deep_enrich_slots(conn, requested: int) -> int:
    """Compatibility wrapper for tests and helper-only reservation flows."""
    if requested <= 0:
        return 0
    try:
        row = await conn.fetchrow(
            "SELECT $1::int AS cap, $2::int AS requested",
            ONBOARDING_AUTO_ENRICH_CAP,
            requested,
        )
        if row and "reserved" in row:
            return int(row["reserved"])
    except Exception:
        pass
    return await reserve_onboarding_buyer_ready_slots(conn, requested)


async def release_onboarding_buyer_ready_slots(conn, credits: int) -> None:
    if credits <= 0:
        return
    try:
        await conn.execute(
            f"UPDATE {_TABLE} "
            f"SET bol_onboarding_deep_enrich_reserved = GREATEST(0, COALESCE(bol_onboarding_deep_enrich_reserved, 0) - $1), "
            f"    updated_at = NOW()",
            credits,
        )
    except Exception as e:
        logger.warning(f"Failed to release onboarding buyer slots: {e}")


async def claim_onboarding(conn) -> bool:
    """Atomically claim onboarding. Returns True if this caller won the race.

    Accepts only `pending` and stuck in-flight states (`enriching`/`competitors`
    unchanged for >ONBOARDING_STUCK_MINUTES). A `failed` status is terminal —
    the onboarding fetch runs exactly once per tenant and will not auto-retry
    after a logged failure; only stuck recovery is still allowed so a crashed
    process doesn't brick the tenant forever.
    """
    try:
        result = await conn.fetchrow(
            f"UPDATE {_TABLE} "
            f"SET bol_onboarding_status = 'enriching', "
            f"    bol_onboarding_phase = 'buyers', "
            f"    bol_buyers_target = {ONBOARDING_BUYER_RESULT_LIMIT}, "
            f"    bol_buyers_ready = 0, "
            f"    bol_competitors_target = {ONBOARDING_COMPETITOR_FETCH}, "
            f"    bol_competitors_ready = 0, "
            f"    bol_warning_code = NULL, "
            f"    bol_warning_meta = NULL, "
            f"    bol_last_error_code = NULL, "
            f"    bol_last_error_meta = NULL, "
            f"    bol_last_transition_at = NOW(), "
            f"    bol_attempt_count = COALESCE(bol_attempt_count, 0) + 1, "
            f"    updated_at = NOW() "
            f"WHERE bol_onboarding_status = 'pending' "
            f"   OR (bol_onboarding_status IN ('enriching', 'competitors') "
            f"       AND updated_at < NOW() - INTERVAL '{ONBOARDING_STUCK_MINUTES} minutes') "
            f"RETURNING bol_onboarding_status",
        )
        return result is not None
    except Exception as e:
        logger.warning(f"Failed to claim onboarding: {e}")
        return False


async def set_onboarding_status(conn, user_email: str, status: str) -> None:
    """Update bol_onboarding_status. Valid: pending, enriching, competitors, complete, failed."""
    phase = {
        "pending": "pending",
        "enriching": "buyers_enriching",
        "competitors": "competitors",
        "complete": "complete",
        "failed": "failed",
    }.get(status, status)
    try:
        await conn.execute(
            f"UPDATE {_TABLE} "
            f"SET bol_onboarding_status = $1, "
            f"    bol_onboarding_phase = $2, "
            f"    bol_last_transition_at = NOW(), "
            f"    updated_at = NOW()",
            status,
            phase,
        )
    except Exception as e:
        logger.warning(f"Failed to set onboarding status to {status}: {e}")


async def update_onboarding_progress(
    conn,
    *,
    buyers_target: int | None = None,
    buyers_ready: int | None = None,
    competitors_target: int | None = None,
    competitors_ready: int | None = None,
    warning_code: str | None = None,
    warning_meta: dict | None = None,
    error_code: str | None = None,
    error_meta: dict | None = None,
) -> None:
    updates = []
    params: list[Any] = []
    if buyers_target is not None:
        params.append(buyers_target)
        updates.append(f"bol_buyers_target = ${len(params)}")
    if buyers_ready is not None:
        params.append(buyers_ready)
        updates.append(f"bol_buyers_ready = ${len(params)}")
    if competitors_target is not None:
        params.append(competitors_target)
        updates.append(f"bol_competitors_target = ${len(params)}")
    if competitors_ready is not None:
        params.append(competitors_ready)
        updates.append(f"bol_competitors_ready = ${len(params)}")
    if warning_code is not None or warning_meta is not None:
        params.append(warning_code)
        updates.append(f"bol_warning_code = ${len(params)}")
        params.append(warning_meta if warning_meta is not None else None)
        updates.append(f"bol_warning_meta = ${len(params)}::jsonb")
    if error_code is not None or error_meta is not None:
        params.append(error_code)
        updates.append(f"bol_last_error_code = ${len(params)}")
        params.append(error_meta if error_meta is not None else None)
        updates.append(f"bol_last_error_meta = ${len(params)}::jsonb")
    if not updates:
        return
    updates.append("bol_last_transition_at = NOW()")
    updates.append("updated_at = NOW()")
    try:
        await conn.execute(
            f"UPDATE {_TABLE} SET {', '.join(updates)}",
            *params,
        )
    except Exception as e:
        logger.warning(f"Failed to update onboarding progress: {e}")


async def heartbeat_onboarding(conn) -> None:
    """Bump tenant_subscription.updated_at to keep claim_onboarding stuck-detection
    from reclaiming a long-running but healthy onboarding (e.g. contact loop)."""
    try:
        await conn.execute(f"UPDATE {_TABLE} SET updated_at = NOW()")
    except Exception as e:
        logger.warning(f"Failed to heartbeat onboarding: {e}")


async def set_trial_started(conn) -> None:
    """Set trial_started_at to now if not already set."""
    try:
        await conn.execute(
            f"UPDATE {_TABLE} SET trial_started_at = $1 WHERE trial_started_at IS NULL",
            datetime.now(timezone.utc),
        )
    except Exception as e:
        logger.warning(f"Failed to set trial_started_at: {e}")


async def get_tenant_hs_codes(conn) -> list:
    """Read HS codes from tenant_subscription."""
    try:
        row = await conn.fetchrow(f"SELECT hs_codes FROM {_TABLE} LIMIT 1")
        if row and row.get("hs_codes"):
            data = row["hs_codes"]
            if isinstance(data, str):
                data = json.loads(data)
            return data
        return []
    except Exception as e:
        logger.warning(f"Failed to read tenant HS codes: {e}")
        return []


async def get_tenant_products(conn) -> list[str]:
    """Read target_products from tenant_subscription."""
    try:
        row = await conn.fetchrow(f"SELECT target_products FROM {_TABLE} LIMIT 1")
    except asyncpg.exceptions.UndefinedColumnError:
        logger.error(
            "tenant_subscription.target_products column missing — apply "
            "`ALTER TABLE tenant_subscription ADD COLUMN target_products "
            "JSONB NOT NULL DEFAULT '[]'::jsonb` against this tenant DB."
        )
        return []
    if not row or not row.get("target_products"):
        return []
    data = row["target_products"]
    if isinstance(data, str):
        try:
            return json.loads(data)
        except json.JSONDecodeError as e:
            logger.warning(f"target_products JSON parse failed: {e}")
            return []
    return data
