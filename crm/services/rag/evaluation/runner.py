"""
Orchestration for offline RAG evaluation.

Wires together the golden dataset (dataset.py), the live ContextRetriever,
and the pure retrieval metrics (metrics.py). LLM-judge metrics from
judges.py can be plugged in later once a judge model and budget are
chosen.

Intentionally not wired into any API route, agent, or scheduled job.
This is a manual quality snapshot intended to be run from a notebook or
one-off script before/after a change to chunking, semantic_weight,
recency_decay_days, or the rerank stage.

Typical (currently uninvoked) usage:

    from services.rag.context_retriever import get_context_retriever
    from services.rag.evaluation.runner import evaluate_retriever, format_report
    from services.rag.evaluation.dataset import GOLDEN_SET

    report = await evaluate_retriever(conn, get_context_retriever(), GOLDEN_SET)
    print(format_report(report))
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Dict, List, Sequence

import asyncpg

from services.rag.context_retriever import ContextRetriever
from services.rag.evaluation.dataset import EvalCase
from services.rag.evaluation.metrics import (
    Ref,
    hit_rate_at_k,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)


@dataclass
class CaseResult:
    case_id: str
    agent: str
    hit_at_5: float
    recall_at_10: float
    precision_at_10: float
    mrr: float
    ndcg_at_10: float


@dataclass
class EvalReport:
    per_case: List[CaseResult]
    aggregate: Dict[str, float]
    by_agent: Dict[str, Dict[str, float]]


_METRIC_KEYS = ("hit_at_5", "recall_at_10", "precision_at_10", "mrr", "ndcg_at_10")


def _refs_from_context_result(result) -> List[Ref]:
    """Project a ContextResult down to (source_type, source_id) tuples."""
    out: List[Ref] = []
    for item in getattr(result, "items", []) or []:
        source_type = getattr(item, "source_type", None)
        source_id = getattr(item, "source_id", None)
        if source_type is None or source_id is None:
            continue
        st = source_type.value if hasattr(source_type, "value") else str(source_type)
        out.append((st, int(source_id)))
    return out


async def evaluate_retriever(
    conn: asyncpg.Connection,
    retriever: ContextRetriever,
    cases: Sequence[EvalCase],
    *,
    k_for_hit: int = 5,
    k_for_recall: int = 10,
    k_for_precision: int = 10,
    k_for_ndcg: int = 10,
    max_items: int = 30,
) -> EvalReport:
    per_case: List[CaseResult] = []
    for case in cases:
        result = await retriever.retrieve_context(
            conn=conn,
            customer_id=case.customer_id,
            query=case.query,
            max_items=max_items,
            tool_name=f"eval:{case.agent}",
        )
        predicted = _refs_from_context_result(result)
        per_case.append(
            CaseResult(
                case_id=case.case_id,
                agent=case.agent,
                hit_at_5=hit_rate_at_k(predicted, case.expected_refs, k_for_hit),
                recall_at_10=recall_at_k(predicted, case.expected_refs, k_for_recall),
                precision_at_10=precision_at_k(predicted, case.expected_refs, k_for_precision),
                mrr=mrr(predicted, case.expected_refs),
                ndcg_at_10=ndcg_at_k(predicted, case.expected_refs, k_for_ndcg),
            )
        )

    aggregate = {
        k: (mean(getattr(r, k) for r in per_case) if per_case else 0.0)
        for k in _METRIC_KEYS
    }
    by_agent: Dict[str, Dict[str, float]] = {}
    for agent in {r.agent for r in per_case}:
        rows = [r for r in per_case if r.agent == agent]
        by_agent[agent] = {k: mean(getattr(r, k) for r in rows) for k in _METRIC_KEYS}

    return EvalReport(per_case=per_case, aggregate=aggregate, by_agent=by_agent)


def format_report(report: EvalReport) -> str:
    lines = ["RAG retrieval evaluation", "=" * 32, "", "Per case:"]
    for r in report.per_case:
        lines.append(
            f"  {r.case_id:<20} {r.agent:<28} "
            f"hit@5={r.hit_at_5:.2f} recall@10={r.recall_at_10:.2f} "
            f"prec@10={r.precision_at_10:.2f} mrr={r.mrr:.2f} "
            f"ndcg@10={r.ndcg_at_10:.2f}"
        )
    lines.append("")
    lines.append("Aggregate:")
    for k, v in report.aggregate.items():
        lines.append(f"  {k:<16} {v:.3f}")
    lines.append("")
    lines.append("By agent:")
    for agent, metrics in report.by_agent.items():
        joined = " ".join(f"{k}={v:.2f}" for k, v in metrics.items())
        lines.append(f"  {agent:<32} {joined}")
    return "\n".join(lines)
