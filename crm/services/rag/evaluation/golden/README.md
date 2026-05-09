# Golden cases

Hand-labeled retrieval cases. One JSONL line per case. The runner loads
every `*.jsonl` file in this directory by default (see
`dataset.default_goldens()` and `dataset.load_jsonl_goldens()`).

## Schema

```json
{
  "id": "next_action__customer_42__followup_q2",
  "agent": "NextActionInsightAgent",
  "customer_id": 42,
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
  "ground_truth_answer": "optional, used only by judges.py (v2)",
  "notes": "1102 is an old shipping notification; should never crowd out the meeting recap."
}
```

- `must_cite` — graded relevance 3, drives `recall@k`.
- `should_cite` — graded relevance 1, drives nDCG only.
- `must_not_cite` — penalty if it appears in top-k.
- `notes` — **the contract.** When a case fails six months from now, this
  is what tells the next person whether the case is still valid.

## Authoring a case

1. Pick a customer in the demo tenant with rich history (≥30 emails, ≥5 meetings).
2. Pick an agent type and write a realistic query (or copy one from
   `AGENT_CATEGORY_QUERIES`).
3. Read the actual emails / interactions / notes for that customer.
4. Mark 1–3 items as `must_cite`, 0–3 as `should_cite`, 0–2 as `must_not_cite`.
5. Add a one-line `notes` explaining the call.

Bias toward cases where the right answer is **not** the most recent
email — those are where retrieval actually does work.

The IDs are stable references to existing rows in a fixed demo tenant
DB. Embeddings are not snapshotted — they are re-generated on each run
so the harness measures the *current* retriever against historical
ground truth.

## Files

| File | Agent |
| --- | --- |
| `next_action.jsonl` | `NextActionInsightAgent` |
| `icebreaker.jsonl` | `IcebreakerIntroAgent` |
| `restart_momentum.jsonl` | `RestartMomentumInsightAgent` |
| `deal_retrospective.jsonl` | `DealRetrospectiveAgent` |

The starter cases are seeds: target is 15–20 per agent (~75 total).
