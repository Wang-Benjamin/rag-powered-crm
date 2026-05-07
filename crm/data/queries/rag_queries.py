"""
RAG-enhanced data retrieval for CRM agents.

Replaces the raw SQL dump in get_comprehensive_customer_data() with
relevance-ranked context via hybrid search + multi-query RAG.

The output dict structure matches get_comprehensive_customer_data() exactly,
so agents need zero code changes.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple

import asyncpg

from data.queries.insights_queries import get_comprehensive_customer_data
from services.rag.context_retriever import get_context_retriever, ContextRetriever
from services.rag.embedding_service import get_embedding_service
from models.context_models import ContextItem, ContextResult

logger = logging.getLogger(__name__)

# Cache for the static base query embedding (computed once, reused)
_BASE_QUERY = "relationship status communication updates progress"
_base_query_embedding_cache: Optional[List[float]] = None


# Agent-specific category queries for multi-query RAG.
# Natural language queries outperform keyword lists for cross-encoder reranking.
AGENT_CATEGORY_QUERIES = {
    "NextActionInsightAgent": [
        {
            "category": "recent_activities",
            "query": "What recent meetings, calls, and communications happened with this client?",
            "top_n": 5,
        },
        {
            "category": "action_items",
            "query": "What follow-ups, tasks, or next steps are pending or waiting for a response?",
            "top_n": 5,
        },
        {
            "category": "deals_progress",
            "query": "How are current deals progressing? What milestones or stage changes occurred?",
            "top_n": 5,
        },
        {
            "category": "concerns",
            "query": "What issues, complaints, or concerns has the client raised recently?",
            "top_n": 3,
        },
        {
            "category": "opportunities",
            "query": "What upsell, expansion, or new business opportunities exist with this client?",
            "top_n": 3,
        },
    ],
    "RestartMomentumInsightAgent": [
        {
            "category": "last_engagement",
            "query": "What was the last meaningful interaction, meeting, or communication with this client?",
            "top_n": 5,
        },
        {
            "category": "previous_wins",
            "query": "What positive outcomes, wins, or successful deliverables were achieved in this relationship?",
            "top_n": 5,
        },
        {
            "category": "open_loops",
            "query": "What promises, follow-ups, or commitments are still unresolved or pending?",
            "top_n": 5,
        },
        {
            "category": "deal_status",
            "query": "What is the current status of active deals, proposals, and contract negotiations?",
            "top_n": 3,
        },
        {
            "category": "restart_hooks",
            "query": "What topics, events, or shared interests could serve as a reason to re-engage?",
            "top_n": 3,
        },
    ],
    "IcebreakerIntroAgent": [
        {
            "category": "industry_context",
            "query": "What is known about this company's industry, market position, and competitive landscape?",
            "top_n": 5,
        },
        {
            "category": "company_background",
            "query": "What background information exists about this company, its products, and its team?",
            "top_n": 5,
        },
        {
            "category": "talking_points",
            "query": "What potential conversation starters, shared interests, or relevant news could be used?",
            "top_n": 5,
        },
    ],
    "DealRetrospectiveAgent": [
        {
            "category": "deal_outcomes",
            "query": "What were the final outcomes of completed deals? What closed won or lost?",
            "top_n": 5,
        },
        {
            "category": "lessons_learned",
            "query": "What lessons, feedback, or process insights emerged from the deal cycle?",
            "top_n": 5,
        },
        {
            "category": "what_worked",
            "query": "What strategies, approaches, or actions contributed to successful deal outcomes?",
            "top_n": 5,
        },
        {
            "category": "what_failed",
            "query": "What obstacles, objections, or mistakes led to lost deals or delays?",
            "top_n": 5,
        },
    ],
}

# Default queries when agent type isn't recognized
DEFAULT_CATEGORY_QUERIES = [
    {
        "category": "general",
        "query": "What are the most important recent interactions, updates, and communications?",
        "top_n": 10,
    },
]


async def get_rag_enhanced_customer_data(
    customer_id: int,
    authenticated_user: dict,
    agent_type: str = "general",
    time_window_days: int = 30,
    rerank_enabled: bool = True,
    conn: asyncpg.Connection = None,
) -> Dict[str, Any]:
    """
    RAG-enhanced version of get_comprehensive_customer_data().

    Calls the original function for structured data (client_info, client_details,
    deals, summary_metrics), then replaces the interaction_details and
    employee_client_notes lists with relevance-ranked RAG results.

    The output dict structure is identical to get_comprehensive_customer_data(),
    so all agents work without code changes.

    Args:
        customer_id: Customer ID
        authenticated_user: Auth context with 'email' key
        agent_type: Agent class name for category-specific queries
        time_window_days: History lookback window
        rerank_enabled: Enable Cohere cross-encoder reranking
        conn: asyncpg connection (from get_tenant_connection)
    """
    user_email = authenticated_user.get('email')

    # If no conn provided, acquire one from the pool
    if conn is None:
        from service_core.db import get_pool_manager
        pm = get_pool_manager()
        db_name = await pm.lookup_db_name(user_email)
        async with pm.acquire(db_name) as acquired_conn:
            return await _do_rag_enhanced_retrieval(
                acquired_conn, customer_id, user_email, agent_type,
                time_window_days, rerank_enabled)
    else:
        return await _do_rag_enhanced_retrieval(
            conn, customer_id, user_email, agent_type,
            time_window_days, rerank_enabled)


async def _do_rag_enhanced_retrieval(
    conn: asyncpg.Connection,
    customer_id: int,
    user_email: str,
    agent_type: str,
    time_window_days: int,
    rerank_enabled: bool,
) -> Dict[str, Any]:
    """Internal implementation of RAG-enhanced retrieval."""
    # 1. Get full structured data (client_info, details, deals, notes, metrics)
    comprehensive_data = await get_comprehensive_customer_data(conn, customer_id)

    if not comprehensive_data:
        return {}

    # 2. Run multi-query RAG retrieval
    try:
        context_result = await _retrieve_multi_query_context(
            conn=conn,
            customer_id=customer_id,
            user_email=user_email,
            agent_type=agent_type,
            time_window_days=time_window_days,
            rerank_enabled=rerank_enabled,
        )

        # 3. Replace interaction_details, emails, and notes with RAG results
        rag_interactions = []
        rag_emails = []
        rag_notes = []

        for item in context_result.items:
            if item.source_type == "interaction":
                rag_interactions.append({
                    "interaction_id": item.source_id,
                    "customer_id": customer_id,
                    "content": item.text,
                    "type": item.metadata.get("type"),
                    "created_at": item.metadata.get("date"),
                    "rag_score": item.score,
                    "rag_category": item.metadata.get("retrieval_category"),
                })
            elif item.source_type == "email":
                rag_emails.append({
                    "email_id": item.source_id,
                    "customer_id": customer_id,
                    "subject": item.metadata.get("subject"),
                    "from_email": item.metadata.get("from_email"),
                    "to_email": item.metadata.get("to_email"),
                    "direction": item.metadata.get("direction"),
                    "body": item.text,
                    "created_at": item.metadata.get("date"),
                    "rag_score": item.score,
                    "rag_category": item.metadata.get("retrieval_category"),
                })
            elif item.source_type == "note":
                rag_notes.append({
                    "note_id": item.source_id,
                    "client_id": customer_id,
                    "body": item.text,
                    "title": item.metadata.get("title"),
                    "created_at": item.metadata.get("date"),
                    "rag_score": item.score,
                    "rag_category": item.metadata.get("retrieval_category"),
                })

        # Replace with RAG-ranked data
        comprehensive_data["interaction_details"] = rag_interactions
        comprehensive_data["crm_emails"] = rag_emails
        comprehensive_data["employee_client_notes"] = rag_notes

        # Update metrics
        comprehensive_data["summary_metrics"]["total_interactions"] = len(rag_interactions)
        comprehensive_data["summary_metrics"]["email_count"] = len(rag_emails)
        comprehensive_data["summary_metrics"]["notes_count"] = len(rag_notes)
        comprehensive_data["summary_metrics"]["rag_enabled"] = True
        comprehensive_data["summary_metrics"]["rag_retrieval_method"] = context_result.retrieval_method

        logger.info(
            f"RAG retrieval for customer {customer_id} ({agent_type}): "
            f"{len(rag_interactions)} interactions, {len(rag_emails)} emails, "
            f"{len(rag_notes)} notes (run_id={context_result.run_id})"
        )

    except Exception as e:
        logger.error(f"RAG retrieval failed for customer {customer_id}, using raw data: {e}")
        # On failure, comprehensive_data already has the raw SQL results

    return comprehensive_data


async def _retrieve_multi_query_context(
    conn: asyncpg.Connection,
    customer_id: int,
    user_email: str,
    agent_type: str,
    time_window_days: int,
    rerank_enabled: bool = True,
    base_max_items: int = 15,
    max_total_items: int = 25,
) -> ContextResult:
    """
    Multi-query retrieval with category-specific queries.

    Runs a base broad query (RRF only) for general coverage, plus
    agent-specific category queries (with optional reranking) in parallel.
    Deduplicates by source_id — base items take priority.
    """
    retriever = get_context_retriever()

    # Cache the base query embedding (static query, never changes)
    global _base_query_embedding_cache
    if _base_query_embedding_cache is None:
        _base_query_embedding_cache = await get_embedding_service().embed(_BASE_QUERY)

    common_kwargs = dict(
        conn=conn,
        customer_id=customer_id,
        user_email=user_email,
        max_items=50,
        time_window_days=time_window_days,
        max_per_source=50,
        semantic_weight=0.7,
        recency_weight=0.2,
        recency_decay_days=30,
    )

    category_queries = AGENT_CATEGORY_QUERIES.get(agent_type, DEFAULT_CATEGORY_QUERIES)

    # Helper for category queries
    async def _run_category_query(cat: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[ContextResult]]:
        try:
            result = await retriever.retrieve_context(
                query=cat["query"],
                rerank_enabled=rerank_enabled,
                rerank_top_n=cat["top_n"],
                tool_name=f"rag_{agent_type}_{cat['category']}",
                **common_kwargs,
            )
            return cat, result
        except Exception as e:
            logger.warning(f"Category query '{cat['category']}' failed: {e}")
            return cat, None

    # Run base + category queries sequentially (sharing the same conn)
    base_result = await retriever.retrieve_context(
        query=_BASE_QUERY,
        query_embedding=_base_query_embedding_cache,
        rerank_enabled=False,
        tool_name=f"rag_{agent_type}_base",
        **common_kwargs,
    )

    category_pairs = []
    for cat in category_queries:
        pair = await _run_category_query(cat)
        category_pairs.append(pair)

    # Deduplicate and merge — base items take priority
    seen = set()
    merged_items = []

    for item in base_result.items[:base_max_items]:
        key = (item.source_type, item.source_id)
        if key not in seen:
            seen.add(key)
            merged_items.append(item)

    for cat, cat_result in category_pairs:
        if cat_result is None:
            continue
        for item in cat_result.items:
            key = (item.source_type, item.source_id)
            if key not in seen:
                seen.add(key)
                item.metadata["retrieval_category"] = cat["category"]
                merged_items.append(item)

    # Sort by score and truncate
    merged_items.sort(key=lambda x: x.score, reverse=True)
    merged_items = merged_items[:max_total_items]

    base_count = sum(1 for item in merged_items if "retrieval_category" not in item.metadata)
    cat_count = len(merged_items) - base_count
    logger.info(
        f"Multi-query RAG for customer {customer_id} ({agent_type}): "
        f"{len(merged_items)} items ({base_count} base + {cat_count} from categories)"
    )

    return ContextResult(
        items=merged_items,
        run_id=base_result.run_id,
        retrieval_method="multi_query",
        query=f"multi_query:{agent_type}",
    )
