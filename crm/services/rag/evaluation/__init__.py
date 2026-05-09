"""
RAG evaluation harness (offline, never invoked at runtime).

This subpackage scaffolds *how* we measure the quality of the RAG
pipeline. Nothing here is wired into request handling, background jobs,
scheduled work, or agents — importing it has no side effects on the
running CRM.

Layered evaluation:

    metrics.py    pure retrieval metrics over (source_type, source_id) refs
                  - hit_rate@k, recall@k, precision@k, MRR, nDCG (binary
                    and graded), precision_violations, source_balance
                  - cheap, deterministic, no API budget

    dataset.py    EvalCase records with graded relevance
                  (must_cite / should_cite / must_not_cite). JSONL files
                  under ``golden/`` are loaded by ``default_goldens()``.

    configs.py    named retriever configurations (baseline, rerank,
                  semantic_only, ...) for ablation studies.

    runner.py     orchestration: feed cases through ContextRetriever
                  under each config, compute metrics, return reports.

    report.py     markdown writer for the configs-x-metrics ablation
                  table.

    replay.py     read recent rows from ``context_retrieval_runs`` and
                  diff their selected_refs vs. what a candidate config
                  would now return.

    judges.py     LLM-as-judge stubs for end-to-end answer quality (v2).

Typical workflow:

    uv run python -m services.rag.evaluation           # full ablation
    uv run python -m services.rag.evaluation.replay    # regression diff

Or programmatically:

    from services.rag.context_retriever import get_context_retriever
    from services.rag.evaluation import (
        CONFIGS, default_goldens, evaluate_ablation, format_markdown,
    )

    cases = default_goldens()
    reports = await evaluate_ablation(conn, get_context_retriever(), cases)
    print(format_markdown(reports))
"""

from services.rag.evaluation.configs import CONFIGS, RetrieverConfig
from services.rag.evaluation.dataset import (
    EvalCase,
    GOLDEN_DIR,
    GOLDEN_SET,
    case_from_dict,
    default_goldens,
    load_jsonl_goldens,
)
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
from services.rag.evaluation.report import format_markdown
from services.rag.evaluation.runner import (
    CaseResult,
    EvalReport,
    evaluate_ablation,
    evaluate_retriever,
    format_report,
    run_case,
)

__all__ = [
    "CONFIGS",
    "CaseResult",
    "EvalCase",
    "EvalReport",
    "GOLDEN_DIR",
    "GOLDEN_SET",
    "Ref",
    "RetrieverConfig",
    "case_from_dict",
    "default_goldens",
    "evaluate_ablation",
    "evaluate_retriever",
    "format_markdown",
    "format_report",
    "hit_rate_at_k",
    "load_jsonl_goldens",
    "mrr",
    "ndcg_at_k",
    "ndcg_graded",
    "precision_at_k",
    "precision_violations",
    "recall_at_k",
    "run_case",
    "source_balance",
]
