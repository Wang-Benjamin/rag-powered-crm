"""
CLI entry: ``python -m services.rag.evaluation``

Runs the full ablation panel against the golden case set on the tenant
DB pointed at by ``--dsn`` (or the ``CRM_EVAL_DSN`` env var) and prints
a markdown report to stdout.

This is intentionally a thin wrapper around ``runner.evaluate_ablation``
and ``report.format_markdown`` — see those modules for the work.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import List, Optional

import asyncpg

from services.rag.context_retriever import get_context_retriever
from services.rag.evaluation.configs import CONFIGS
from services.rag.evaluation.dataset import (
    GOLDEN_SET,
    default_goldens,
    load_jsonl_goldens,
)
from services.rag.evaluation.report import format_markdown
from services.rag.evaluation.runner import evaluate_ablation


async def _run(args: argparse.Namespace) -> int:
    if args.golden:
        cases = load_jsonl_goldens(Path(args.golden))
    else:
        cases = default_goldens() or GOLDEN_SET

    if not cases:
        print("no golden cases found", file=sys.stderr)
        return 1

    if args.configs:
        wanted = [c.strip() for c in args.configs.split(",") if c.strip()]
        unknown = [c for c in wanted if c not in CONFIGS]
        if unknown:
            print(f"unknown configs: {unknown}; known: {sorted(CONFIGS)}", file=sys.stderr)
            return 2
        configs = [CONFIGS[c] for c in wanted]
    else:
        configs = list(CONFIGS.values())

    if not args.dsn:
        print(
            "DSN required (pass --dsn postgres://... or set CRM_EVAL_DSN)",
            file=sys.stderr,
        )
        return 2

    conn = await asyncpg.connect(args.dsn)
    try:
        reports = await evaluate_ablation(conn, get_context_retriever(), cases, configs)
    finally:
        await conn.close()

    print(format_markdown(reports))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="services.rag.evaluation")
    p.add_argument(
        "--dsn",
        default=os.environ.get("CRM_EVAL_DSN"),
        help="Postgres DSN for the tenant DB (default: env CRM_EVAL_DSN)",
    )
    p.add_argument(
        "--golden",
        default=None,
        help="Path to a JSONL file or directory; defaults to services/rag/evaluation/golden/",
    )
    p.add_argument(
        "--configs",
        default=None,
        help="Comma-separated subset of CONFIGS to run (default: all)",
    )
    args = p.parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
