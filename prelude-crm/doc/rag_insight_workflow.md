# How RAG Generates Better Insights

## The Problem Without RAG

Before RAG, the system worked like this:

```
get_comprehensive_customer_data(customer_id)
    |
    v
SELECT * FROM interaction_details WHERE customer_id = X    --> ALL meetings/calls (could be 500+)
SELECT * FROM employee_client_notes WHERE client_id = X    --> ALL notes
SELECT * FROM deals WHERE client_id = X                    --> ALL deals
    |
    v
Dump everything into agent prompt
    |
    v
Agent tries to find relevant info in a sea of data
```

**Problems:**
1. Emails were completely missing (stored in `crm_emails`, never queried)
2. ALL interactions dumped regardless of relevance — a meeting from 6 months ago has equal weight as yesterday's call
3. Token limits wasted on irrelevant old data, leaving less room for the LLM to reason
4. Agent gets overwhelmed with noise, produces generic insights

## The Solution With RAG

RAG retrieves only the **most relevant** content for each specific agent's task, from **all three data sources** (meetings/calls, emails, notes).

---

## Complete Workflow: Step by Step

### Step 1: User Requests Insight

**Trigger:** User clicks "Generate Insight" for Customer X in the CRM UI.

**Input:**
```
POST /api/interaction-summaries
{
    "customer_id": 42
}
```

**Output:** Request routed to `interaction_router.py`

---

### Step 2: Agent Selection

**File:** `interaction_router.py` -> `insights_queries.py:analyze_customer_activity()`

**Input:** `customer_id = 42`

**Logic:** Queries `interaction_details` and `deals` to classify the customer:
```sql
-- Count interactions in last 14 days
SELECT COUNT(*) as interactions_last_14_days FROM interaction_details
WHERE customer_id = 42 AND created_at >= NOW() - INTERVAL '14 days'

-- Check deal status
SELECT COUNT(*) as deal_count,
       COUNT(CASE WHEN stage NOT IN ('Closed-Lost','Closed-Won') THEN 1 END) as active_deal_count
FROM deals WHERE client_id = 42
```

**Decision tree:**
```
No deals at all?                    --> IcebreakerIntroAgent
Has deals but none active?          --> DealRetrospectiveAgent
Active deals + interactions < 14d?  --> RestartMomentumInsightAgent
Active deals + interactions >= 14d? --> NextActionInsightAgent
```

**Output:** `selected_agent_name = "NextActionInsightAgent"`

---

### Step 3: RAG-Enhanced Data Retrieval

**File:** `rag_queries.py:get_rag_enhanced_customer_data()`

**Input:**
```python
customer_id = 42
agent_type = "NextActionInsightAgent"
time_window_days = 30
```

This step has two sub-steps:

#### Step 3a: Get Structured Data (unchanged from before)

**File:** `insights_queries.py:get_comprehensive_customer_data()`

Fetches structured metadata that doesn't need relevance ranking:

```sql
SELECT * FROM clients WHERE client_id = 42
SELECT * FROM deals WHERE client_id = 42
```

**Output:**
```python
{
    "client_info": {"name": "Acme Corp", "industry": "SaaS", ...},
    "client_details": {"contract_value": 50000, "health_score": 0.8, ...},
    "deals": [{"deal_name": "Enterprise Plan", "stage": "Negotiation", ...}],
}
```

#### Step 3b: Multi-Query RAG Retrieval

**File:** `rag_queries.py:_retrieve_multi_query_context()`

Instead of one generic query, the system runs **6 parallel queries** tailored to what NextActionInsightAgent needs:

**Input:** Agent type determines the queries:
```python
# Base query (broad coverage, no reranking)
"relationship status communication updates progress"

# 5 category queries (with Cohere reranking)
"What recent meetings, calls, and communications happened with this client?"
"What follow-ups, tasks, or next steps are pending or waiting for a response?"
"How are current deals progressing? What milestones or stage changes occurred?"
"What issues, complaints, or concerns has the client raised recently?"
"What upsell, expansion, or new business opportunities exist with this client?"
```

