# Document Ingestion Feature — Plan

Author: onboarding team
Status: Draft, pending review
Scope: `prelude-user-settings` service + onboarding wizard on `prelude-frontend-next`
Related: `EMAIL_SIGNATURE_FEATURE_PLAN.md`, `CS510_Project_Proposal.md`

---

## 1. Goal

Let a user drop a document at any step of the factory-onboarding wizard and have the relevant form pre-filled automatically. The user still reviews and edits before anything is saved. This replaces the current experience where every company profile, product, and certification field is typed by hand.

The feature is framed as **"upload-to-autofill"**, not a separate ingestion system. Every ingestion lane lands on an existing commit target (`tenant_subscription.company_profile`, `factory_certifications`, a new `product_catalog` table).

## 2. Non-goals

- Not a general RAG knowledge-base ingester. That is a separate concern in the CS510 proposal and belongs in the CRM service.
- Not bulk/admin ingestion. One user, one upload at a time.
- Not real-time streaming extraction. Extraction runs asynchronously and the user polls.
- Not a replacement for the existing manual form. The form stays; uploads are a shortcut.

## 3. User stories

1. **New factory signs up.** They have a company profile PDF ready. They drop it into step 1 of the wizard, wait 10–30 seconds, see the company name, description, year founded, certifications-mentioned-in-prose, and factory location pre-filled. They tweak two fields and click Save.
2. **Factory has a product catalog in CSV.** They drop the CSV into step 3. The system proposes a column mapping (`Item No. → sku`, `Name → name`, `MOQ (pcs) → moq`). They confirm with one dropdown fix. They see 87 products in an editable table, delete 3 they no longer make, edit prices on 5, click Save.
3. **Factory has a product catalog in PDF.** Same entry point. The PDF is parsed page by page, product blocks extracted with thumbnail images. Same editable table.
4. **Factory has a pile of certification PDFs.** For each cert, they drop the file into the existing Add Certification modal. The modal's fields are pre-filled (cert type, number, issuing body, dates). They confirm each.

## 4. Four ingestion lanes

Each lane is one document type → one target schema → one commit target.

| Lane | Accepted input | Target schema | Commit target |
|---|---|---|---|
| Company profile | `.pdf` | Company profile JSON (fields below) | `tenant_subscription.company_profile` and `.factory_details` via existing `POST /factory-profile/save` |
| Product CSV | `.csv`, `.xlsx` | List of product records | New `product_catalog` table |
| Product PDF | `.pdf` (catalog / brochure) | List of product records | New `product_catalog` table |
| Certification | `.pdf` or image | Single cert record | `factory_certifications` via existing `POST /certifications` |

### 4.1 Company profile target schema

Fields the extractor aims to fill. All optional — missing fields stay blank for the user to type.

- `company_name_en`, `company_name_local`
- `year_founded` (int)
- `headquarters_location` (string)
- `employee_count_range` (e.g. "50-200")
- `business_type` (manufacturer / trading / OEM / ODM)
- `product_description` (one-paragraph summary)
- `main_markets` (array of country names)
- `factory_location`, `factory_size_sqm`, `production_capacity`
- `certifications_mentioned` (array of strings — loose mentions, not authoritative cert records)
- `key_customers_mentioned` (array, optional)

### 4.2 Product target schema

One row per product. Fields:

- `name` (required)
- `sku`
- `description`
- `specs` (JSON: key-value pairs from the spec table)
- `image_url` (GCS URL after extraction/upload)
- `moq` (integer)
- `price_range` (JSON: `{min, max, currency, unit}`)
- `hs_code_suggestion` (optional, fed into existing `/hs-codes/suggest` later)

### 4.3 Certification target schema

Matches existing `factory_certifications` columns exactly:
- `cert_type`, `cert_number`, `issuing_body`, `issue_date`, `expiry_date`, `notes`

## 5. User flow (one state machine, reused across lanes)

```
idle ─► uploading ─► processing ─► ready_for_review ─► committed
                 │                │                 │
                 └────► failed ◄──┘                 └► discarded
```

