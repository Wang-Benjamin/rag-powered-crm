# Document Ingestion Feature — Coding Plan

Companion to `DOC_INGESTION_PLAN.md`. This doc is the build sequence: files to create, endpoint contracts, schema fields, task order, and verification steps. Written so an engineer can pick it up and execute without re-deriving design.

---

## 0. Before touching code

1. Read `DOC_INGESTION_PLAN.md` and agree on lane scope.
2. Confirm `OPENAI_API_KEY` is set in `.env` and that the current `hs_codes_router.py` path works locally. That validates the OpenAI + tenant-auth baseline.
3. Confirm GCS uploads work — call `POST /factory-profile/upload-photo` as a smoke test.
4. Branch off `main`: `doc-ingestion`.

## 1. Milestones at a glance

| # | Milestone | Exit criterion |
|---|---|---|
| M1 | Schemas + job table | `models.py` and migration reviewed; test DB has the new table. |
| M2 | Reusable dropzone on the frontend, mocked backend | Drop a file, see all 5 UI states with a hand-crafted mock payload. |
| M3 | Company profile lane end-to-end | Upload a real brochure, review, commit writes to `tenant_subscription`. |
| M4 | Certification lane | Same loop, pre-fills the existing Add Certification modal. |
| M5 | Product PDF lane (with images, prices, specs) | Upload catalog PDF, review rows with cropped image thumbnails + prices + specs, commit writes to `product_catalog`. |
| M6 | Product CSV lane (incl. column-mapping modal) | Upload CSV, map columns, edit rows, commit writes to `product_catalog`. |
| M7 | Rate limits, retention cron, observability | `ingestion_jobs` purges old rows; per-user quota enforced; Sentry wired. |

Each milestone is independently shippable. Do not merge a milestone without the frontend piece for that lane.

**Note on M5/M6 ordering.** M5 is the heaviest lane because it introduces the product table UI, the `product_catalog` commit path, and image extraction from PDFs in a single milestone. M6 (CSV) then reuses the product table UI and commit path. If image extraction turns out to be flaky in M5, use the scope cut in §6.5 (ship text-only PDF first, add image upload in a follow-up) — don't hold up the milestone.

## 2. Milestone M1 — Schemas and storage

### 2.1 Files to create

- `src/services/document_ingestion/__init__.py`
- `src/services/document_ingestion/schemas.py`

Contents of `schemas.py`: four pydantic models (no methods, just fields).

- `CompanyProfileDraft`:
  - `company_name_en: Optional[str]`
  - `company_name_local: Optional[str]`
  - `year_founded: Optional[int]`
  - `headquarters_location: Optional[str]`
  - `employee_count_range: Optional[str]`
  - `business_type: Optional[Literal["manufacturer", "trading", "oem", "odm", "other"]]`
  - `product_description: Optional[str]`
  - `main_markets: list[str] = []`
  - `factory_location: Optional[str]`
  - `factory_size_sqm: Optional[int]`
  - `production_capacity: Optional[str]`
  - `certifications_mentioned: list[str] = []`
  - `key_customers_mentioned: list[str] = []`

- `ProductRecordDraft`:
  - `name: str`
  - `sku: Optional[str]`
  - `description: Optional[str]`
  - `specs: dict[str, str] = {}`
  - `image_url: Optional[str]`
  - `moq: Optional[int]`
  - `price_range: Optional[dict]`
  - `hs_code_suggestion: Optional[str]`