Each query goes through the **Hybrid Search Pipeline** (Step 4 below), all running in parallel via `asyncio.gather()`.

**Output after deduplication and merge:**
```python
ContextResult(
    items=[
        ContextItem(source_type="email", source_id=891, text="Subject: Q2 Contract...", score=0.92, ...),
        ContextItem(source_type="interaction", source_id=234, text="Meeting notes: discussed...", score=0.87, ...),
        ContextItem(source_type="email", source_id=445, text="Subject: Re: Pricing...", score=0.81, ...),
        ContextItem(source_type="note", source_id=67, text="Client mentioned budget...", score=0.76, ...),
        # ... up to 25 most relevant items from all 3 sources
    ],
    retrieval_method="multi_query"
)
```

---

### Step 4: Hybrid Search Pipeline (per query)

**File:** `context_retriever.py:retrieve_context()`

Each of the 6 queries from Step 3b goes through this pipeline. Shown for one query:

**Input:**
```python
query = "What follow-ups, tasks, or next steps are pending?"
customer_id = 42
user_email = "rep@company.com"  # for multi-tenant DB routing
```

#### Step 4a: Query Embedding

**File:** `embedding_service.py:embed()`

**Input:** `"What follow-ups, tasks, or next steps are pending?"`

**Process:** Calls OpenAI `text-embedding-3-small` API

**Output:** `[0.0123, -0.0456, 0.0789, ...]` — 1536-dimensional vector

#### Step 4b: Search interaction_details (meetings/calls)

**Input:** Query vector + query text + customer_id

**Process:** Single SQL query with two CTEs joined by RRF:

```sql
-- CTE 1: Semantic search (finds conceptually similar content)
WITH semantic_search AS (
    SELECT interaction_id, content, type, created_at,
           1 - (embedding <=> query_vector::vector) as semantic_score,
           ROW_NUMBER() OVER (ORDER BY embedding <=> query_vector::vector) as semantic_rank
    FROM interaction_details
    WHERE embedding IS NOT NULL AND customer_id = 42
    LIMIT 200
),
-- CTE 2: Keyword search (finds exact term matches)
keyword_search AS (
    SELECT interaction_id, content, type, created_at,
           ts_rank_cd(text_search, plainto_tsquery('english', 'follow-ups tasks next steps pending')) as keyword_score,
           ROW_NUMBER() OVER (ORDER BY ts_rank_cd(...) DESC) as keyword_rank
    FROM interaction_details
    WHERE text_search @@ plainto_tsquery('english', 'follow-ups tasks next steps pending')
    AND customer_id = 42
    LIMIT 200
),
-- Fuse with Reciprocal Rank Fusion
combined AS (
    SELECT *,
           (0.7 * COALESCE(1.0/(60 + semantic_rank), 0)) +
           (0.3 * COALESCE(1.0/(60 + keyword_rank), 0)) as rrf_score
    FROM semantic_search s FULL OUTER JOIN keyword_search k ON s.interaction_id = k.interaction_id
)
SELECT * FROM combined WHERE rrf_score > 0 ORDER BY rrf_score DESC
```

**Output:** Ranked list of meetings/calls:
```
interaction_id=234  "Call: Discussed Q2 timeline, client asked for follow-up proposal"   rrf=0.0142
interaction_id=189  "Meeting: Reviewed deliverables, 3 action items assigned"            rrf=0.0128
interaction_id=301  "Call: Weekly sync, no blockers mentioned"                            rrf=0.0095
```

#### Step 4c: Search crm_emails

**Input:** Same query vector + query text + customer_id

**Process:** Same hybrid search pattern on `crm_emails` table:

