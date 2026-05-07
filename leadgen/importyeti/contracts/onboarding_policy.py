"""Shared policy helpers for the BoL onboarding contract."""

ONBOARDING_BUYER_RESULT_TARGET = 100

def buyer_overfetch_need(max_results: int, hs_code_count: int) -> int:
    """Per-HS cache fetch size — no overfetch. The router already inflates
    max_results by len(existing_leads) to cover pipeline dedup; the cache is
    deterministic so asking for exactly that many is enough for single-HS
    searches. Multi-HS searches may end up slightly short after merge
    dedup — acceptable trade-off for the bandwidth savings on the hot path.
    """
    safe_hs_count = max(1, hs_code_count)
    return max(1, max_results // safe_hs_count)


