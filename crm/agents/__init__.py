"""
CRM Agents Package

Reorganized agent structure:
- core/: Shared utilities (ModelFactory)
- insights/: Main CRM insight agents
- communication/: Email and note analysis agents
- deals/: Deal-related agents
- feedback/: Feedback analysis agents
"""

# Core utilities
from .core.model_factory import ModelFactory, ModelInfo

# Insight agents
from .insights.icebreaker_intro_agent import IcebreakerIntroAgent
from .insights.next_action_insight_agent import NextActionInsightAgent
from .insights.restart_momentum_insight_agent import RestartMomentumInsightAgent
from .insights.deal_retrospective_agent import DealRetrospectiveAgent

# Communication agents
from .communication.email_agent import EmailAgent
from .communication.note_agent import NoteAgent

# Deal agents
from .deals.deal_history_agent import DealHistoryAgent
from .deals.deal_stage_progression_agent import DealStageProgressionAgent

# Feedback agents
from .feedback.feedback_agent import FeedbackAnalysisAgent
from .feedback.category_preference_agent import CategoryPreferenceAgent

__all__ = [
    # Core
    "ModelFactory",
    "ModelInfo",
    # Insights
    "IcebreakerIntroAgent",
    "NextActionInsightAgent",
    "RestartMomentumInsightAgent",
    "DealRetrospectiveAgent",
    # Communication
    "EmailAgent",
    "NoteAgent",
    # Deals
    "DealHistoryAgent",
    "DealStageProgressionAgent",
    # Feedback
    "FeedbackAnalysisAgent",
    "CategoryPreferenceAgent",
]
