"""
Markdown report writer for ablation runs.

Takes the list of ``EvalReport`` instances produced by
``runner.evaluate_ablation`` and renders the configs-x-metrics table
described in the design doc, plus per-agent breakdowns.

The output is plain GitHub-flavored markdown so it can be pasted into a
PR, committed under ``docs/reviews/rag-eval/<date>.md``, or piped through
``less``.
"""

from __future__ import annotations

from typing import Iterable, List, Sequence

from services.rag.evaluation.runner import EvalReport


_HEADLINE = (
    ("recall@10",   "recall_at_10",      ".2f"),
    ("recall@25",   "recall_at_25",      ".2f"),
    ("MRR",         "mrr",               ".2f"),
    ("nDCG@10",     "ndcg_at_10",        ".2f"),
    ("nDCG_g@25",   "ndcg_graded_at_25", ".2f"),
    ("viol@25",     "violations_at_25",  ".2f"),
)


def _row(name: str, agg: dict) -> str:
    cells = [name]
    for _, key, fmt in _HEADLINE:
        cells.append(format(agg.get(key, 0.0), fmt))
    return "| " + " | ".join(cells) + " |"


def _header() -> List[str]:
    head = ["config"] + [label for label, _, _ in _HEADLINE]
    return [
        "| " + " | ".join(head) + " |",
        "| " + " | ".join(["---"] * len(head)) + " |",
    ]


def format_markdown(reports: Sequence[EvalReport]) -> str:
    """Render a full ablation report. ``reports[0]`` is treated as
    baseline for the per-agent diff section."""
    if not reports:
        return "# RAG eval report\n\n_No reports — empty case set._\n"

    lines: List[str] = ["# RAG eval report", ""]
    lines.append(f"_Configs: {len(reports)} • Cases per config: {len(reports[0].per_case)}_")
    lines.append("")
    lines.append("## Aggregate (configs × metrics)")
    lines.append("")
    lines.extend(_header())
    for rep in reports:
        lines.append(_row(rep.config, rep.aggregate))
    lines.append("")

    agents = sorted({a for rep in reports for a in rep.by_agent})
    if agents:
        lines.append("## By agent")
        lines.append("")
        for agent in agents:
            lines.append(f"### {agent}")
            lines.append("")
            lines.extend(_header())
            for rep in reports:
                metrics = rep.by_agent.get(agent)
                if metrics is None:
                    continue
                lines.append(_row(rep.config, metrics))
            lines.append("")

    baseline = reports[0]
    lines.append("## Per-case results — baseline config")
    lines.append("")
    lines.append("| case_id | agent | hit@5 | recall@10 | mrr | nDCG@10 | viol@25 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for r in baseline.per_case:
        lines.append(
            f"| {r.case_id} | {r.agent} | {r.hit_at_5:.2f} | "
            f"{r.recall_at_10:.2f} | {r.mrr:.2f} | "
            f"{r.ndcg_at_10:.2f} | {int(r.violations_at_25)} |"
        )
    lines.append("")
    return "\n".join(lines)
