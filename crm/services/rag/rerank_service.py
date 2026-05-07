"""
Rerank Service - Cohere Cross-Encoder Reranking

Uses Cohere's Rerank API to re-score context items with a cross-encoder
that evaluates (query, document) pairs together for true relevance scoring.
"""

import os
import logging
from typing import List, Optional

from models.context_models import ContextItem

logger = logging.getLogger(__name__)

RERANK_MODEL = "rerank-v3.5"
DEFAULT_MAX_CANDIDATES = 50
DEFAULT_TOP_N = 30


class RerankService:
    """Cross-encoder reranking using Cohere Rerank API."""

    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if RerankService._client is None:
            api_key = os.getenv("COHERE_API_KEY")
            if not api_key:
                logger.warning("COHERE_API_KEY not set - reranking will be disabled")
                return
            import cohere
            RerankService._client = cohere.Client(api_key=api_key)
            logger.info(f"Cohere rerank client initialized: {RERANK_MODEL}")

    @property
    def client(self):
        return RerankService._client

    @property
    def is_available(self) -> bool:
        return RerankService._client is not None

    def rerank(
        self,
        query: str,
        items: List[ContextItem],
        top_n: int = DEFAULT_TOP_N,
        max_candidates: int = DEFAULT_MAX_CANDIDATES,
    ) -> List[ContextItem]:
        if not items or not query:
            return items

        if not self.is_available:
            logger.warning("Reranking unavailable (no API key), returning items unchanged")
            return items[:top_n]

        candidates = [item for item in items[:max_candidates] if item.text and item.text.strip()]

        if not candidates:
            return items[:top_n]

        documents = [item.text for item in candidates]
        top_n = min(top_n, len(candidates))

        logger.info(
            f"Reranking {len(candidates)} candidates -> top {top_n} "
            f"(query: '{query[:50]}...')"
        )

        response = self.client.rerank(
            model=RERANK_MODEL,
            query=query,
            documents=documents,
            top_n=top_n,
        )

        reranked = []
        for result in response.results:
            item = candidates[result.index]
            item.score = result.relevance_score
            reranked.append(item)

        if reranked:
            logger.info(
                f"Reranking complete: top score={reranked[0].score:.4f}, "
                f"bottom score={reranked[-1].score:.4f}"
            )

        return reranked


_rerank_service: Optional[RerankService] = None


def get_rerank_service() -> RerankService:
    global _rerank_service
    if _rerank_service is None:
        _rerank_service = RerankService()
    return _rerank_service


def reset_rerank_service():
    global _rerank_service
    _rerank_service = None
    RerankService._instance = None
    RerankService._client = None