```sql
WITH semantic_search AS (
    SELECT email_id, subject, body, from_email, to_email, direction, created_at,
           1 - (embedding <=> query_vector::vector) as semantic_score,
           ROW_NUMBER() OVER (ORDER BY embedding <=> query_vector::vector) as semantic_rank
    FROM crm_emails
    WHERE embedding IS NOT NULL AND customer_id = 42
    LIMIT 200
),
keyword_search AS (
    -- same pattern with ts_rank_cd on text_search column
),
combined AS (
    -- same RRF fusion
)
```

**Output:** Ranked list of emails:
```
email_id=891  "Subject: Re: Q2 Contract Renewal - still waiting on legal review"     rrf=0.0156
email_id=445  "Subject: Action items from Tuesday meeting"                            rrf=0.0131
email_id=567  "Subject: FYI - competitor pricing update"                              rrf=0.0089
```

#### Step 4d: Search employee_client_notes

**Input:** Query text + customer_id (keyword-only, no embeddings)

**Process:**
```sql
SELECT note_id, title, body, created_at,
       ts_rank_cd(text_search, plainto_tsquery('english', 'follow-ups tasks next steps pending')) as score
FROM employee_client_notes
WHERE text_search @@ plainto_tsquery('english', 'follow-ups tasks next steps pending')
AND client_id = 42
```

**Output:** Ranked notes:
```
note_id=67  "Client mentioned budget freeze until Q3, follow up after April board meeting"   score=0.008
```

#### Step 4e: Source-Type Weighting

**Input:** All items from 4b + 4c + 4d

**Process:** Apply multipliers to normalize across source types:
```python
interaction score *= 1.0    # meetings/calls are high-value
email score      *= 0.95   # emails slightly lower
note score       *= 1.5    # boost notes (keyword scores are inherently lower)
```

**Output:** All items in a single list, sorted by weighted score

#### Step 4f: Cohere Cross-Encoder Reranking (category queries only)

**Input:** Top 50 items from Step 4e + original query text

**Process:** Sends (query, document) pairs to Cohere `rerank-v3.5` API. The cross-encoder reads both the query and document together with full attention, producing a true relevance score (0-1).

```python
cohere.rerank(
    model="rerank-v3.5",
    query="What follow-ups, tasks, or next steps are pending?",
    documents=["Subject: Re: Q2 Contract Renewal...", "Call: Discussed Q2 timeline...", ...],
    top_n=5
)
```

**Why this matters:** Bi-encoder embeddings compare query and document independently. Cross-encoder sees them together — catches nuances like "the document mentions 'waiting on legal' which IS a pending follow-up even though it doesn't use the word 'follow-up'."

**Output:** Top 5 items re-scored with cross-encoder relevance:
```
email_id=891   relevance=0.94  "Subject: Re: Q2 Contract Renewal - still waiting on legal review"
interaction=234 relevance=0.87  "Call: Discussed Q2 timeline, client asked for follow-up proposal"
email_id=445   relevance=0.82  "Subject: Action items from Tuesday meeting"
note_id=67     relevance=0.71  "Client mentioned budget freeze until Q3..."
interaction=189 relevance=0.65  "Meeting: Reviewed deliverables, 3 action items assigned"
```

#### Step 4g: Diversity Filter

**Input:** Reranked items

**Process:** Cap items per source type (default 30) to prevent one type from dominating.

**Output:** Balanced mix of emails, meetings/calls, and notes

#### Step 4h: Recency Boost

**Input:** Diversity-filtered items

**Process:** Multiply scores by time decay:
```
boosted_score = score * (0.8 + 0.2 * e^(-days_old / 30))

Example:
  Today's email (0 days):     0.94 * (0.8 + 0.2 * 1.00) = 0.94 * 1.00 = 0.940
  Last week's call (7 days):  0.87 * (0.8 + 0.2 * 0.79) = 0.87 * 0.96 = 0.835
  Month-old note (30 days):   0.71 * (0.8 + 0.2 * 0.37) = 0.71 * 0.87 = 0.618
```

**Output:** Items re-sorted by time-boosted scores

---

### Step 5: Merge Multi-Query Results

**File:** `rag_queries.py:_retrieve_multi_query_context()`

