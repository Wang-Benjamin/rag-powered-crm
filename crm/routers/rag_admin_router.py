"""
RAG Admin Router - Endpoints for managing the RAG system.

Provides embedding stats, backfill triggers, and debug search.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from service_core.db import get_tenant_connection

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/rag/stats")
async def get_rag_stats(tenant: tuple = Depends(get_tenant_connection)):
    """Get embedding coverage statistics for the current tenant."""
    from services.rag.embedding_sync_service import get_embedding_stats

    conn, user = tenant
    stats = await get_embedding_stats(conn)
    return {"status": "ok", "stats": stats}


@router.post("/rag/backfill")
async def trigger_backfill(tenant: tuple = Depends(get_tenant_connection)):
    """Trigger embedding backfill for the current tenant."""
    from services.rag.embedding_sync_service import (
        populate_interaction_embeddings,
        populate_email_embeddings,
        populate_note_embeddings,
    )

    conn, user = tenant

    interaction_stats = await populate_interaction_embeddings(conn)
    email_stats = await populate_email_embeddings(conn)
    note_stats = await populate_note_embeddings(conn)

    return {
        "status": "ok",
        "interactions": interaction_stats,
        "emails": email_stats,
        "notes": note_stats,
    }


@router.post("/rag/search")
async def debug_search(
    customer_id: int,
    query: str,
    semantic_weight: float = 0.7,
    time_window_days: Optional[int] = 30,
    max_items: int = 20,
    rerank_enabled: bool = False,
    tenant: tuple = Depends(get_tenant_connection),
):
    """Debug endpoint: run a hybrid search and return scored results."""
    from services.rag.context_retriever import get_context_retriever

    conn, user = tenant
    user_email = user.get('email', '')

    retriever = get_context_retriever()
    result = await retriever.retrieve_context(
        conn=conn,
        customer_id=customer_id,
        query=query,
        user_email=user_email,
        max_items=max_items,
        semantic_weight=semantic_weight,
        time_window_days=time_window_days,
        rerank_enabled=rerank_enabled,
        tool_name="rag_debug",
    )

    return {
        "status": "ok",
        "run_id": result.run_id,
        "retrieval_method": result.retrieval_method,
        "item_count": len(result.items),
        "items": [item.to_dict() for item in result.items],
    }
