"""
Replay mode — re-run the last N production retrievals under a candidate
config and diff the resulting top-k vs. what shipped.

Reads from ``context_retrieval_runs`` (the audit table written by
``ContextRetriever.retrieve_context``) and feeds each (query, customer_id)
back through the retriever with a different config. Emits an added /
removed / reranked diff per run.

Replay is **regression-only** — it does not know what is *right*, only
what *changed*. Useful for catching unexpectedly large reorderings
before they ship, especially when there are no labeled goldens for the
queries in question.

CLI:

    uv run python -m services.rag.evaluation.replay --limit 50 --config rerank
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import asyncpg

from services.rag.context_retriever import ContextRetriever, get_context_retriever
from services.rag.evaluation.configs import CONFIGS, RetrieverConfig
from services.rag.evaluation.metrics import Ref
from services.rag.evaluation.runner import _refs_from_context_result


logger = logging.getLogger(__name__)


@dataclass
class ReplayDiff:
    run_id: int
    customer_id: int
    tool_name: str
    query: str
    original_top_k: int
    added: List[Tuple[Ref, int]]      # (ref, new_rank)
    removed: List[Tuple[Ref, int]]    # (ref, old_rank)
    reranked: int                     # count of refs that shifted >= 3 positions

    def render(self) -> str:
        lines = [
            f"run_id={self.run_id}  query={self.query!r}  tool={self.tool_name}"
        ]
        if self.added:
            joined = ", ".join(f"{st}#{sid} (rank {r})" for (st, sid), r in self.added[:5])
            extra = f" (+{len(self.added) - 5} more)" if len(self.added) > 5 else ""
            lines.append(f"  added:    {joined}{extra}")
        if self.removed:
            joined = ", ".join(f"{st}#{sid} (was rank {r})" for (st, sid), r in self.removed[:5])
            extra = f" (+{len(self.removed) - 5} more)" if len(self.removed) > 5 else ""
            lines.append(f"  removed:  {joined}{extra}")
        if self.reranked:
            lines.append(f"  reranked: {self.reranked} items shifted >=3 positions")
        if not (self.added or self.removed or self.reranked):
            lines.append("  (no change)")
        return "\n".join(lines)


def _refs_from_selected(selected_refs) -> List[Ref]:
    """Read a list of refs from the JSONB selected_refs column."""
    if isinstance(selected_refs, str):
        try:
            selected_refs = json.loads(selected_refs)
        except json.JSONDecodeError:
            return []
    if not isinstance(selected_refs, list):
        return []
    out: List[Ref] = []
    for item in selected_refs:
        st = item.get("source_type")
        sid = item.get("source_id")
        if st is None or sid is None:
            continue
        out.append((str(st), int(sid)))
    return out


def _diff(
    old_refs: Sequence[Ref],
    new_refs: Sequence[Ref],
    rerank_threshold: int = 3,
) -> Tuple[List[Tuple[Ref, int]], List[Tuple[Ref, int]], int]:
    old_rank: Dict[Ref, int] = {r: i + 1 for i, r in enumerate(old_refs)}
    new_rank: Dict[Ref, int] = {r: i + 1 for i, r in enumerate(new_refs)}
    added = [(r, new_rank[r]) for r in new_refs if r not in old_rank]
    removed = [(r, old_rank[r]) for r in old_refs if r not in new_rank]
    reranked = sum(
        1
        for r in new_refs
        if r in old_rank and abs(new_rank[r] - old_rank[r]) >= rerank_threshold
    )
    return added, removed, reranked


async def replay_recent(
    conn: asyncpg.Connection,
    retriever: ContextRetriever,
    config: RetrieverConfig,
    *,
    limit: int = 50,
    tool_name_filter: Optional[str] = None,
) -> List[ReplayDiff]:
    """Read the last ``limit`` rows from ``context_retrieval_runs`` and
    re-run each under ``config``.

    Rows whose ``tool_name`` starts with ``eval::`` (i.e. produced by
    this harness) are skipped to avoid feedback loops.
    """
    sql = """
        SELECT id, customer_id, tool_name, query, selected_refs
        FROM context_retrieval_runs
        WHERE query IS NOT NULL AND query <> ''
          AND tool_name NOT LIKE 'eval::%'
    """
    params: List = []
    if tool_name_filter:
        sql += " AND tool_name = $1"
        params.append(tool_name_filter)
    sql += " ORDER BY id DESC LIMIT $%d" % (len(params) + 1)
    params.append(limit)

    rows = await conn.fetch(sql, *params)

    diffs: List[ReplayDiff] = []
    for row in rows:
        old_refs = _refs_from_selected(row["selected_refs"])
        try:
            result = await retriever.retrieve_context(
                conn=conn,
                customer_id=row["customer_id"],
                query=row["query"],
                max_items=config.max_items,
                semantic_weight=config.semantic_weight,
                time_window_days=config.time_window_days,
                source_types=config.source_types,
                max_per_source=config.max_per_source,
                recency_weight=config.recency_weight,
                recency_decay_days=config.recency_decay_days,
                rerank_enabled=config.rerank_enabled,
                rerank_top_n=config.rerank_top_n,
                tool_name=f"eval::replay::{config.name}",
                user_email="eval@preludeos.local",
            )
        except Exception as e:
            logger.warning("replay failed for run_id=%s: %s", row["id"], e)
            continue
        new_refs = _refs_from_context_result(result)
        added, removed, reranked = _diff(old_refs, new_refs)
        diffs.append(
            ReplayDiff(
                run_id=row["id"],
                customer_id=row["customer_id"],
                tool_name=row["tool_name"] or "",
                query=row["query"] or "",
                original_top_k=len(old_refs),
                added=added,
                removed=removed,
                reranked=reranked,
            )
        )
    return diffs


async def _main_async(args: argparse.Namespace) -> None:
    if args.config not in CONFIGS:
        raise SystemExit(
            f"unknown config {args.config!r}; known: {sorted(CONFIGS)}"
        )
    if not args.dsn:
        raise SystemExit(
            "DSN required (pass --dsn postgres://... or set CRM_EVAL_DSN)."
        )
    conn = await asyncpg.connect(args.dsn)
    try:
        diffs = await replay_recent(
            conn,
            get_context_retriever(),
            CONFIGS[args.config],
            limit=args.limit,
            tool_name_filter=args.tool,
        )
    finally:
        await conn.close()
    for d in diffs:
        print(d.render())
        print()


def main(argv: Optional[Iterable[str]] = None) -> None:
    import os

    p = argparse.ArgumentParser(prog="services.rag.evaluation.replay")
    p.add_argument("--config", default="baseline", help="named config in CONFIGS")
    p.add_argument("--limit", type=int, default=50, help="number of recent runs to replay")
    p.add_argument("--tool", default=None, help="filter by tool_name (exact match)")
    p.add_argument(
        "--dsn",
        default=os.environ.get("CRM_EVAL_DSN"),
        help="Postgres DSN for the tenant DB (default: env CRM_EVAL_DSN)",
    )
    args = p.parse_args(list(argv) if argv is not None else None)
    asyncio.run(_main_async(args))


if __name__ == "__main__":
    main()
