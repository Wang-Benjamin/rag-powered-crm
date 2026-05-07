"""
LLM-as-judge metric stubs for end-to-end RAG quality.

These metrics complement the pure retrieval metrics in metrics.py by
scoring the *generated answer* against the retrieved context and (where
available) the ground-truth answer. They mirror the Ragas taxonomy:

    context_precision   how much of the retrieved context is relevant
    context_recall      how much of the ground truth is covered by context
    faithfulness        is every claim in the answer supported by context
    answer_relevancy    does the answer actually address the question

The functions below are intentionally stubs. Filling them in requires:
    1. picking a judge model (e.g. Sonnet 4.6, kept distinct from the
       generator to avoid self-grading bias)
    2. a per-claim decomposition prompt
    3. an API budget line item, since each case costs ~3-5 judge calls

Until those decisions are made they raise NotImplementedError so callers
cannot silently record meaningless zeros.
"""

from __future__ import annotations

from typing import Sequence


def context_precision(
    question: str,
    retrieved_contexts: Sequence[str],
    ground_truth_answer: str,
) -> float:
    raise NotImplementedError(
        "context_precision: have an LLM judge score each retrieved chunk for"
        " relevance to the ground-truth answer, then average the scores."
    )


def context_recall(
    retrieved_contexts: Sequence[str],
    ground_truth_answer: str,
) -> float:
    raise NotImplementedError(
        "context_recall: decompose ground truth into atomic claims; for"
        " each claim, ask the judge whether the retrieved contexts entail it."
    )


def faithfulness(
    generated_answer: str,
    retrieved_contexts: Sequence[str],
) -> float:
    raise NotImplementedError(
        "faithfulness: decompose the generated answer into atomic claims;"
        " each claim is supported (1) or not (0) by the retrieved contexts."
    )


def answer_relevancy(
    question: str,
    generated_answer: str,
) -> float:
    raise NotImplementedError(
        "answer_relevancy: have the judge generate N candidate questions"
        " from the answer; score is mean cosine similarity to the original"
        " question's embedding."
    )
