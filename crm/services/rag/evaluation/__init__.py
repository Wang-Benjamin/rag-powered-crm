"""
RAG evaluation plan (offline, never invoked at runtime).

This subpackage documents and scaffolds *how* we would measure the quality
of the RAG pipeline. Nothing here is wired into request handling,
background jobs, scheduled work, or agents - importing it has no side
effects on the running CRM.

Layered evaluation:

    metrics.py    pure retrieval metrics over (source_type, source_id) refs
                  - hit_rate@k, recall@k, precision@k, MRR, nDCG@k
                  - cheap, deterministic, no API budget

    dataset.py    small in-code golden set of (query, customer_id, refs)
                  cases curated by a domain expert; one per agent /
                  source-type combination

    judges.py     LLM-as-judge stubs for end-to-end answer quality
                  - context_precision, context_recall, faithfulness,
                    answer_relevancy (Ragas taxonomy)
                  - costs API budget; left as NotImplementedError until
                    a judge model and budget are picked

    runner.py     orchestration: feed dataset through ContextRetriever,
                  collect predicted refs, compute metrics, return a report

Intended workflow:

    1. Curate ~30-100 cases in dataset.GOLDEN_SET against a fixture tenant.
    2. Run runner.evaluate_retriever() before merging changes that touch
       chunking, semantic_weight, recency_decay_days, or the rerank stage.
    3. Compare aggregate + by_agent numbers against the previous baseline.
    4. (Future) Layer in judges.py for end-to-end answer scoring.

Nothing in this package is imported by services/rag/__init__.py or any
router - it must be invoked explicitly from a script or notebook.
"""

from services.rag.evaluation.dataset import EvalCase, GOLDEN_SET
from services.rag.evaluation.metrics import (
    Ref,
    hit_rate_at_k,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)
from services.rag.evaluation.runner import (
    CaseResult,
    EvalReport,
    evaluate_retriever,
    format_report,
)

__all__ = [
    "CaseResult",
    "EvalCase",
    "EvalReport",
    "GOLDEN_SET",
    "Ref",
    "evaluate_retriever",
    "format_report",
    "hit_rate_at_k",
    "mrr",
    "ndcg_at_k",
    "precision_at_k",
    "recall_at_k",
]
