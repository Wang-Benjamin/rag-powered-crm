"""
Context Retriever Service - Hybrid semantic + keyword search with RRF fusion.

Adapted for the CRM's multi-tenant PostgreSQL architecture (asyncpg).
Searches interaction_details, crm_emails, and employee_client_notes tables
scoped by customer_id using an asyncpg connection.
"""

import json
import math
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import asyncpg

from services.rag.embedding_service import get_embedding_service
from models.context_models import ContextItem, ContextResult, ContextSourceType, JSONEncoder

logger = logging.getLogger(__name__)


async def _register_vector(conn: asyncpg.Connection):
    """Register pgvector type with asyncpg connection."""
    from pgvector.asyncpg import register_vector
    await register_vector(conn)


class ContextRetriever:
    """
    Hybrid context retrieval for CRM agents.

    Combines semantic search (pgvector cosine similarity) with
    keyword search (PostgreSQL tsvector FTS) using Reciprocal Rank Fusion.
    """

    def __init__(self):
        self._embedding_service = None

    @property
    def embedding_service(self):
        if self._embedding_service is None:
            self._embedding_service = get_embedding_service()
        return self._embedding_service

    async def retrieve_context(
        self,
        conn: asyncpg.Connection,
        customer_id: int,
        query: str,
        max_items: int = 50,
        semantic_weight: float = 0.7,
        time_window_days: Optional[int] = None,
        source_types: Optional[List[str]] = None,
        max_per_source: int = 30,
        recency_weight: float = 0.2,
        recency_decay_days: int = 30,
        rerank_enabled: bool = False,
        rerank_top_n: int = 30,
        tool_name: str = "agent",
        query_embedding: Optional[List[float]] = None,
        user_email: str = "",
    ) -> ContextResult:
        """
        Retrieve relevant context for a customer using hybrid search.

        Args:
            conn: asyncpg connection for database access
            customer_id: Customer to retrieve context for
            query: Search query
            max_items: Maximum items to return
            semantic_weight: Weight for semantic vs keyword (0-1)
            time_window_days: Only include items from last N days
            source_types: Filter by source types (interaction, email, note)
            max_per_source: Max items per source type (diversity)
            recency_weight: Weight for recency vs relevance (0-0.5)
            recency_decay_days: Half-life for exponential recency decay
            rerank_enabled: Enable Cohere cross-encoder reranking
            rerank_top_n: Items to keep after reranking
            tool_name: Name of requesting tool (for audit)
            query_embedding: Pre-computed embedding to skip redundant API call
            user_email: For audit trail
        """
        effective_decay_days = recency_decay_days

        if not query:
            return ContextResult(items=[], run_id=0, retrieval_method="none")

        # Determine source types to search
        if source_types is None:
            source_types = [
                ContextSourceType.INTERACTION.value,
                ContextSourceType.EMAIL.value,
                ContextSourceType.NOTE.value,
            ]

        # Use pre-computed embedding or generate one
        if query_embedding is None:
            query_embedding = await self.embedding_service.embed(query)

        await _register_vector(conn)

        items = []

        # Search interactions (hybrid: semantic + keyword)
        if ContextSourceType.INTERACTION.value in source_types:
            interaction_items = await self._search_interactions(
                conn=conn,
                customer_id=customer_id,
                query=query,
                query_embedding=query_embedding,
                semantic_weight=semantic_weight,
                time_window_days=time_window_days,
                limit=max_items * 2,
            )
            items.extend(interaction_items)

        # Search emails (hybrid: semantic + keyword)
        if ContextSourceType.EMAIL.value in source_types:
            email_items = await self._search_emails(
                conn=conn,
                customer_id=customer_id,
                query=query,
                query_embedding=query_embedding,
                semantic_weight=semantic_weight,
                time_window_days=time_window_days,
                limit=max_items * 2,
            )
            items.extend(email_items)

        # Search notes (hybrid: semantic + keyword)
        if ContextSourceType.NOTE.value in source_types:
            note_items = await self._search_notes(
                conn=conn,
                customer_id=customer_id,
                query=query,
                query_embedding=query_embedding,
                semantic_weight=semantic_weight,
                time_window_days=time_window_days,
                limit=max_items,
            )
            items.extend(note_items)

        # Sort by score
        items.sort(key=lambda x: x.score, reverse=True)

        # Cross-encoder reranking (run in thread to avoid blocking event loop)
        if rerank_enabled and len(items) > 1:
            try:
                import asyncio
                from services.rag.rerank_service import get_rerank_service
                rerank_service = get_rerank_service()
                items = await asyncio.to_thread(
                    rerank_service.rerank,
                    query=query,
                    items=items,
                    top_n=rerank_top_n,
                )
            except Exception as e:
                logger.warning(f"Reranking failed, falling back to RRF scores: {e}")

        # Apply source-type weighting (after reranking so scores aren't overwritten)
        source_type_weights = {
            ContextSourceType.INTERACTION.value: 1.0,
            ContextSourceType.EMAIL.value: 0.95,  # Slightly lower than meetings/calls
            ContextSourceType.NOTE.value: 1.5,  # Boost notes since keyword scores are lower
        }
        for item in items:
            weight = source_type_weights.get(item.source_type, 1.0)
            item.score = item.score * weight

        # Apply diversity filter
        items = self._apply_diversity(items, max_per_source=max_per_source)

        # Apply recency boost
        if recency_weight > 0:
            if time_window_days and time_window_days > 90:
                effective_decay_days = max(recency_decay_days, time_window_days // 3)
            items = self._apply_recency_boost(items, recency_weight, effective_decay_days)

        # Limit to max_items
        items = items[:max_items]

        # Create audit trail
        run_id = await self._create_context_run(
            conn=conn,
            customer_id=customer_id,
            tool_name=tool_name,
            query=query,
            retrieval_params={
                "max_items": max_items,
                "semantic_weight": semantic_weight,
                "time_window_days": time_window_days,
                "source_types": source_types,
                "max_per_source": max_per_source,
                "recency_weight": recency_weight,
                "recency_decay_days": recency_decay_days,
                "effective_decay_days": effective_decay_days,
                "rerank_enabled": rerank_enabled,
            },
            selected_refs=[item.to_dict() for item in items],
            user_email=user_email,
        )

        return ContextResult(
            items=items,
            run_id=run_id,
            retrieval_method="smart",
            query=query,
        )

    async def _search_interactions(
        self,
        conn: asyncpg.Connection,
        customer_id: int,
        query: str,
        query_embedding: List[float],
        semantic_weight: float = 0.7,
        time_window_days: Optional[int] = None,
        limit: int = 40,
    ) -> List[ContextItem]:
        """Hybrid search on interaction_details using RRF fusion."""
        keyword_weight = 1 - semantic_weight

        time_filter = ""
        if time_window_days:
            time_filter = f"AND created_at >= NOW() - INTERVAL '{int(time_window_days)} days'"

        sql = f"""
            WITH semantic_search AS (
                SELECT
                    interaction_id,
                    content,
                    type,
                    created_at,
                    1 - (embedding <=> $1::vector) as semantic_score,
                    ROW_NUMBER() OVER (ORDER BY embedding <=> $1::vector) as semantic_rank
                FROM interaction_details
                WHERE embedding IS NOT NULL
                AND customer_id = $2
                {time_filter}
                ORDER BY embedding <=> $1::vector
                LIMIT 200
            ),
            keyword_search AS (
                SELECT
                    interaction_id,
                    content,
                    type,
                    created_at,
                    ts_rank_cd(text_search, plainto_tsquery('english', $3)) as keyword_score,
                    ROW_NUMBER() OVER (
                        ORDER BY ts_rank_cd(text_search, plainto_tsquery('english', $3)) DESC
                    ) as keyword_rank
                FROM interaction_details
                WHERE text_search @@ plainto_tsquery('english', $3)
                AND customer_id = $2
                {time_filter}
                ORDER BY keyword_score DESC
                LIMIT 200
            ),
            combined AS (
                SELECT
                    COALESCE(s.interaction_id, k.interaction_id) as interaction_id,
                    COALESCE(s.content, k.content) as content,
                    COALESCE(s.type, k.type) as type,
                    COALESCE(s.created_at, k.created_at) as created_at,
                    ($4::float * COALESCE(1.0/(60 + s.semantic_rank), 0)) +
                    ($5::float * COALESCE(1.0/(60 + k.keyword_rank), 0)) as rrf_score
                FROM semantic_search s
                FULL OUTER JOIN keyword_search k ON s.interaction_id = k.interaction_id
            )
            SELECT * FROM combined
            WHERE rrf_score > 0
            ORDER BY rrf_score DESC
            LIMIT $6
        """

        rows = await conn.fetch(sql,
            query_embedding,   # $1: semantic search embedding
            customer_id,       # $2: customer_id
            query,             # $3: keyword search query
            semantic_weight,   # $4: RRF semantic weight
            keyword_weight,    # $5: RRF keyword weight
            limit,             # $6: final LIMIT
        )

        return [
            ContextItem(
                source_type=ContextSourceType.INTERACTION.value,
                source_id=row['interaction_id'],
                text=row['content'] or '',
                score=float(row['rrf_score']),
                metadata={
                    "type": row.get('type'),
                    "date": row['created_at'].isoformat() if row.get('created_at') else None,
                }
            )
            for row in rows
        ]

    async def _search_emails(
        self,
        conn: asyncpg.Connection,
        customer_id: int,
        query: str,
        query_embedding: List[float],
        semantic_weight: float = 0.7,
        time_window_days: Optional[int] = None,
        limit: int = 40,
    ) -> List[ContextItem]:
        """Hybrid search on crm_emails using RRF fusion."""
        keyword_weight = 1 - semantic_weight

        time_filter = ""
        if time_window_days:
            time_filter = f"AND created_at >= NOW() - INTERVAL '{int(time_window_days)} days'"

        sql = f"""
            WITH semantic_search AS (
                SELECT
                    email_id,
                    subject,
                    body,
                    from_email,
                    to_email,
                    direction,
                    created_at,
                    1 - (embedding <=> $1::vector) as semantic_score,
                    ROW_NUMBER() OVER (ORDER BY embedding <=> $1::vector) as semantic_rank
                FROM crm_emails
                WHERE embedding IS NOT NULL
                AND customer_id = $2
                {time_filter}
                ORDER BY embedding <=> $1::vector
                LIMIT 200
            ),
            keyword_search AS (
                SELECT
                    email_id,
                    subject,
                    body,
                    from_email,
                    to_email,
                    direction,
                    created_at,
                    ts_rank_cd(text_search, plainto_tsquery('english', $3)) as keyword_score,
                    ROW_NUMBER() OVER (
                        ORDER BY ts_rank_cd(text_search, plainto_tsquery('english', $3)) DESC
                    ) as keyword_rank
                FROM crm_emails
                WHERE text_search @@ plainto_tsquery('english', $3)
                AND customer_id = $2
                {time_filter}
                ORDER BY keyword_score DESC
                LIMIT 200
            ),
            combined AS (
                SELECT
                    COALESCE(s.email_id, k.email_id) as email_id,
                    COALESCE(s.subject, k.subject) as subject,
                    COALESCE(s.body, k.body) as body,
                    COALESCE(s.from_email, k.from_email) as from_email,
                    COALESCE(s.to_email, k.to_email) as to_email,
                    COALESCE(s.direction, k.direction) as direction,
                    COALESCE(s.created_at, k.created_at) as created_at,
                    ($4::float * COALESCE(1.0/(60 + s.semantic_rank), 0)) +
                    ($5::float * COALESCE(1.0/(60 + k.keyword_rank), 0)) as rrf_score
                FROM semantic_search s
                FULL OUTER JOIN keyword_search k ON s.email_id = k.email_id
            )
            SELECT * FROM combined
            WHERE rrf_score > 0
            ORDER BY rrf_score DESC
            LIMIT $6
        """

        rows = await conn.fetch(sql,
            query_embedding,   # $1: semantic search embedding
            customer_id,       # $2: customer_id
            query,             # $3: keyword search query
            semantic_weight,   # $4: RRF semantic weight
            keyword_weight,    # $5: RRF keyword weight
            limit,             # $6: final LIMIT
        )

        return [
            ContextItem(
                source_type=ContextSourceType.EMAIL.value,
                source_id=row['email_id'],
                text=f"Subject: {row.get('subject') or '(no subject)'}\nFrom: {row.get('from_email', '')}\nTo: {row.get('to_email', '')}\nDirection: {row.get('direction', '')}\n\n{row.get('body') or ''}".strip(),
                score=float(row['rrf_score']),
                metadata={
                    "subject": row.get('subject'),
                    "from_email": row.get('from_email'),
                    "to_email": row.get('to_email'),
                    "direction": row.get('direction'),
                    "date": row['created_at'].isoformat() if row.get('created_at') else None,
                }
            )
            for row in rows
        ]

    async def _search_notes(
        self,
        conn: asyncpg.Connection,
        customer_id: int,
        query: str,
        query_embedding: Optional[List[float]] = None,
        semantic_weight: float = 0.7,
        time_window_days: Optional[int] = None,
        limit: int = 20,
    ) -> List[ContextItem]:
        """Hybrid search on employee_client_notes using RRF fusion.

        Falls back to keyword-only search if query_embedding is None.
        """
        time_filter = ""
        if time_window_days:
            time_filter = f"AND created_at >= NOW() - INTERVAL '{int(time_window_days)} days'"

        # Use hybrid search when embeddings are available
        if query_embedding is not None:
            keyword_weight = 1 - semantic_weight

            sql = f"""
                WITH semantic_search AS (
                    SELECT
                        note_id,
                        title,
                        body,
                        created_at,
                        1 - (embedding <=> $1::vector) as semantic_score,
                        ROW_NUMBER() OVER (ORDER BY embedding <=> $1::vector) as semantic_rank
                    FROM employee_client_notes
                    WHERE embedding IS NOT NULL
                    AND client_id = $2
                    {time_filter}
                    ORDER BY embedding <=> $1::vector
                    LIMIT 200
                ),
                keyword_search AS (
                    SELECT
                        note_id,
                        title,
                        body,
                        created_at,
                        ts_rank_cd(text_search, plainto_tsquery('english', $3)) as keyword_score,
                        ROW_NUMBER() OVER (
                            ORDER BY ts_rank_cd(text_search, plainto_tsquery('english', $3)) DESC
                        ) as keyword_rank
                    FROM employee_client_notes
                    WHERE text_search @@ plainto_tsquery('english', $3)
                    AND client_id = $2
                    {time_filter}
                    ORDER BY keyword_score DESC
                    LIMIT 200
                ),
                combined AS (
                    SELECT
                        COALESCE(s.note_id, k.note_id) as note_id,
                        COALESCE(s.title, k.title) as title,
                        COALESCE(s.body, k.body) as body,
                        COALESCE(s.created_at, k.created_at) as created_at,
                        ($4::float * COALESCE(1.0/(60 + s.semantic_rank), 0)) +
                        ($5::float * COALESCE(1.0/(60 + k.keyword_rank), 0)) as rrf_score
                    FROM semantic_search s
                    FULL OUTER JOIN keyword_search k ON s.note_id = k.note_id
                )
                SELECT * FROM combined
                WHERE rrf_score > 0
                ORDER BY rrf_score DESC
                LIMIT $6
            """

            rows = await conn.fetch(sql,
                query_embedding,   # $1: semantic search embedding
                customer_id,       # $2: client_id
                query,             # $3: keyword search query
                semantic_weight,   # $4: RRF semantic weight
                keyword_weight,    # $5: RRF keyword weight
                limit,             # $6: final LIMIT
            )

            return [
                ContextItem(
                    source_type=ContextSourceType.NOTE.value,
                    source_id=row['note_id'],
                    text=f"{row.get('title', '') or ''}\n\n{row.get('body', '') or ''}".strip(),
                    score=float(row['rrf_score']),
                    metadata={
                        "title": row.get('title'),
                        "date": row['created_at'].isoformat() if row.get('created_at') else None,
                    }
                )
                for row in rows
            ]

        # Keyword-only fallback
        sql = f"""
            SELECT
                note_id,
                title,
                body,
                created_at,
                ts_rank_cd(
                    text_search,
                    plainto_tsquery('english', $1)
                ) as score
            FROM employee_client_notes
            WHERE text_search @@ plainto_tsquery('english', $1)
            AND client_id = $2
            {time_filter}
            ORDER BY score DESC
            LIMIT $3
        """

        rows = await conn.fetch(sql, query, customer_id, limit)

        # Scale keyword-only scores to be comparable with RRF scores
        score_factor = 0.02
        return [
            ContextItem(
                source_type=ContextSourceType.NOTE.value,
                source_id=row['note_id'],
                text=f"{row.get('title', '') or ''}\n\n{row.get('body', '') or ''}".strip(),
                score=min(float(row['score']) * score_factor, score_factor),
                metadata={
                    "title": row.get('title'),
                    "date": row['created_at'].isoformat() if row.get('created_at') else None,
                }
            )
            for row in rows
        ]

    def _apply_diversity(
        self,
        items: List[ContextItem],
        max_per_source: int = 30,
    ) -> List[ContextItem]:
        """Apply diversity filter to avoid over-representation from one source type."""
        source_counts: Dict[str, int] = {}
        filtered_items = []

        for item in items:
            count = source_counts.get(item.source_type, 0)
            if count < max_per_source:
                filtered_items.append(item)
                source_counts[item.source_type] = count + 1

        return filtered_items

    def _apply_recency_boost(
        self,
        items: List[ContextItem],
        recency_weight: float,
        recency_decay_days: int,
    ) -> List[ContextItem]:
        """
        Apply multiplicative recency boost based on item age.

        score = relevance * (floor + (1 - floor) * e^(-days_old / decay))
        where floor = (1 - recency_weight)
        """
        now = datetime.now(timezone.utc)
        floor = 1.0 - recency_weight

        for item in items:
            date_str = item.metadata.get('date')

            if date_str:
                try:
                    item_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    days_old = max(0, (now - item_date).days)
                    recency_factor = math.exp(-days_old / recency_decay_days)
                except (ValueError, TypeError):
                    recency_factor = 0.5
            else:
                recency_factor = 0.5

            item.score = item.score * (floor + (1 - floor) * recency_factor)

        items.sort(key=lambda x: x.score, reverse=True)
        return items

    async def _create_context_run(
        self,
        conn: asyncpg.Connection,
        customer_id: int,
        tool_name: str,
        query: Optional[str],
        retrieval_params: Dict[str, Any],
        selected_refs: List[Dict[str, Any]],
        user_email: str,
    ) -> int:
        """Create an audit trail record for the context retrieval."""
        try:
            result = await conn.fetchrow(
                """
                INSERT INTO context_retrieval_runs (
                    customer_id, tool_name, query,
                    retrieval_params, selected_refs, user_email
                ) VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                customer_id,
                tool_name,
                query,
                json.loads(json.dumps(retrieval_params, cls=JSONEncoder)),
                json.loads(json.dumps(selected_refs, cls=JSONEncoder)),
                user_email,
            )
            return result['id'] if result else 0
        except Exception as e:
            logger.warning(f"Failed to create context run audit: {e}")
            return 0


# Singleton
_context_retriever: Optional[ContextRetriever] = None


def get_context_retriever() -> ContextRetriever:
    global _context_retriever
    if _context_retriever is None:
        _context_retriever = ContextRetriever()
    return _context_retriever
