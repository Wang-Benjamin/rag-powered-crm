"""RAG (Retrieval-Augmented Generation) services for CRM agents."""

from services.rag.embedding_service import get_embedding_service, EmbeddingService, EMBEDDING_DIM
from services.rag.embedding_sync_service import (
    embed_single_interaction,
    embed_single_email,
    embed_single_note,
    populate_interaction_embeddings,
    populate_email_embeddings,
    populate_note_embeddings,
    get_embedding_stats,
)
from services.rag.context_retriever import get_context_retriever, ContextRetriever
from services.rag.rerank_service import get_rerank_service, RerankService

__all__ = [
    "get_embedding_service",
    "EmbeddingService",
    "EMBEDDING_DIM",
    "embed_single_interaction",
    "embed_single_email",
    "embed_single_note",
    "populate_interaction_embeddings",
    "populate_email_embeddings",
    "populate_note_embeddings",
    "get_embedding_stats",
    "get_context_retriever",
    "ContextRetriever",
    "get_rerank_service",
    "RerankService",
]
