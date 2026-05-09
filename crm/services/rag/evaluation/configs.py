"""
Named retriever configurations for ablation studies.

Each ``RetrieverConfig`` is a thin record that gets unpacked into the
arguments of ``ContextRetriever.retrieve_context``. The named ``CONFIGS``
dict is the standard ablation panel — when a PR touches the retriever,
we run all six and compare to baseline.

The defaults mirror the production defaults of ``retrieve_context`` so a
config only needs to override the knobs it cares about.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class RetrieverConfig:
    name: str
    max_items: int = 25
    semantic_weight: float = 0.7
    recency_weight: float = 0.2
    recency_decay_days: int = 30
    rerank_enabled: bool = False
    rerank_top_n: int = 30
    max_per_source: int = 30
    time_window_days: Optional[int] = None
    source_types: Optional[List[str]] = None


CONFIGS: Dict[str, RetrieverConfig] = {
    "baseline":      RetrieverConfig(name="baseline"),
    "semantic_only": RetrieverConfig(name="semantic_only", semantic_weight=1.0),
    "keyword_only":  RetrieverConfig(name="keyword_only",  semantic_weight=0.0),
    "rerank":        RetrieverConfig(name="rerank",        rerank_enabled=True),
    "high_recency":  RetrieverConfig(name="high_recency",  recency_weight=0.4),
    "no_recency":    RetrieverConfig(name="no_recency",    recency_weight=0.0),
}
