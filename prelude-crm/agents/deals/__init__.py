"""
Deal Analysis Agents.

Agents focused on deal history and stage progression analysis.
"""

from .deal_history_agent import DealHistoryAgent
from .deal_stage_progression_agent import DealStageProgressionAgent

__all__ = [
    "DealHistoryAgent",
    "DealStageProgressionAgent",
]

