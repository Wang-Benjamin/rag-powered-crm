"""
Orchestration for offline RAG evaluation.

Wires together the golden dataset (dataset.py), the live ContextRetriever,
the named retriever configs (configs.py), and the pure retrieval metrics
(metrics.py). LLM-judge metrics from judges.py can be plugged in later
once a judge model and budget are chosen.

Intentionally not wired into any API route, agent, or scheduled job.
This is a manual quality snapshot intended to be run from a notebook or
one-off script before/after a change to chunking, semantic_weight,
recency_decay_days, or the rerank stage.

Typical usage:

    from services.rag.context_retriever import get_context_retriever
    from services.rag.evaluation import (
        CONFIGS, GOLDEN_SET, default_goldens,
        evaluate_ablation, format_markdown, format_report,
    )

    cases = default_goldens() or GOLDEN_SET
    reports = await evaluate_ablation(conn, get_context_retriever(), cases, CONFIGS.values())
    print(format_markdown(reports))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Dict, Iterable, List, Sequence

import asyncpg

from services.rag.context_retriever import ContextRetriever
from services.rag.evaluation.configs import CONFIGS, RetrieverConfig
from services.rag.evaluation.dataset import EvalCase
from services.rag.evaluation.metrics import (
    Ref,
    hit_rate_at_k,
    mrr,
    ndcg_at_k,
    ndcg_graded,
    precision_at_k,
    precision_violations,
    recall_at_k,
    source_balance,
)


@dataclass
class CaseResult:
    case_id: str
    agent: str
    config: str
    hit_at_5: float
    recall_at_10: float
    recall_at_25: float
    precision_at_10: float
    mrr: float
    ndcg_at_10: float
    ndcg_graded_at_25: float
    violations_at_25: int
    source_counts: Dict[str, int] = field(default_factory=dict)


@dataclass
class EvalReport:
    config: str
    per_case: List[CaseResult]
    aggregate: Dict[str, float]
    by_agent: Dict[str, Dict[str, float]]


_NUMERIC_KEYS = (
    "hit_at_5",
    "recall_at_10",
    "recall_at_25",
    "precision_at_10",
    "mrr",
    "ndcg_at_10",
    "ndcg_graded_at_25",
    "violations_at_25",
)


def _refs_from_context_result(result) -> List[Ref]:
    """Project a ContextResult down to (source_type, source_id) tuples,
    in the order the retriever returned them."""
    out: List[Ref] = []
    for item in getattr(result, "items", []) or []:
        source_type = getattr(item, "source_type", None)
        source_id = getattr(item, "source_id", None)
        if source_type is None or source_id is None:
            continue
        st = source_type.value if hasattr(source_type, "value") else str(source_type)
        out.append((st, int(source_id)))
    return out


async def run_case(
    conn: asyncpg.Connection,
    retriever: ContextRetriever,
    case: EvalCase,
    config: RetrieverConfig,
) -> CaseResult:
    """Run a single golden case under one retriever config and return the
    full set of metrics."""
    result = await retriever.retrieve_context(
        conn=conn,
        customer_id=case.customer_id,
        query=case.query,
        max_items=config.max_items,
        semantic_weight=config.semantic_weight,
        time_window_days=config.time_window_days,
        source_types=config.source_types,
        max_per_source=config.max_per_source,
        recency_weight=config.recency_weight,
        recency_decay_days=config.recency_decay_days,
        rerank_enabled=config.rerank_enabled,
        rerank_top_n=config.rerank_top_n,
        tool_name=f"eval::{config.name}",
        user_email="eval@preludeos.local",
    )
    predicted = _refs_from_context_result(result)
    required = case.required_refs()
    return CaseResult(
        case_id=case.case_id,
        agent=case.agent,
        config=config.name,
        hit_at_5=hit_rate_at_k(predicted, required, 5),
        recall_at_10=recall_at_k(predicted, required, 10),
        recall_at_25=recall_at_k(predicted, required, 25),
        precision_at_10=precision_at_k(predicted, required, 10),
        mrr=mrr(predicted, required),
        ndcg_at_10=ndcg_at_k(predicted, required, 10),
        ndcg_graded_at_25=ndcg_graded(predicted, case.gains(), 25),
        violations_at_25=precision_violations(predicted, case.must_not_cite, 25),
        source_counts=source_balance(predicted),
    )


def _aggregate(per_case: Sequence[CaseResult]) -> Dict[str, float]:
    if not per_case:
        return {k: 0.0 for k in _NUMERIC_KEYS}
    return {k: mean(getattr(r, k) for r in per_case) for k in _NUMERIC_KEYS}


def _build_report(config_name: str, per_case: List[CaseResult]) -> EvalReport:
    aggregate = _aggregate(per_case)
    by_agent: Dict[str, Dict[str, float]] = {}
    for agent in {r.agent for r in per_case}:
        rows = [r for r in per_case if r.agent == agent]
        by_agent[agent] = _aggregate(rows)
    return EvalReport(
        config=config_name,
        per_case=per_case,
        aggregate=aggregate,
        by_agent=by_agent,
    )


async def evaluate_retriever(
    conn: asyncpg.Connection,
    retriever: ContextRetriever,
    cases: Sequence[EvalCase],
    *,
    config: RetrieverConfig | None = None,
) -> EvalReport:
    """Run one config across the case set. Defaults to ``CONFIGS['baseline']``."""
    cfg = config or CONFIGS["baseline"]
    per_case: List[CaseResult] = []
    for case in cases:
        per_case.append(await run_case(conn, retriever, case, cfg))
    return _build_report(cfg.name, per_case)


async def evaluate_ablation(
    conn: asyncpg.Connection,
    retriever: ContextRetriever,
    cases: Sequence[EvalCase],
    configs: Iterable[RetrieverConfig] | None = None,
) -> List[EvalReport]:
    """Run every config in ``configs`` against ``cases``. Defaults to the
    full ``CONFIGS`` panel."""
    configs = list(configs) if configs is not None else list(CONFIGS.values())
    reports: List[EvalReport] = []
    for cfg in configs:
        reports.append(await evaluate_retriever(conn, retriever, cases, config=cfg))
    return reports


def format_report(report: EvalReport) -> str:
    """Plain-text single-config report (kept for back-compat with v1 callers)."""
    lines = [f"RAG retrieval evaluation [{report.config}]", "=" * 40, "", "Per case:"]
    for r in report.per_case:
        lines.append(
            f"  {r.case_id:<20} {r.agent:<28} "
            f"hit@5={r.hit_at_5:.2f} recall@10={r.recall_at_10:.2f} "
            f"prec@10={r.precision_at_10:.2f} mrr={r.mrr:.2f} "
            f"ndcg@10={r.ndcg_at_10:.2f} viol@25={int(r.violations_at_25)}"
        )
    lines.append("")
    lines.append("Aggregate:")
    for k in _NUMERIC_KEYS:
        lines.append(f"  {k:<20} {report.aggregate[k]:.3f}")
    lines.append("")
    lines.append("By agent:")
    for agent, metrics in report.by_agent.items():
        joined = " ".join(f"{k}={v:.2f}" for k, v in metrics.items())
        lines.append(f"  {agent:<32} {joined}")
    return "\n".join(lines)