1. **idle** — dropzone visible on the relevant wizard step.
2. **uploading** — file streamed to backend, GCS upload, job row created. Returns `{job_id}`.
3. **processing** — background task runs the lane's extractor. Frontend polls every 2s.
4. **ready_for_review** — `draft_payload` is ready. Frontend pre-fills form fields and shows a banner: "We filled these in from `profile.pdf` — review and edit before saving."
5. **committed** — user clicks Save in the wizard. Draft payload is written to the authoritative store; job marked `committed`.
6. **failed** — extractor errored or confidence too low. User sees a red banner and falls back to manual entry.
7. **discarded** — user clicks "Start over" or navigates away. Draft is retained for 30 days then purged.

## 6. Frontend changes

The wizard (`components/onboarding/customize-ai/CustomizeAIQuestionnaire.tsx`) gains:

- A reusable `<DocumentDropzone kind="..." />` component above the relevant form fields on steps 1, 3, and inside the Add Certification modal on step 4. Handles the 5 states.
- A `<ColumnMappingModal />` that appears only after a CSV upload finishes extraction, before the product table is shown. Left column = user's headers. Right column = dropdown of our schema fields (or "ignore"). LLM pre-fills the dropdowns.
- An `<AutofilledFieldHighlight />` wrapper that gives auto-filled fields a soft yellow background + "auto-filled" badge. The highlight clears as soon as the user edits that field.

What does **not** change on the frontend:
- Existing form layouts, validation, save buttons, step navigation.
- Existing `settingsApiClient` — just one new prefix `/ingestion/*`.
- i18n conventions (zh-CN parity required for every new string).

## 7. Backend changes

### 7.1 New routes under `/ingestion`

- `POST /ingestion/upload` — multipart. Body: `file`, `kind`. Returns `{job_id, status}`.
- `GET /ingestion/jobs/{job_id}` — returns `{status, draft_payload?, error?}`.
- `POST /ingestion/jobs/{job_id}/commit` — body is the final (possibly user-edited) payload. Writes to the authoritative store for that kind. Returns `{success: true}`.
- `DELETE /ingestion/jobs/{job_id}` — user-initiated discard.

### 7.2 New service module `src/services/document_ingestion/`

- `schemas.py` — pydantic schemas for each lane's target output.
- `company_profile_extractor.py` — sends PDF bytes to OpenAI with JSON schema; returns typed dict.
- `product_csv_mapper.py` — pandas read + one OpenAI call to map headers → schema → coerced rows.
- `product_pdf_extractor.py` — sends PDF to OpenAI, returns array of products; for each product, optionally crops image by bbox (deferred — see scope cuts).
- `certification_extractor.py` — sends PDF/image to OpenAI, returns cert record.
- `runner.py` — one dispatch function per kind, called by `BackgroundTasks`.

### 7.3 Two new tables (single Alembic migration in the next weekly batch)

**`ingestion_jobs`**
- `job_id` UUID PK
- `email` text (FK semantics via application layer)
- `kind` text (`company_profile` | `product_csv` | `product_pdf` | `certification`)
- `source_url` text (GCS)
- `status` text (see state machine)
- `draft_payload` JSONB nullable
- `error` text nullable
- `created_at`, `updated_at` TIMESTAMPTZ
- Index on `(email, created_at DESC)`

**`product_catalog`**
- `product_id` UUID PK
- `email` text
- `name`, `sku`, `description`
- `specs` JSONB
- `image_url` text nullable
- `moq` int nullable
- `price_range` JSONB nullable
- `hs_code` text nullable
- `source_job_id` UUID nullable (FK to `ingestion_jobs`)
- `created_at`, `updated_at` TIMESTAMPTZ
- Index on `(email, name)`

Migration is applied to all tenant DBs via the existing `migrate-tenants` skill. `models.py` is updated in the same PR.

## 8. Tooling

All services in the plan use **only tools already paid for** in the current system:

- **OpenAI API** (existing `OPENAI_API_KEY`, same pattern as `hs_codes_router.py`) — native PDF input + `response_format={type: "json_schema"}` for typed output. One call per document.
- **Google Cloud Storage** (existing `utils/gcs.py`) — raw uploads. New folder prefixes: `ingestion/company/`, `ingestion/product/`, `ingestion/cert/`.
- **PostgreSQL** — two new tables, per above.
- **pandas** (existing dep) — CSV reading.
- **pdfplumber** (free, MIT, add to `requirements.txt`) — optional text pre-pass so the model sees small-print numbers reliably.
- **FastAPI `BackgroundTasks`** — no new queue infra.