**Input:** Results from 6 parallel queries (1 base + 5 category)

**Process:**
1. Take top 15 items from base query (broad coverage)
2. For each category query, add items not already seen (deduplicate by source_id)
3. Tag category items with their retrieval category (e.g., `"retrieval_category": "action_items"`)
4. Sort merged list by score, truncate to 25 items

**Output:**
```python
ContextResult(
    items=[25 most relevant items across all queries and all 3 data sources],
    retrieval_method="multi_query"
)
```

---

### Step 6: Build Agent Input

**File:** `rag_queries.py:get_rag_enhanced_customer_data()`

**Input:** Structured data (Step 3a) + RAG context (Step 5)

**Process:** Split RAG items back into source-type buckets:

```python
for item in context_result.items:
    if item.source_type == "interaction":
        rag_interactions.append({...})
    elif item.source_type == "email":
        rag_emails.append({...})
    elif item.source_type == "note":
        rag_notes.append({...})
```

**Output:** Same dict structure agents expect, but with relevance-ranked content:
```python
{
    "client_info": {"name": "Acme Corp", ...},           # from SQL (unchanged)
    "client_details": {"contract_value": 50000, ...},    # from SQL (unchanged)
    "deals": [{"deal_name": "Enterprise Plan", ...}],    # from SQL (unchanged)
    "interaction_details": [                              # RAG-ranked meetings/calls
        {"interaction_id": 234, "content": "Call: Discussed Q2 timeline...", "rag_score": 0.87},
        {"interaction_id": 189, "content": "Meeting: Reviewed deliverables...", "rag_score": 0.65},
    ],
    "crm_emails": [                                      # RAG-ranked emails (NEW)
        {"email_id": 891, "subject": "Re: Q2 Contract Renewal", "body": "...", "rag_score": 0.94},
        {"email_id": 445, "subject": "Action items from Tuesday", "body": "...", "rag_score": 0.82},
    ],
    "employee_client_notes": [                            # RAG-ranked notes
        {"note_id": 67, "title": "Budget freeze note", "body": "...", "rag_score": 0.71},
    ],
    "summary_metrics": {
        "total_interactions": 2,
        "email_count": 2,
        "notes_count": 1,
        "rag_enabled": True,
        "rag_retrieval_method": "multi_query"
    }
}
```

---

### Step 7: Agent Processes Data

**File:** e.g., `next_action_insight_agent.py`

**Input:** The dict from Step 6

**Process:** The agent runs two sub-analyses in parallel:

```python
# Thread 1: Email analysis
email_agent.analyze_email_communications(
    client_history.get("crm_emails", []),     # <-- RAG-ranked emails
    client_id,
    analysis_focus="comprehensive"
)

# Thread 2: Note analysis
note_agent.analyze_client_notes(
    client_history.get("employee_client_notes", []),  # <-- RAG-ranked notes
    client_id
)
```

The agent also directly reads `interaction_details` (RAG-ranked meetings/calls) and `deals` to build its prompt.

**The agent builds a prompt like:**
```
=== CLIENT NEXT ACTION ANALYSIS ===
Company: Acme Corp
Activity Status: active
Recent Interactions (Last 7 Days): 2

=== RECENT EMAIL COMMUNICATIONS ===
[Email analysis from email_agent — now has actual email data]

=== EMPLOYEE NOTES ===
[Note analysis from note_agent — relevance-ranked]

=== RECENT ACTIVITY DETAILS ===
[RAG-ranked meetings and calls]

=== DEAL PIPELINE ===
[Deal data from SQL]
```

**Output:** Agent sends prompt to OpenAI and gets structured JSON:
```json
{
    "activities": [...],
    "insights": [
        {
            "category": "Follow-Up Required",
            "insight": "Q2 contract renewal is blocked on legal review (email from March 12). Client's budget freeze lifts after April board meeting. Propose scheduling a pricing review call for early May."
        }
    ],
    "next_move": {
        "priority": "high",
        "action": "Send follow-up to legal team and schedule May pricing review",
        "rationale": "Contract renewal window closes in 6 weeks..."
    }
}
```

