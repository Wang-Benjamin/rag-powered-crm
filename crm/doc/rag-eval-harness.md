# RAG Eval Harness — Design Doc

Status: **Implemented (v1)** — phases 1–4 landed in `crm/services/rag/evaluation/`.
Owner: CRM service.
Related: [`crm/doc/rag_insight_workflow.md`](rag_insight_workflow.md) (pipeline reference).

---

## 1. Why

The CRM agents (`NextActionInsightAgent`, `RestartMomentumInsightAgent`, `IcebreakerIntroAgent`, `DealRetrospectiveAgent`) all consume the top-25 items returned by `get_rag_enhanced_customer_data()`. That retrieval step decides what evidence the LLM ever sees — if the right email is missing, the agent's output is wrong no matter how well the prompt is tuned.

Today there is **no harness** that answers:

- Did this retriever change improve or regress recall?
- What does reranking actually buy us?
- Are we getting the right evidence for `NextActionInsightAgent` vs. `IcebreakerIntroAgent`?
- Did backfilling note embeddings help?

Every retriever knob (`semantic_weight`, `recency_weight`, `recency_decay_days`, `rerank_enabled`, `max_per_source`) is currently tuned by intuition. A small offline harness closes that gap.

## 2. Scope

**In scope:** retrieval-quality evaluation. Inputs go in, ranked context items come out, we score them against a labeled set.

**Out of scope (for v1):** end-to-end LLM output quality (faithfulness, hallucination, answer relevancy). RAGAS/DeepEval-style evals are a v2 — they're slower, more expensive, and have higher variance. Retrieval-level metrics give us 80% of the signal at <1% of the cost.

## 3. Architecture

```
crm/services/rag/evaluation/
├── __init__.py               # public API
├── __main__.py               # python -m services.rag.evaluation
├── golden/
│   ├── README.md             # schema + how to add cases
│   ├── next_action.jsonl
│   ├── icebreaker.jsonl
│   ├── restart_momentum.jsonl
│   └── deal_retrospective.jsonl
├── runner.py                 # core eval loop, ablation driver
├── metrics.py                # recall@k, MRR, nDCG, violations, source_balance
├── configs.py                # named retriever configs (ablations)
├── dataset.py                # EvalCase + JSONL loader
├── judges.py                 # LLM-as-judge stubs (v2)
├── replay.py                 # replay from context_retrieval_runs
└── report.py                 # markdown report writer
```

Self-contained. No new runtime dependencies — uses `asyncpg` and the existing `context_retriever` module. The package is offline-only: nothing in `services/rag/__init__.py` or any router imports it, so importing it has no effect on running CRM behavior.

### 3.1 Golden case schema

One JSONL line per case:

```json
{
  "id": "next_action__customer_42__followup_q2",
  "agent_type": "NextActionInsightAgent",
  "customer_id": 42,
  "tenant_db": "preludeos_demo7",
  "query": "What follow-ups are pending?",
  "must_cite": [
    {"source_type": "email", "source_id": 1839},
    {"source_type": "interaction", "source_id": 221}
  ],
  "should_cite": [
    {"source_type": "email", "source_id": 1845}
  ],
  "must_not_cite": [
    {"source_type": "email", "source_id": 1102}
  ],
  "notes": "1102 is an old shipping notification; should never crowd out the meeting recap."
}
```

- `must_cite` — graded relevance 3 (counted in recall@k).
- `should_cite` — graded relevance 1 (counted in nDCG, not recall).
- `must_not_cite` — penalty if it appears in top-k.

The labeled IDs are **stable references to existing rows** in a fixed demo tenant DB. We do not snapshot the embeddings — we re-run them every time so the harness measures the *current* retriever against historical ground truth.

### 3.2 Runner contract

```python
# services/rag/evaluation/runner.py
async def run_case(
    case: GoldenCase,
    config: RetrieverConfig,
    conn: asyncpg.Connection,
) -> CaseResult:
    result = await get_context_retriever().retrieve_context(
        conn=conn,
        customer_id=case.customer_id,
        query=case.query,
        max_items=config.max_items,
        semantic_weight=config.semantic_weight,
        recency_weight=config.recency_weight,
        rerank_enabled=config.rerank_enabled,
        rerank_top_n=config.rerank_top_n,
        tool_name=f"eval::{config.name}",
        user_email="eval@preludeos.local",
    )
    return CaseResult(
        case_id=case.id,
        config=config.name,
        retrieved=[(i.source_type, i.source_id) for i in result.items],
        run_id=result.run_id,
    )
```

The runner calls the **production** `ContextRetriever`. No mocks, no shadow code path. Everything we score is what an agent would actually see.

### 3.3 Metrics (`metrics.py`)

| Metric | What it measures | Why we want it |
|--------|------------------|----------------|
| `recall@k` (k = 5, 10, 25) | Fraction of `must_cite` items that appear in top-k | Headline number. If this drops, agents get worse. |
| `MRR` | Mean reciprocal rank of the *first* `must_cite` hit | Catches "right answer is in top-25 but at position 24" — the LLM may truncate before reaching it. |
| `nDCG@25` | Graded ranking quality (uses `must_cite=3`, `should_cite=1`) | Picks up improvements that don't change recall but reorder the right things upward. |
| `precision_violations` | Count of `must_not_cite` items in top-25 | Negative signal — guards against regressions where junk crowds out signal. |
| `source_balance` | Distribution across interaction / email / note | Sanity check the diversity filter is doing its job. |

All metrics are reported per-agent and aggregated.

### 3.4 Named configs (`configs.py`)