- `ProductCatalogDraft`:
  - `products: list[ProductRecordDraft]`
  - `column_mapping: Optional[dict[str, str]]` (CSV lane only — records the user's final mapping)

- `CertificationDraft`:
  - Mirrors `factory_certifications` columns exactly: `cert_type`, `cert_number`, `issuing_body`, `issue_date` (ISO string), `expiry_date` (ISO string), `notes`.

Also define a `JobKind` literal and a `JobStatus` literal used across the service.

### 2.2 Alembic migration

One migration file in `alembic_postgres/versions/`. Adds two tables (see DDL below) and updates `models.py` with matching `IngestionJobs` and `ProductCatalog` classes.

**`ingestion_jobs`**
```
job_id         UUID PK default gen_random_uuid()
email          VARCHAR(255) NOT NULL
kind           VARCHAR(32)  NOT NULL CHECK (kind IN ('company_profile','product_csv','product_pdf','certification'))
source_url     TEXT         NOT NULL
status         VARCHAR(32)  NOT NULL DEFAULT 'queued'
                 CHECK (status IN ('queued','processing','ready_for_review','committed','failed','discarded'))
draft_payload  JSONB        NULL
error          TEXT         NULL
created_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
updated_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
INDEX idx_ingestion_jobs_email_created (email, created_at DESC)
INDEX idx_ingestion_jobs_status (status) WHERE status IN ('queued','processing')
```

**`product_catalog`**
```
product_id     UUID PK default gen_random_uuid()
email          VARCHAR(255) NOT NULL
name           VARCHAR(500) NOT NULL
sku            VARCHAR(255) NULL
description    TEXT NULL
specs          JSONB NOT NULL DEFAULT '{}'::jsonb
image_url      TEXT NULL
moq            INTEGER NULL
price_range    JSONB NULL
hs_code        VARCHAR(16) NULL
source_job_id  UUID NULL REFERENCES ingestion_jobs(job_id) ON DELETE SET NULL
created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
INDEX idx_product_catalog_email_name (email, name)
```

After merging: run `migrate-tenants` skill to roll out to every tenant DB.

### 2.3 Repository layer

Add `src/data/repositories/ingestion_repository.py` with plain async functions (no class needed):

- `create_job(conn, email, kind, source_url) -> job_id`
- `get_job(conn, job_id, email) -> row | None`
- `update_job_status(conn, job_id, status, *, draft_payload=None, error=None)`
- `list_recent_jobs(conn, email, kind=None, limit=20)`
- `purge_stale_jobs(conn)` — helper used by the retention cron (M7).

### 2.4 Verification

- Unit test: insert job row, read back, update status, confirm indexes exist.
- Run `alembic upgrade head` on a scratch DB, verify schema.

## 3. Milestone M2 — Frontend dropzone against a mocked backend

### 3.1 Files to create

- `components/onboarding/customize-ai/ingestion/DocumentDropzone.tsx` — the state-machine component.
- `components/onboarding/customize-ai/ingestion/AutofilledFieldHighlight.tsx` — wrapper.
- `components/onboarding/customize-ai/ingestion/types.ts` — types mirroring the backend schemas.
- `lib/api/ingestion.ts` — tiny client over `settingsApiClient` with `upload`, `getJob`, `commit`, `discard`.

### 3.2 DocumentDropzone contract

Props:
- `kind: "company_profile" | "product_csv" | "product_pdf" | "certification"`
- `accept: string` (MIME list per lane)
- `maxSizeMB: number`
- `onReady: (draft: unknown, jobId: string) => void`
- `onFailed: (message: string) => void`

Internal states: `idle` → `uploading` → `processing` → `ready` | `failed`. Poll `getJob` every 2s while in `processing`, with a 120s ceiling then surface `failed`.

### 3.3 Mock backend

Add a dev-mode toggle in `lib/api/ingestion.ts` that returns canned payloads (one per lane, realistic enough to pre-fill fields). This lets us ship the UI before the extractors land.

### 3.4 Verification

- Manual: drop a file, observe all 5 states. zh-CN and en strings both render.
- Storybook entry for `DocumentDropzone` covering each state.

## 4. Milestone M3 — Company profile lane (reference lane)

### 4.1 Backend files

- `src/services/document_ingestion/company_profile_extractor.py`
  - One async function `extract(pdf_bytes: bytes) -> CompanyProfileDraft`.
  - Uses OpenAI `responses.create` with `input_file` (PDF) and `response_format={"type": "json_schema", "json_schema": CompanyProfileDraft.model_json_schema()}`.
  - Retries once on parse failure, then raises.

- `src/services/document_ingestion/runner.py`
  - `async def run_job(job_id: UUID)` — fetches the job, downloads file from GCS, dispatches by `kind`, writes back `ready_for_review` or `failed`.

- `src/routers/ingestion_router.py`
  - `POST /ingestion/upload` (multipart, fields: `file`, `kind`) — validates MIME/size, uploads to GCS under `ingestion/{kind}/{email}/{job_id}`, creates job row, schedules `BackgroundTasks.add_task(runner.run_job, job_id)`, returns `{job_id, status: "queued"}`.
  - `GET /ingestion/jobs/{job_id}` — returns `{status, draft_payload?, error?}`.
  - `POST /ingestion/jobs/{job_id}/commit` — body: `{payload: CompanyProfileDraft}`. Calls the existing `POST /factory-profile/save` logic (refactor the shared write into a small helper in the factory profile router so both routes call it). Sets job `status=committed`.
  - `DELETE /ingestion/jobs/{job_id}` — marks `discarded`, does not delete the file.

- Register the router in `main.py` (`app.include_router(ingestion_router, prefix=API_PREFIX, tags=["Document Ingestion"])`).

### 4.2 Frontend wiring

- Add `<DocumentDropzone kind="company_profile" />` at the top of step 1 in `CustomizeAIQuestionnaire.tsx`.
- On `onReady(draft)`, merge into the wizard's `data` state, wrapping each touched field with `<AutofilledFieldHighlight>`.
- Commit happens through the existing wizard Save button, which already calls `/factory-profile/save` — no additional commit UI needed. After a successful wizard Save, call `POST /ingestion/jobs/{id}/commit` to mark the job `committed` (bookkeeping only).

### 4.3 Verification

- Upload 3 real factory PDFs from different industries. Confirm at least 6 of the 12 target fields populate correctly on each.
- Confirm user edits clear the yellow highlight.
- Confirm re-upload replaces the draft, not append.
- Sentry breadcrumb check: upload, extraction, commit each emit a breadcrumb.

## 5. Milestone M4 — Certification lane

### 5.1 Backend files

- `src/services/document_ingestion/certification_extractor.py` — same shape as company profile extractor, returns `CertificationDraft`.
- `runner.py` gains the `certification` branch.

### 5.2 Frontend wiring

- Existing Add Certification modal on step 4 gains a `<DocumentDropzone kind="certification" />` at the top.
- `onReady` pre-fills the modal fields. User clicks Save (existing button), which calls the existing `POST /certifications`. Then we call the commit endpoint for bookkeeping.

### 5.3 Verification

- Upload 5 different cert types (ISO 9001, BSCI, CE, FDA, Sedex). Confirm ≥ 4 of the 5 target fields populate on each.

## 6. Milestone M5 — Product PDF lane (with images, prices, specs)

This is the first product-catalog lane. It introduces the editable product table UI and the `product_catalog` commit path that M6 (CSV) will reuse.

### 6.1 Backend files

- `src/services/document_ingestion/product_pdf_extractor.py`
  - `async def extract(pdf_bytes: bytes, *, job_id, email) -> ProductCatalogDraft`
  - **Step 1 — structured text extraction.** OpenAI native PDF input with a JSON schema asking for:
    - `products: list[ProductRecordDraft]` (name, SKU, description, specs, moq, price_range, hs_code_suggestion), **plus**
    - per-product `image_hint: { page_number: int, bbox: [x0, y0, x1, y1] } | null` where bbox is in PDF-point coordinates normalized 0–1 per page.
  - **Step 2 — image crop + upload.** For each product with a non-null `image_hint`:
    - Render the PDF page to a PIL image via `pdf2image.convert_from_bytes` (uses poppler; MIT-licensed).
    - Crop the bbox region with Pillow.
    - Upload PNG to GCS under `ingestion/product/{email}/{job_id}/{product_idx}.png` using the existing `utils/gcs.upload_file`.
    - Set `image_url` on the record to the returned URL.
  - **Step 3 — graceful fallback.** If rendering or cropping fails for a product, leave `image_url=None`. The record still ships; user can upload an image manually in the review table.
  - Optional `pdfplumber` text pre-pass to feed extracted text alongside the PDF, improves small-print spec-table accuracy.
  - Retries the step-1 call once on JSON parse failure, then raises.

- `runner.py` gains the `product_pdf` branch.

- **Library choice / AGPL note.** Use `pdf2image` + `Pillow` (both MIT). Do **not** introduce PyMuPDF / `fitz` for this lane — it's AGPL and would force license review of the whole service. `pdf2image` is heavier at runtime (shells out to poppler) but fine at onboarding scale.

### 6.2 Frontend wiring

- Dropzone on step 3, `kind="product_pdf"`. Skips the column-mapping modal.
- Build a new `<ProductCatalogReviewTable />` in `components/onboarding/customize-ai/ingestion/`:
  - One row per product. Columns: thumbnail (64×64, from `image_url` or upload-slot placeholder), name, SKU, price, MOQ, description, spec-count, actions (edit, delete).
  - Inline edit on click. "Add row" button for missing products. "Upload image" button on rows where `image_url` is null.
  - Selection of thumbnail opens a full-size preview (uses existing shadcn Dialog).
- M6 (CSV) will import and reuse this same table component — design it not to assume PDF-specific state.

### 6.3 Commit

- Extend the ingestion router's commit handler: for `product_pdf` kind, bulk-insert into `product_catalog` with `source_job_id = job_id`, scoped by email, in a single transaction.
- Image URLs are already live on GCS from step 2 — commit is a pure DB write.

### 6.4 Verification

- Upload a 10-page product brochure. Confirm:
  - ≥ 80% of products end up in the draft with a correct name and SKU.
  - ≥ 60% of products end up with a correctly-cropped thumbnail (bbox can be fuzzy on dense grid layouts — acceptable).
  - Prices and specs come through on products where the brochure shows them.
- Upload a purely text-only catalog (no extractable images). Confirm products come through with `image_url=None` and the UI shows an "Upload image" placeholder per row, not an error.
- Confirm failure mode: malformed PDF returns partial data + `error` set, frontend surfaces a helpful message.

### 6.5 Scope cut (use if image extraction is unreliable)

If step-2 image cropping produces mostly-wrong thumbnails in real-world testing, strip it out:

1. Remove step 2 (image crop + upload) — extractor returns products with `image_url=None`.
2. Frontend shows the same "Upload image" placeholder per row.
3. Ship the milestone. Open a follow-up to revisit image extraction with better bbox prompting or a hosted parser (LlamaParse has a free tier) — not in scope for this PR series.

This keeps M5 demo-able without blocking on the hardest piece.

## 7. Milestone M6 — Product CSV lane

Reuses the editable product table built in M5. Adds the CSV mapper + column-mapping modal.

### 7.1 Backend files

- `src/services/document_ingestion/product_csv_mapper.py`
  - `async def propose_mapping(headers: list[str], sample_rows: list[dict]) -> dict[str, str]` — one OpenAI call, returns mapping from user header → our schema field (or `"ignore"`).
  - `def apply_mapping(df: pandas.DataFrame, mapping: dict[str, str]) -> list[ProductRecordDraft]` — coerces types, drops ignored columns, validates required fields.
- `runner.py` gains the `product_csv` branch. Extraction output is `{proposed_mapping, sample_rows, row_count}` — the user reviews the mapping first, then a second call applies it.

### 7.2 New endpoint for the two-phase flow

- `POST /ingestion/jobs/{job_id}/apply-mapping` — body: `{mapping: dict[str, str]}`. Runs `apply_mapping`, sets `draft_payload` to the full product list, status stays `ready_for_review`.

### 7.3 Frontend wiring

- New `<ColumnMappingModal />` opens when dropzone reaches `ready` and the payload contains `proposed_mapping`. User confirms mapping, clicks Apply, which calls the new endpoint and waits for the updated draft.
- Once the product list is ready, render the `<ProductCatalogReviewTable />` built in M5. CSV products default to `image_url=null`; user uploads each image manually in the review table (same "Upload image" per-row button M5 already built).
- Save (wizard-level) commits the full list via `POST /ingestion/jobs/{id}/commit`.

### 7.4 Commit-target write

- Same commit path as M5 (`product_catalog` bulk insert). The kind-switch in the commit handler already handles `product_csv`.

### 7.5 Verification

- Upload a CSV with messy headers (`Item#`, `Product Name (EN)`, `MOQ pcs`, `FOB $`). Confirm proposed mapping is correct on ≥ 3 of 4 columns.
- Upload a CSV with 100+ rows. Confirm commit runs under 2s and produces the right row count.

## 8. Milestone M7 — Rate limiting, retention, observability

### 8.1 Rate limiting

- In the router: check count of `ingestion_jobs` rows for this email in the last 24h. If ≥ 10, return `429`. Check `file.size` ≤ 50 MB before streaming to GCS.

### 8.2 Retention cron

- Add `scripts/purge_ingestion_jobs.py`:
  - Delete jobs in `processing` older than 10 minutes (stuck workers).
  - Delete jobs in any terminal state older than 30 days, and delete their GCS blobs (including the per-product cropped images for `product_pdf` jobs).
- Schedule via existing cron infra (same place as other periodic scripts).

### 8.3 Observability

- Add Sentry breadcrumbs at upload-received, extraction-start, extraction-complete, commit. Tag by `kind`.
- Log counters: success rate per kind, median latency per kind, average token cost per kind. For `product_pdf`, also log image-crop success rate.

## 9. Endpoint reference (full list)

```
POST   /ingestion/upload
GET    /ingestion/jobs/{job_id}
POST   /ingestion/jobs/{job_id}/apply-mapping    # product_csv only
POST   /ingestion/jobs/{job_id}/commit
DELETE /ingestion/jobs/{job_id}
```

All routes use the existing `get_tenant_connection` dependency. Email is derived from the JWT — never passed in the request.

## 10. Requirements changes

Add to `requirements.txt`:
- `pdfplumber` (exact version pinned to the latest stable minor at branch time)
- `pdf2image` (MIT, needs poppler in the Docker base image)
- `Pillow` (already in the dep tree via other packages, but pin explicitly if not)

System-level dependency: `poppler-utils` must be installed in the Dockerfile (needed by `pdf2image`). Add an `apt-get install -y poppler-utils` line to the user-settings Dockerfile during M5.

No other new deps. `openai`, `asyncpg`, `pandas`, `fastapi`, `pydantic` already installed.

**Do not add** PyMuPDF (AGPL) or any hosted parser (LlamaParse, Reducto, Mistral OCR, Anthropic). See plan §8.

## 11. Testing

- Unit tests for each extractor using recorded OpenAI responses (VCR-style fixtures or hand-written JSON stubs). Do not hit OpenAI in CI.
- Unit tests for `ingestion_repository` against a test DB.
- Integration tests for each router endpoint using FastAPI `TestClient` with a mocked runner.
- Frontend: Storybook stories for each dropzone state, the column-mapping modal, and the product catalog review table (including the "Upload image" empty-state row).
- Manual QA matrix: one real document per lane, en and zh-CN locales, quota boundary (10th vs 11th upload of the day), file over 50 MB rejected, malformed PDF rejected, PDF lane with and without extractable images.

## 12. Deployment checklist

- [ ] Alembic migration merged and applied via `migrate-tenants`.
- [ ] `pdfplumber`, `pdf2image`, `Pillow` added to `requirements.txt`.
- [ ] `poppler-utils` added to the user-settings Dockerfile.
- [ ] `ingestion_router` registered in `main.py`.
- [ ] Health endpoint in `main.py` reports `"document_ingestion": True` under `features`.
- [ ] Retention cron scheduled.
- [ ] Rate limits verified in staging.
- [ ] Frontend proxy route added for `/ingestion/*` in `app/api/proxy/settings` (or equivalent) and i18n strings added for both en and zh-CN.
- [ ] Sentry dashboard has a filter for `tag:feature=doc_ingestion`.
- [ ] `DOC_INGESTION_PLAN.md` marked as Shipped.

## 13. Out of scope for this PR series (parking lot)

- DOCX / TXT / image-only company profiles.
- Multi-image per product (hero + gallery).
- Bulk cert upload in a single action (user still drops one cert at a time).
- Feeding extracted product descriptions into `/hs-codes/suggest` automatically — add later as a one-click "Suggest HS codes for all products" action.
- Migrating existing `tenant_subscription.target_products` consumers (lead-gen) to the new `product_catalog` table — separate follow-up.
- Upgrading PDF-image extraction to a hosted parser (LlamaParse / Reducto) if OpenAI bbox accuracy is insufficient at real-world volume.
- **Product catalog management UI** — standalone `/settings/products` page with full CRUD (list, search, filter, paginate, edit, delete, replace image, bulk ops) on the `product_catalog` table. Reuses the `<ProductCatalogReviewTable />` component built in M5. Scoped as its own follow-up feature because ingestion is onboarding-time bulk autofill, whereas catalog management is ongoing CRUD with different UX concerns. On that page, the M5/M6 dropzones reappear as an "Import from catalog" action so bulk ingestion remains available post-onboarding. Merge policy on re-import defaults to "append with dedup on SKU," user-overridable per upload.

## 14. Task ordering summary

Day-sized tasks in execution order:

1. Schemas + migration + repository (M1).
2. Dropzone + mock client + Storybook (M2).
3. Company profile extractor + router + wizard wiring (M3).
4. Certification extractor + modal wiring (M4).
5. Product PDF extractor (text + bbox + crop) + product table UI + commit path (M5).
6. CSV mapper + column-mapping modal (reuses M5's product table) (M6).
7. Rate limits + retention cron + Sentry tags (M7).

Do not reorder M3 before M2 — a working UI against a mock backend de-risks every later lane. Do not reorder M6 before M5 — M6 depends on the product table UI and commit path introduced in M5.