---

## Why This Produces Better Insights

### Before RAG
```
Agent input: 500 interactions (all meetings/calls, no emails) + 20 notes
             Most of it irrelevant old data
             Zero email content

Agent output: "Consider following up with the client about recent discussions."
              (generic, no specifics, misses email context entirely)
```

### After RAG
```
Agent input: 10 most relevant meetings/calls + 8 most relevant emails + 5 most relevant notes
             Each item selected because it matches what the agent needs
             Email content provides the richest context

Agent output: "Q2 contract renewal is blocked on legal review (email from March 12).
              Client's budget freeze lifts after April board meeting.
              Propose scheduling a pricing review call for early May."
              (specific, actionable, grounded in actual email + meeting + note content)
```

### Specific improvements:

| Dimension | Before | After |
|-----------|--------|-------|
| Email context | Missing entirely | RAG-ranked relevant emails from `crm_emails` |
| Data volume | ALL 500+ interactions dumped | Top 25 most relevant items |
| Relevance | Random (time-ordered dump) | Semantic + keyword + cross-encoder ranked |
| Specificity | Generic advice | Cites specific emails, dates, action items |
| Multi-aspect | Single data stream | 5 targeted queries per agent (action items, concerns, opportunities, etc.) |
| Recency | Old data has equal weight | Exponential decay boosts recent items |
| Balance | Only meetings/calls | Balanced mix of emails, meetings, calls, notes |
| Email quality | N/A (no emails) | Pre-cleaned before embedding — quotes, greetings, signatures stripped |

---

## Data Source Coverage

| Source | Table | Search Method | Embedding | What It Contains |
|--------|-------|---------------|-----------|------------------|
| Meetings/Calls | `interaction_details` | Hybrid (semantic + keyword + RRF) | text-embedding-3-small (1536d) | Meeting notes, call summaries, deal activities |
| Emails | `crm_emails` | Hybrid (semantic + keyword + RRF) | text-embedding-3-small (1536d) | Sent + received emails with subject, body, from/to, direction, thread |
| Notes | `employee_client_notes` | Keyword only (tsvector FTS) | Not yet | Manual employee notes about customers |
| Deals | `deals` | Direct SQL (no RAG) | N/A | Deal metadata passed through unchanged |
| Client Info | `clients` | Direct SQL (no RAG) | N/A | Company metadata passed through unchanged |

---

## Embedding Write Path (How Embeddings Are Generated)

The retrieval pipeline above assumes embeddings already exist. Here is how they get created.

### Real-Time Embedding

Every time a new record is created (email sent, meeting logged, note saved), the corresponding router fires a **fire-and-forget** embedding call:

```
Router creates record in DB
    |
    v
asyncio.create_task(embed_single_email/interaction/note(...))
    |
    v
embedding_sync_service generates embedding via OpenAI
    |
    v
UPDATE table SET embedding = %s WHERE id = %s
```

**Files involved:**
- `routers/email_router.py`, `calendar_sync_router.py`, `call_summary_router.py`, `deal_activities_router.py`, `meetings_router.py`, `notes_router.py` — trigger embedding after record creation
- `services/embedding_sync_service.py` — `embed_single_email()`, `embed_single_interaction()`, `embed_single_note()`

### Bulk Backfill

For existing records with no embedding, the admin endpoint triggers a batch backfill:

```
POST /api/crm/rag/backfill
    |
    v
populate_interaction_embeddings()  \
populate_email_embeddings()         } — run for the tenant
populate_note_embeddings()         /
    |
    v
Finds rows WHERE embedding IS NULL, batch-embeds via OpenAI, writes back
```

### Email Pre-Cleaning

**File:** `embedding_sync_service.py:clean_email_for_embedding()`

Before generating an embedding for an email, the body is **pre-cleaned** to remove noise that would dilute the semantic vector. This happens in both the real-time and backfill paths.

**What gets removed:**