```python
CONFIGS = {
    "baseline":        RetrieverConfig(semantic_weight=0.7, rerank_enabled=False),
    "semantic_only":   RetrieverConfig(semantic_weight=1.0, rerank_enabled=False),
    "keyword_only":    RetrieverConfig(semantic_weight=0.0, rerank_enabled=False),
    "rerank":          RetrieverConfig(semantic_weight=0.7, rerank_enabled=True),
    "high_recency":    RetrieverConfig(semantic_weight=0.7, recency_weight=0.4),
    "no_recency":      RetrieverConfig(semantic_weight=0.7, recency_weight=0.0),
}
```

A single CI run executes **all** configs against the golden set so every PR gets an ablation table for free. Total cost per run: ~40 cases × 6 configs × (1 embedding + 2 SQL queries) ≈ <$0.05 in OpenAI calls + a few seconds of Postgres.

### 3.5 Replay mode (`replay.py`)

`context_retrieval_runs` already stores `(query, retrieval_params, selected_refs)` for every production retrieval. Replay reads the last N rows, re-runs each query under the candidate config, and diffs the resulting top-25 vs. what production returned. Output:

```
run_id=8421  query="renegotiate price"  agent=NextActionInsightAgent
  added:    email#1839 (rank 4), interaction#221 (rank 11)
  removed:  email#1102 (was rank 8), email#1450 (was rank 19)
  reranked: 14 items shifted ≥3 positions
```

Replay is **regression-only** — it doesn't know what's right, just what changed. Useful for catching unexpectedly large reorderings before they ship.

## 4. Workflow

### 4.1 Authoring golden cases

1. Pick a customer in the demo tenant with rich history (≥30 emails, ≥5 meetings).
2. Pick an agent type and write a realistic query (or copy one from `AGENT_CATEGORY_QUERIES`).
3. Read the actual emails/interactions/notes for that customer.
4. Mark 1–3 items as `must_cite`, 0–3 as `should_cite`, 0–2 as `must_not_cite`.
5. Add a one-line `notes` field explaining the call. **The note is the contract** — when a case fails six months from now, the note tells the next person whether the case is still valid.

Initial target: **15–20 cases per agent** (≈75 total). Bias toward cases where the right answer is not the most recent email — those are where retrieval actually does work.

### 4.2 Running locally

```bash
cd crm
# Full ablation report (markdown to stdout)
uv run python -m services.rag.evaluation

# Replay last N production retrievals under a candidate config
uv run python -m services.rag.evaluation.replay --limit 50 --config rerank
```

### 4.3 In CI

Smoke-mode (subset, fast) on every PR that touches `services/rag/` or `data/queries/rag_queries.py`. Full ablation nightly. Reports posted to `docs/reviews/rag-eval/<date>.md` for trend-watching.

## 5. Pass / fail criteria (v1)

A retriever change is **green** if, against the full golden set:

- `recall@25` ≥ baseline − 1pp (per agent).
- `MRR` ≥ baseline − 0.02.
- `precision_violations` ≤ baseline.

A change is **shippable but flagged** if any of those slip and the diff explains why (e.g., we deliberately traded recall for diversity). The harness produces the table — humans decide whether the trade is worth it.

## 6. What this doesn't catch

Be honest about the limits:

- **No ground truth for novel queries.** The harness can't tell us if the retriever handles a query no one has ever asked.
- **Demo-tenant bias.** Real customers have messier data than `preludeos_demo7`. Plan to add 1–2 anonymized real-tenant snapshots in v2.
- **No LLM-output eval.** A retriever could pass every metric and still feed the LLM something that produces a bad insight. v2 layer (RAGAS-style) addresses this.
- **Embeddings drift.** If we change embedding models, every golden score shifts. That's fine — the *relative* ranking of configs is what matters, but treat absolute thresholds as model-version-scoped.

## 7. Implementation phases

| Phase | Deliverable | Effort |
|-------|-------------|--------|
| 1 | Folder + runner + 5 hand-written `next_action` cases + recall@k, MRR | 1 day |
| 2 | `configs.py` ablations + markdown report writer | 0.5 day |
| 3 | Expand to all 4 agents, ~75 cases | 1–2 days (mostly labeling) |
| 4 | Replay mode against `context_retrieval_runs` | 0.5 day |
| 5 | CI integration + nightly trend report | 0.5 day |

Phase 1 alone is enough to start gating PRs. Everything else is incremental.

## 8. Open questions

- Where do we store the demo-tenant DB snapshot? Pinning to `preludeos_demo7` works as long as we never bulk-delete from it — worth a one-line guard in the harness that skips runs if `must_cite` IDs no longer exist (and prints which ones are missing).
- Should `should_cite` items be auto-extracted from production `selected_refs` for popular queries? Cheap labels, but risk of fitting the harness to current behavior.
- Do we want per-source recall (recall on emails, recall on interactions) as separate headline metrics? Probably yes once `employee_client_notes` embeddings are backfilled and notes start showing up in results.

---

## Appendix: golden set seed (5 starter cases for `NextActionInsightAgent`)

To unblock phase 1, the first author should label these themselves against `preludeos_demo7`:

1. Customer with a recent meeting where the buyer asked for a revised quote — `must_cite` the meeting + the quote email.
2. Customer who has gone silent for 14 days after expressing interest — `must_cite` the last inbound; `must_not_cite` an unrelated bounce notification.
3. Customer mid-negotiation with three pricing emails — `must_cite` the latest, `should_cite` the prior two.
4. Customer where the relevant signal is in a meeting note, not an email — tests the (currently unembedded) notes path; will fail until backfill runs.
5. Customer with an old high-relevance email and a recent low-relevance email — tests `recency_weight`. The old email should still surface.
