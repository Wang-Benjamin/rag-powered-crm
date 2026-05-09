"""
Golden evaluation dataset for the RAG retriever.

Held in code (and as JSONL on disk under ``golden/``) on purpose: this
stays under version control alongside the metrics that consume it, can
be diffed in PRs, and will not silently drift with tenant data.

Each EvalCase pins one query against a known customer_id together with
graded relevance labels:

  must_cite      gain=3, drives recall@k
  should_cite    gain=1, only drives nDCG
  must_not_cite  penalty if it shows up in top-k

A back-compat ``expected_refs`` field is preserved — when populated it
maps onto ``must_cite`` so older callers keep working. New cases should
use the graded fields.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence, Tuple

from services.rag.evaluation.metrics import Ref


GAIN_MUST_CITE: float = 3.0
GAIN_SHOULD_CITE: float = 1.0


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    customer_id: int
    query: str
    agent: str
    must_cite: Tuple[Ref, ...] = ()
    should_cite: Tuple[Ref, ...] = ()
    must_not_cite: Tuple[Ref, ...] = ()
    ground_truth_answer: Optional[str] = None
    notes: str = ""
    # Back-compat: older cases (dataset.py v1) populated this single field.
    # When non-empty and must_cite is empty, it is treated as must_cite.
    expected_refs: Tuple[Ref, ...] = ()

    def required_refs(self) -> Tuple[Ref, ...]:
        """Refs that count toward recall@k. Prefers must_cite; falls back
        to expected_refs for legacy cases."""
        return self.must_cite or self.expected_refs

    def gains(self) -> Dict[Ref, float]:
        """Map of ref -> gain value for graded nDCG."""
        out: Dict[Ref, float] = {}
        for r in self.required_refs():
            out[r] = GAIN_MUST_CITE
        for r in self.should_cite:
            out.setdefault(r, GAIN_SHOULD_CITE)
        return out


def _coerce_refs(items: Optional[Iterable]) -> Tuple[Ref, ...]:
    """Accept either [{"source_type": "email", "source_id": 42}, ...]
    or [["email", 42], ...] and return tuples of (str, int)."""
    if not items:
        return ()
    out = []
    for it in items:
        if isinstance(it, dict):
            out.append((str(it["source_type"]), int(it["source_id"])))
        else:
            st, sid = it
            out.append((str(st), int(sid)))
    return tuple(out)


def case_from_dict(raw: dict) -> EvalCase:
    """Build an EvalCase from a JSONL row. Tolerates both the new graded
    schema and the legacy ``expected_refs`` schema."""
    return EvalCase(
        case_id=str(raw["id"] if "id" in raw else raw["case_id"]),
        customer_id=int(raw["customer_id"]),
        query=str(raw["query"]),
        agent=str(raw.get("agent") or raw.get("agent_type") or ""),
        must_cite=_coerce_refs(raw.get("must_cite")),
        should_cite=_coerce_refs(raw.get("should_cite")),
        must_not_cite=_coerce_refs(raw.get("must_not_cite")),
        expected_refs=_coerce_refs(raw.get("expected_refs")),
        ground_truth_answer=raw.get("ground_truth_answer"),
        notes=str(raw.get("notes", "")),
    )


def load_jsonl_goldens(path: Path | str) -> Tuple[EvalCase, ...]:
    """Load every .jsonl file under ``path`` (or the single file at
    ``path``) into a tuple of EvalCases."""
    p = Path(path)
    files: Sequence[Path]
    if p.is_dir():
        files = sorted(p.glob("*.jsonl"))
    else:
        files = [p]
    cases = []
    for f in files:
        with f.open() as fh:
            for line_no, line in enumerate(fh, start=1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    cases.append(case_from_dict(json.loads(line)))
                except (KeyError, ValueError, json.JSONDecodeError) as e:
                    raise ValueError(
                        f"{f}:{line_no}: invalid golden case ({e})"
                    ) from e
    return tuple(cases)


GOLDEN_DIR: Path = Path(__file__).parent / "golden"


def default_goldens() -> Tuple[EvalCase, ...]:
    """Cases shipped under ``golden/``. Returns an empty tuple if the
    directory is missing — callers should fall back to ``GOLDEN_SET``."""
    if GOLDEN_DIR.exists():
        return load_jsonl_goldens(GOLDEN_DIR)
    return ()


# In-code seed set, kept for unit tests and as a fallback when the JSONL
# files are unreachable. Real labeling lives under ``golden/``.
GOLDEN_SET: Tuple[EvalCase, ...] = (
    EvalCase(
        case_id="next-action-001",
        customer_id=1,
        agent="NextActionInsightAgent",
        query="What did we last discuss with this customer about pricing?",
        must_cite=(
            ("email", 101),
            ("interaction", 55),
        ),
        ground_truth_answer=(
            "The most recent pricing discussion was an email exchange about"
            " the enterprise tier discount, followed by a discovery call"
            " where the customer requested a revised quote."
        ),
        notes="Pricing email should rank above the unrelated onboarding email.",
    ),
    EvalCase(
        case_id="restart-001",
        customer_id=2,
        agent="RestartMomentumInsightAgent",
        query="Open loops and unanswered questions from this customer",
        must_cite=(
            ("note", 12),
            ("email", 207),
        ),
        notes="Recency boost should pull the unread reply to the top.",
    ),
    EvalCase(
        case_id="icebreaker-001",
        customer_id=4,
        agent="IcebreakerIntroAgent",
        query="Recent industry context and talking points for this account",
        must_cite=(
            ("note", 88),
            ("interaction", 410),
        ),
    ),
    EvalCase(
        case_id="retro-001",
        customer_id=3,
        agent="DealRetrospectiveAgent",
        query="What objections did the customer raise during the sales cycle?",
        must_cite=(
            ("interaction", 312),
            ("interaction", 318),
            ("note", 44),
        ),
        ground_truth_answer=(
            "Two objections surfaced: integration cost with the existing"
            " billing system, and the lack of a data residency option in EU."
        ),
    ),
)
