"""
Pure retrieval-quality metrics for the RAG pipeline.

These functions take two lists of refs - the predictions returned by
ContextRetriever and the expected refs from a curated golden case - and
return a scalar score. A ref is a (source_type, source_id) tuple, e.g.
("email", 42), which is what the CRM already uses to identify a chunk.

These are the cheapest layer of the evaluation plan: deterministic, no
DB access, no LLM calls, no API budget. They can be unit-tested in
isolation against hand-built ref lists.
"""

from __future__ import annotations

from math import log2
from typing import Iterable, Sequence, Tuple

Ref = Tuple[str, int]


def hit_rate_at_k(predicted: Sequence[Ref], expected: Iterable[Ref], k: int) -> float:
    """1.0 if any expected ref appears in the top-k predictions, else 0.0."""
    expected_set = set(expected)
    return 1.0 if any(r in expected_set for r in predicted[:k]) else 0.0


def recall_at_k(predicted: Sequence[Ref], expected: Iterable[Ref], k: int) -> float:
    """Fraction of expected refs that show up anywhere in the top-k."""
    expected_set = set(expected)
    if not expected_set:
        return 0.0
    hits = sum(1 for r in predicted[:k] if r in expected_set)
    return hits / len(expected_set)


def precision_at_k(predicted: Sequence[Ref], expected: Iterable[Ref], k: int) -> float:
    """Fraction of the top-k predictions that are in the expected set."""
    if k <= 0:
        return 0.0
    top_k = list(predicted[:k])
    if not top_k:
        return 0.0
    expected_set = set(expected)
    hits = sum(1 for r in top_k if r in expected_set)
    return hits / len(top_k)


def mrr(predicted: Sequence[Ref], expected: Iterable[Ref]) -> float:
    """Reciprocal rank of the first expected ref in predictions; 0 if none."""
    expected_set = set(expected)
    for i, r in enumerate(predicted, start=1):
        if r in expected_set:
            return 1.0 / i
    return 0.0


def ndcg_at_k(predicted: Sequence[Ref], expected: Iterable[Ref], k: int) -> float:
    """Binary-relevance nDCG@k. Each expected ref contributes gain=1."""
    expected_set = set(expected)
    dcg = 0.0
    for i, r in enumerate(predicted[:k], start=1):
        if r in expected_set:
            dcg += 1.0 / log2(i + 1)
    ideal_hits = min(len(expected_set), k)
    if ideal_hits == 0:
        return 0.0
    idcg = sum(1.0 / log2(i + 1) for i in range(1, ideal_hits + 1))
    return dcg / idcg