Zero new vendor signups. Zero new API keys. No GPU compute added.

## 9. Cost impact

- **OpenAI incremental**: ~$0.01–0.30 per user during onboarding, one-time. Driven by PDF input token cost and JSON output tokens.
- **GCS storage**: cents per month at class/launch scale. PDFs average ~10 MB.
- **Postgres**: negligible. Purge committed `ingestion_jobs` after 30 days via cron.

No new line items on any vendor bill.

## 10. Safety and limits

- Per-user rate limit: 10 uploads/day, 50 MB/file. Enforced at the router.
- MIME + extension allowlist per lane.
- JSON schema on OpenAI output is strict — we reject the job with `status=failed` if parsing fails twice.
- User sees every extracted field before commit. No silent writes.
- Source file URL and extraction output both retained on the job row, so the user can re-review or we can re-extract with a new prompt later.

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| OpenAI returns hallucinated or wrong fields | Human-in-the-loop review is non-negotiable. Never auto-commit. |
| Long PDFs time out the extractor | Cap at 50 pages. Over that, reject with a message to split the doc. |
| Product catalog table extraction fails on dense layouts | Ship text-only extraction first. Add LlamaParse only if we see real failures. LlamaParse has a free tier (1k pages/day) that covers any class-scale use. |
| Async job orphans (user abandons mid-flow) | Purge `ingestion_jobs` in `processing` state older than 10 minutes; keep `ready_for_review` for 30 days then purge. |
| Re-upload of the same doc creates dupes | `ingestion_jobs` keeps a history; the wizard only surfaces the most recent `ready_for_review` job per kind. |
| Cross-tenant data leak through GCS | Existing `upload_file()` already scopes by email. Reuse it — do not write a new uploader. |

## 12. Scope cuts if we run out of time

In order of what to drop first:

1. **Image extraction from product PDFs (M5 step-2).** Ship the PDF lane text-only: products come through with `image_url=None` and the review table shows an "Upload image" placeholder per row. Keeps M5 demo-able when bbox cropping misbehaves. See coding plan §6.5.
2. **Async processing.** Fall back to sync with a 60-second timeout and a spinner. Onboarding traffic is low enough to tolerate this.
3. **Column-mapping modal for CSV.** Publish a template CSV, require users to match it.
4. **Cert auto-extract.** Smallest win per hour; the manual form is already quick.

What we never cut: the review-and-edit step, the schema-strict extraction contract, and rate limits.

## 13. Open questions

- Do we need to support DOCX for company profiles? (Decision: no for v1 — PDF only. Add DOCX if a real user asks.)
- Should the product catalog support multi-image per product? (Decision: no for v1 — one hero image per product row. Add a gallery table later if needed.)
- Do we localize extraction prompts for Chinese documents, or trust the model to handle mixed-language PDFs? (Decision: single English prompt with an instruction to respect source language for free-text fields. Revisit if zh-CN accuracy is bad.)

## 14. Success criteria

- 80% of factory-profile uploads produce a draft the user commits with ≤ 3 edits.
- 90% of CSV uploads produce a column mapping the user accepts without manual override.
- Median extraction latency under 30 seconds per document.
- Zero cross-tenant data incidents.
- Onboarding time-to-first-Save for the company profile step drops by ≥ 50% vs. typing it in.

---

## Appendix A — Relationship to existing features

- `factory_profile_router.py` — **commit target** for company profile lane. No changes to its contract; we just pre-fill the request body.
- `certification_router.py` — **commit target** for cert lane. Same.
- `hs_codes_router.py` — unchanged. The product catalog lane can feed product descriptions into the existing `/hs-codes/suggest` endpoint as a follow-up step; out of scope here.
- `tenant_subscription.target_products` — left alone. The `product_catalog` table is the new source of truth for the catalog. Lead-gen's existing read of `target_products` continues to work until a follow-up migrates it.