| Pattern | Example | Why |
|---------|---------|-----|
| Quoted replies | `> On Mar 12, John wrote:` and `> previous message text` | Already embedded separately; duplicates distort similarity |
| Forwarded headers | `---- Original Message ----` | Structural noise, no semantic value |
| Greetings | `Hi John,`, `Dear team,`, `Good morning,` | Generic filler, matches too many unrelated emails |
| Signatures | `Best regards,` + everything after | Contact info, legal disclaimers — not relevant to intent |
| HTML remnants | `<div>`, `<br>`, `<p>` | Leftover tags from rich-text emails |
| Excess whitespace | Multiple blank lines | Normalizes spacing after removal |

**Example:**

```
Before cleaning:
  "Hi Sarah,\n\nJust following up on the Q2 pricing discussion. We can offer\n
   a 15% volume discount if the contract is signed by April 30.\n\nBest regards,\n
   Mike\nSales Director\nAcme Corp\n+1-555-0123"

After cleaning:
  "Just following up on the Q2 pricing discussion. We can offer\n
   a 15% volume discount if the contract is signed by April 30."
```

The embedding now captures only the **actionable content** — the pricing offer and deadline — without noise from greetings or signature blocks that would cause false similarity matches with other emails.

---

## Agent-Specific Query Design

Each agent type gets queries tailored to its task. This is critical — a "next action" agent needs different context than a "restart momentum" agent.

### NextActionInsightAgent
For active customers with recent interactions and deals. Needs: what's happening now, what's next.

| Query | Purpose | Why It Helps |
|-------|---------|--------------|
| Base: "relationship status communication updates progress" | Broad coverage | Catches general relationship signals |
| "What recent meetings, calls, and communications happened?" | Recent activities | Grounds the insight in actual events |
| "What follow-ups, tasks, or next steps are pending?" | Action items | Identifies what needs to happen next |
| "How are current deals progressing? What milestones occurred?" | Deal progress | Connects insights to revenue impact |
| "What issues, complaints, or concerns has the client raised?" | Concerns | Flags risks the rep should address |
| "What upsell or expansion opportunities exist?" | Opportunities | Identifies growth potential |

### RestartMomentumInsightAgent
For inactive customers needing re-engagement. Needs: what happened before, why they went quiet, how to restart.

| Query | Purpose | Why It Helps |
|-------|---------|--------------|
| Base: "relationship status communication updates progress" | Broad coverage | Understand the overall state |
| "What was the last meaningful interaction?" | Last engagement | Know where things left off |
| "What positive outcomes or wins were achieved?" | Previous wins | Leverage past successes |
| "What promises or commitments are still unresolved?" | Open loops | Use unfinished business as re-entry |
| "What is the current status of active deals?" | Deal status | Understand commercial context |
| "What topics could serve as a reason to re-engage?" | Restart hooks | Provide specific conversation starters |

### IcebreakerIntroAgent
For new prospects with no deal history. Needs: background, talking points.

| Query | Purpose | Why It Helps |
|-------|---------|--------------|
| Base: "relationship status communication updates progress" | Any existing context | Avoid cold-starting if some data exists |
| "What is known about this company's industry and market?" | Industry context | Industry-relevant talking points |
| "What background information exists about this company?" | Company background | Personalize the approach |
| "What potential conversation starters or relevant news?" | Talking points | Specific icebreaker material |

### DealRetrospectiveAgent
For customers with closed deals (no active ones). Needs: what happened, lessons learned.

| Query | Purpose | Why It Helps |
|-------|---------|--------------|
| Base: "relationship status communication updates progress" | Broad coverage | Overall relationship picture |
| "What were the final outcomes of completed deals?" | Deal outcomes | Win/loss analysis |
| "What lessons or process insights emerged?" | Lessons learned | Improve future approach |
| "What strategies contributed to successful outcomes?" | What worked | Repeat winning patterns |
| "What obstacles or mistakes led to lost deals?" | What failed | Avoid past mistakes |
