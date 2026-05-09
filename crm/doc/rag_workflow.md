# RAG-Powered CRM — End-to-End Workflow

This is the honest, code-grounded view of how the system processes a request from
frontend to LLM output. The Lead and CRM paths share a frontend, FastAPI layer, and
Postgres+pgvector store, but their middle layers are intentionally different shapes:

- **Lead path** — small, structured, pre-curated corpus. The "intelligence" lives in
  domain scoring + LLM enrichment, not in retrieval. Search is a simple FTS filter
  on top of a hand-engineered 11-signal scoring pipeline.
- **CRM path** — large, unstructured, conversational corpus. Hybrid retrieval
  (dense + lexical → RRF → cross-encoder rerank) does the heavy lifting; generation
  is grounded in retrieved context.

## Diagram

![RAG workflow](rag_workflow.png)

<details>
<summary>Mermaid source (renders inline on GitHub / mermaid.live)</summary>

```mermaid
flowchart TB
    subgraph L1["1 — Frontend (Next.js)"]
        direction LR
        FE1[Lead Search]
        FE2[CRM Dashboard]
        FE3[Email Composer]
        FE4[Upload]
    end

    subgraph L2["2 — FastAPI Services"]
        direction LR
        API1[Lead Gen API]
        API2[CRM API]
    end

    L1 --> L2

    subgraph L3A["3a — Lead Processing Pipeline"]
        direction TB
        LP1["Filter & Search<br/>Postgres FTS to_tsvector(company)<br/>+ structured filters<br/>(industry, score range, country)"]
        LP2["Preliminary Scoring · top 500<br/>S2 + S4 + S6 + S7<br/>continuous curves, soft-clamp 80"]
        LP3["Contact Enrichment · top 50<br/>Apollo / Lemlist + cache<br/>email-domain validation"]
        LP4["Full Scoring · top 50<br/>S1–S11, hard-clamp 100<br/>11-signal trade intelligence"]
        LP5["LLM Insight (GPT-mini)<br/>buyer one-liner, cached<br/>+ real-company filter"]
        LP1 --> LP2 --> LP3 --> LP4 --> LP5
    end

    subgraph L3B["3b — CRM Hybrid Retrieval"]
        direction TB
        HR1["Dense<br/>pgvector cosine"]
        HR2["Lexical<br/>Postgres FTS → BM25*<br/>(rank_bm25 over top-N)"]
        HR3["RRF Fusion<br/>per-source weights<br/>notes / emails / interactions"]
        HR4["Recency boost<br/>+ diversity filter"]
        HR5["Cross-Encoder Rerank<br/>Cohere rerank-v3.5<br/>(optional, graceful fallback)"]
        HR1 --> HR3
        HR2 --> HR3
        HR3 --> HR4 --> HR5
    end

    API1 --> L3A
    API2 --> L3B

    subgraph L4["4 — PostgreSQL + pgvector (per tenant)"]
        direction LR
        DB1["Lead tables<br/>customs_records · company_profiles<br/>trade_summaries · personnel"]
        DB2["CRM tables<br/>interaction_details · employee_client_notes<br/>deal_history · KB"]
    end

    L3A --> DB1
    L3B --> DB2

    subgraph L5["5 — LLM Generation (GPT-4o)"]
        direction LR
        GEN1["Lead → cold outreach<br/>two-pager + AI email<br/>grounded in trade data + contact"]
        GEN2["CRM → follow-up + insights<br/>grounded in client history"]
    end

    L3A --> GEN1
    L3B --> GEN2

    EVAL[["Eval harness<br/>rag-eval-harness.md<br/>NDCG@k / MRR"]]
    EVAL -.tunes.-> L3B

    classDef new fill:#fff4d6,stroke:#c08a00,stroke-width:2px;
    class HR2 new;
```

</details>

`*` BM25 (highlighted in amber) is the only proposed addition not yet in code.
Everything else maps to existing files — see "Box → code" map below.

## Box → code map

### Lead Processing Pipeline (3a)

| Box | File(s) |
|---|---|
| Filter & Search | `leadgen/data/repositories/lead_repository.py:606-612` |
| Preliminary / Full Scoring | `leadgen/importyeti/domain/scoring.py` |
| Contact Enrichment | `leadgen/importyeti/services/lead_enrichment.py` |
| LLM Insight | `leadgen/importyeti/domain/insight.py` |
| Real-company filter | `leadgen/importyeti/reports/real_company_filter.py` |
| Two-pager + outreach | `leadgen/importyeti/reports/two_pager_service.py`, `reports/email_generator.py` |

### CRM Hybrid Retrieval (3b)

| Box | File(s) |
|---|---|
| Dense (pgvector cosine) | `crm/services/rag/context_retriever.py:236, 433` |
| Lexical (Postgres FTS, → BM25 proposed) | `crm/services/rag/context_retriever.py:251-253, 448-450` |
| RRF Fusion + per-source weights | `crm/services/rag/context_retriever.py:242-251, 459-469` (`source_type_weights`) |
| Recency boost + diversity filter | `crm/services/rag/context_retriever.py` |
| Cross-encoder rerank | `crm/services/rag/rerank_service.py:1-40` |
| Eval harness | `crm/doc/rag-eval-harness.md` |

## Why the two halves look different

The Lead corpus is a small, structured set of buyer records that's already
pre-scored on 11 trade-intelligence signals. Free-text search over it is mostly a
filter, not a ranker — the order is computed deterministically from domain
features. Throwing dense embeddings + BM25 + cross-encoders at it would replace a
deterministic, explainable ranking with a stochastic one for no measurable gain.

The CRM corpus is the opposite: thousands of free-text notes, emails, and
transcripts where queries are short and conversational. That's exactly where
hybrid retrieval + cross-encoder reranking earns its keep.

## Proposed change: BM25 on the lexical leg

The amber-highlighted box (`Lexical → BM25*`) is the only piece not yet in code.
The cheapest way to ship it is a Python-side `rank_bm25` re-score over the top-N
FTS candidates, slotted between the SQL fetch and RRF fusion. This keeps the
Postgres FTS path as the candidate generator (so no Docker/extension change), and
the eval harness can produce a real NDCG@k delta vs. the current `ts_rank_cd`
baseline.
