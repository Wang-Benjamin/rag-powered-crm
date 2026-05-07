"""Re-export shim — trade_utils now lives in email_core.generation.trade_utils.
This file will be removed after all consumers update their imports (Phase 4e).
"""
from email_core.generation.trade_utils import (
    needs_cultural_adaptation,
    build_trade_context,
    build_buyer_intelligence_context,
    CULTURAL_ADAPTATION_PROMPT,
)

__all__ = [
    "needs_cultural_adaptation",
    "build_trade_context",
    "build_buyer_intelligence_context",
    "CULTURAL_ADAPTATION_PROMPT",
]
