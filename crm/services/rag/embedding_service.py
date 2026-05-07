"""
Embedding Service - OpenAI API

Cloud-based embedding service using OpenAI's text-embedding-3-small model
for generating text embeddings for semantic search in the CRM.
"""

import os
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
MAX_TOKENS_PER_INPUT = 8000
MAX_CHARS_PER_INPUT = 6000
MAX_TEXTS_PER_BATCH = 2048


class EmbeddingService:
    """Cloud embedding service using OpenAI API."""

    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if EmbeddingService._client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")

            import openai
            EmbeddingService._client = openai.AsyncOpenAI(api_key=api_key, max_retries=3)
            logger.info(f"OpenAI embedding client initialized: {EMBEDDING_MODEL}")

    @property
    def client(self):
        return EmbeddingService._client

    @property
    def embedding_dim(self) -> int:
        return EMBEDDING_DIM

    @staticmethod
    def estimate_tokens(text: str) -> int:
        if not text:
            return 0
        return max(1, len(text) // 4)

    @staticmethod
    def calculate_smart_batch_size(
        texts: List[str],
        target_tokens_per_batch: int = 50_000,
        max_batch_size: int = 500
    ) -> int:
        if not texts:
            return 0

        token_counts = [EmbeddingService.estimate_tokens(t) for t in texts]
        avg_tokens = sum(token_counts) / len(texts) if texts else 0

        if avg_tokens > 0:
            tokens_based_batch = int(target_tokens_per_batch / avg_tokens)
        else:
            tokens_based_batch = max_batch_size

        optimal_batch_size = max(1, min(tokens_based_batch, max_batch_size))

        logger.debug(
            f"Smart batch: {len(texts)} texts, avg {avg_tokens:.0f} tokens/text, "
            f"batch_size={optimal_batch_size}"
        )

        return optimal_batch_size

    async def embed(self, text: str) -> Optional[List[float]]:
        if not text or not text.strip():
            return None

        if len(text) > MAX_CHARS_PER_INPUT:
            text = text[:MAX_CHARS_PER_INPUT]
            logger.warning(f"Text truncated to {MAX_CHARS_PER_INPUT} chars")

        response = await self.client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text
        )

        return response.data[0].embedding

    async def embed_batch(
        self,
        texts: List[str],
        batch_size: Optional[int] = None,
        show_progress: bool = True
    ) -> List[List[float]]:
        if not texts:
            return []

        processed_texts = []
        empty_indices = set()
        for i, t in enumerate(texts):
            if not t or not t.strip():
                empty_indices.add(i)
                processed_texts.append(" ")
            else:
                if len(t) > MAX_CHARS_PER_INPUT:
                    t = t[:MAX_CHARS_PER_INPUT]
                processed_texts.append(t)

        if batch_size is None:
            batch_size = self.calculate_smart_batch_size(processed_texts)

        all_embeddings = []
        total_batches = (len(processed_texts) + batch_size - 1) // batch_size

        for batch_idx in range(0, len(processed_texts), batch_size):
            batch_num = batch_idx // batch_size + 1
            batch_texts = processed_texts[batch_idx:batch_idx + batch_size]

            if show_progress and len(texts) > 100:
                logger.info(f"Embedding batch {batch_num}/{total_batches} ({len(batch_texts)} texts)")

            response = await self.client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=batch_texts
            )

            batch_embeddings = [d.embedding for d in response.data]
            all_embeddings.extend(batch_embeddings)

        for i in empty_indices:
            all_embeddings[i] = None

        return all_embeddings


_embedding_service = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


def reset_embedding_service():
    global _embedding_service
    _embedding_service = None
    EmbeddingService._instance = None
    EmbeddingService._client = None
