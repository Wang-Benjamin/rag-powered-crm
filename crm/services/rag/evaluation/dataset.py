"""
Golden evaluation dataset for the RAG retriever.

Held in code (not in the database) on purpose: this stays under version
control alongside the metrics that consume it, can be diffed in PRs, and
will not silently drift with tenant data.

Each EvalCase pins one query against a known customer_id together with the
specific (source_type, source_id) refs a domain expert has confirmed are
relevant. Optionally a ground-truth answer is included so end-to-end
LLM-judge metrics (see judges.py) can be added later.

The cases below are illustrative. A real eval set would include 30-100
queries spanning each insight agent (NextActionInsightAgent,
RestartMomentumInsightAgent, IcebreakerIntroAgent, DealRetrospectiveAgent)
and each source type (interaction, email, note).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from services.rag.evaluation.metrics import Ref


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    customer_id: int
    query: str
    expected_refs: Tuple[Ref, ...]
    agent: str
    ground_truth_answer: Optional[str] = None
    notes: str = ""


GOLDEN_SET: Tuple[EvalCase, ...] = (
    EvalCase(
        case_id="next-action-001",
        customer_id=1,
        agent="NextActionInsightAgent",
        query="What did we last discuss with this customer about pricing?",
        expected_refs=(
            ("email", 101),
            ("interaction", 55),
        ),
        ground_truth_answer=(
            "The most recent pricing discussion was an email exchange about"
            " the enterprise tier discount, followed by a discovery call"
            " where the customer requested a revised quote."
        ),
        notes="Pricing email should rank above the unrelated onboarding email.",
    ),
    EvalCase(
        case_id="restart-001",
        customer_id=2,
        agent="RestartMomentumInsightAgent",
        query="Open loops and unanswered questions from this customer",
        expected_refs=(
            ("note", 12),
            ("email", 207),
        ),
        notes="Recency boost should pull the unread reply to the top.",
    ),
    EvalCase(
        case_id="icebreaker-001",
        customer_id=4,
        agent="IcebreakerIntroAgent",
        query="Recent industry context and talking points for this account",
        expected_refs=(
            ("note", 88),
            ("interaction", 410),
        ),
    ),
    EvalCase(
        case_id="retro-001",
        customer_id=3,
        agent="DealRetrospectiveAgent",
        query="What objections did the customer raise during the sales cycle?",
        expected_refs=(
            ("interaction", 312),
            ("interaction", 318),
            ("note", 44),
        ),
        ground_truth_answer=(
            "Two objections surfaced: integration cost with the existing"
            " billing system, and the lack of a data residency option in EU."
        ),
    ),
)
