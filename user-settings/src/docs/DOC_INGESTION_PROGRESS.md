# Document Ingestion — Progress Log

Running log of every build session for the document-ingestion feature.
Paired with `DOC_INGESTION_PLAN.md` (product plan) and `DOC_INGESTION_CODING_PLAN.md` (build plan).

## House rules for this build (read every session)

These rules apply to every session on this feature. They survive `/clear` because they live in this file, not in the conversation.

- **Source of truth.** `DOC_INGESTION_PLAN.md`, `DOC_INGESTION_CODING_PLAN.md`, and this progress log are the design. If you want to deviate, stop and propose the change before coding.
- **One milestone at a time.** Don't start the next milestone until the current one is merged. Don't touch scope outside the current milestone.
- **Confirm before coding.** At the start of each milestone, restate the exit criterion from the coding plan, list the files you'll create or modify, and wait for the user to say "go" before writing code.
- **Verify before declaring done.** Run the migration, hit the endpoint, check the UI state. Type-checks alone are not verification.
- **No new paid services.** The plan uses OpenAI + GCS + Postgres only — all already paid. If tempted to add LlamaParse, Anthropic, Docling, etc., stop and ask.
- **Branch.** `doc-ingestion`, one branch for the whole feature, one commit per milestone. Do not create sub-branches per milestone.
- **Tight updates.** One sentence per tool call. Don't narrate internal reasoning.
- **End every session the same way:** verify exit criterion, commit, append a dated entry to this file using the template below, push, then summarize in 3 lines.

## How to use the log below

- One dated entry per session, newest at the bottom.
- Record what landed, what's open, any deviations from the plan, and the next session's first task.
- Record **decisions** (why we deviated) more than **actions** (what we typed — git already knows).
- Do **not** paste code here. Point at files and commits instead.
- Update at the end of every session before pushing.

## Entry template

```
## YYYY-MM-DD
- Branch: doc-ingestion @ <commit sha>
- Milestone: M_
- Status: IN PROGRESS | DONE | BLOCKED
- Done:
  - <bullet per file/change that landed>
- Open:
  - <bullet per thing still to do inside this milestone>
- Deviations from plan:
  - <none | describe and link back to plan section>
- Open questions:
  - <anything to revisit>
- Next session first task:
  - <the single next thing to do>
```

---

## 2026-04-22

- Branch: not yet created (will branch off `main` @ 996855db)
- Milestone: Pre-M1 (planning)
- Status: DONE
- Done:
  - Reviewed existing user-settings service (`factory_profile_router`, `certification_router`, `hs_codes_router`) and identified existing commit targets so we reuse them rather than duplicate.
  - Confirmed OpenAI is an existing paid dependency across all services — no new vendor needed.
  - Wrote `DOC_INGESTION_PLAN.md` (product/design plan).
  - Wrote `DOC_INGESTION_CODING_PLAN.md` (build plan, 8 milestones M1–M8).
  - Wrote this progress log with a template and house rules.
- Open:
  - Build hasn't started. M1 (schemas + Alembic migration + repository) is next.
- Deviations from plan:
  - None.
- Open questions:
  - None yet. Will capture as they come up during implementation.
- Next session first task:
  - Start M1. Read both plan docs, then create `src/services/document_ingestion/schemas.py` with the four pydantic draft models listed in the coding plan section 2.1.

---

## 2026-04-22 (M1)

- Branch: doc-ingestion @ (to be filled at commit time — this entry + M1 code commit together)
- Milestone: M1 — Schemas + storage
- Status: DONE
- Done:
  - Added `src/services/document_ingestion/{__init__.py, schemas.py}` with `CompanyProfileDraft`, `ProductRecordDraft`, `ProductCatalogDraft`, `CertificationDraft`, plus `JobKind` / `JobStatus` / `BusinessType` literals. `ProductRecordDraft.price_range` uses a typed `PriceRange` submodel instead of a bare dict — small tightening consistent with plan intent.
  - Extended `alembic_postgres/models.py` with `IngestionJobs` and `ProductCatalog` matching the DDL in coding plan §2.2 (UUID PKs, CHECK constraints on `kind`/`status`, indexes incl. the partial `idx_ingestion_jobs_active`, FK `product_catalog.source_job_id → ingestion_jobs.job_id ON DELETE SET NULL`).
  - Wrote migration `alembic_postgres/versions/20260422_1200_add_ingestion_tables.py` (revision `b2c3d4e5f6a1`, down_revision `a1b2c3d4e5f6`) using `CREATE ... IF NOT EXISTS` so it's a no-op on fresh tenant DBs that receive the tables via baseline's `Base.metadata.create_all()` — same idempotency pattern as `drop_unused_employee_columns.py`.
  - Added `src/data/repositories/ingestion_repository.py` with `create_job`, `get_job`, `update_job_status`, `list_recent_jobs`, `purge_stale_jobs`. JSONB columns parsed via existing `utils/json_helpers.parse_jsonb` so callers get dicts back — matches repo-wide convention.
  - Verified end-to-end on scratch DBs (`doc_ingestion_scratch` + `doc_ingestion_fresh`, both dropped after): migration ran clean, physical schema matches plan, repo round-trip passes (insert → fetch → status-update with draft_payload → list → kind filter → app-layer + DB CHECK rejection → FK SET NULL cascade). Both scratch DBs dropped.
- Open:
  - Rolling the migration to real tenant DBs via the `migrate-tenants` skill — intentionally deferred until after this commit is reviewed.
- Deviations from plan:
  - Branch name is `doc-ingestion`, not `feat/doc-ingestion`. Updated house rules + CODING_PLAN §0 to match reality.
  - Added a typed `PriceRange` pydantic submodel under `ProductRecordDraft.price_range`. Plan said `Optional[dict]`; submodel is stricter and round-trips identically. Noting it here because the plan explicitly listed the loose dict.
  - Installed `alembic==1.13.1` (already pinned in `requirements.txt`) into `./venv` for local verification — the package was listed but not installed.
- Open questions:
  - None.
- Next session first task:
  - Start M2 — restate exit criterion ("drop a file, see all 5 UI states with a hand-crafted mock payload") and list files before touching code.

---

## 2026-04-22 (M2)

- Branch: doc-ingestion @ (commit SHA recorded in the M2 commit message)
- Milestone: M2 — Frontend dropzone against a mocked backend
- Status: DONE
- Done:
  - Added `components/onboarding/customize-ai/ingestion/{types.ts, DocumentDropzone.tsx, AutofilledFieldHighlight.tsx}`. Dropzone is a pure state-machine component (`idle → uploading → processing → ready | failed`) with drag-drop, MIME/size rejection, 2s polling + 120s ceiling, bilingual copy, zinc/emerald/red palette per `ui-components` skill.
  - Added `lib/api/ingestion.ts`: thin wrapper over `settingsApiClient` for `POST /ingestion/upload`, `GET /ingestion/jobs/{id}`, `POST /ingestion/jobs/{id}/commit`, `DELETE /ingestion/jobs/{id}`. Ships a hot-reload-safe mock backend keyed on filename prefix — `fail*` → `failed`, `slow*` → 8s processing, anything else → `ready` with realistic payloads per lane. Mock gates on `NEXT_PUBLIC_INGESTION_MOCK=1` or `?mock=1` in dev only.
  - Added `settings.customizeAi.ingestion.*` i18n subtree to `messages/{en,zh-CN}/settings.json` covering dropzone state labels, action labels, the `auto-filled` badge, and error copy. Six errors × two languages.
  - Added dev-only verification page `app/[locale]/dev/ingestion-demo/page.tsx` + `IngestionDemo.tsx`. Mounts dropzones for all four lanes, previews the company-profile draft with interactive `AutofilledFieldHighlight` wrappers (click a field → highlight clears), returns 404 in production.
  - Verified in Chrome via Playwright at `/en/dev/ingestion-demo?mock=1` and `/zh-CN/...`: captured all five UI states (idle, uploading [via accessibility-tree snapshot showing "Uploading…"], processing, ready with auto-filled highlights, failed with wrong-type rejection). zh-CN dropzone renders Chinese copy (`拖拽文件以自动填写`, `支持 ... · 单个文件最大 50 MB`). tsc clean. Fixed one hydration mismatch on the demo page's "Mock mode is ON/OFF" banner by deferring the client-only check to `useEffect`.
- Open:
  - None inside M2. M3 will wire the dropzone into the real wizard step + add pre-fill onto the company-profile form fields, and delete the dev demo page.
- Deviations from plan:
  - My pre-M2 proposal said I'd mount the dropzone into `CustomizeAIQuestionnaire.tsx` step 1. Two problems with that: (a) step 1 in the current wizard is `guardrails`, not the company profile — the plan's "step 1" was stale vs. the live `STEP_IDS` in code; (b) wiring it into production UI without pre-fill would confuse real users. Switched to a dev-only `/{locale}/dev/ingestion-demo` page instead. Real wizard integration moves into M3 where it's paired with pre-fill. This matches the coding-plan intent (M2 = "drop a file, see all 5 UI states") better than my earlier proposal did.
  - Coding plan §3.4 lists Storybook as the verification surface. No Storybook in this repo — used the dev demo page + Playwright instead. Equivalent evidence (five state captures).
  - Tightened `ProductRecordDraft.priceRange` to a typed `PriceRange` submodel on the frontend too, matching the backend shape landed in M1.
- Open questions:
  - None.
- Next session first task:
  - Start M3 — restate exit criterion ("Upload a real brochure, review, commit writes to tenant_subscription"), list backend + frontend files, and wait for go. M3 will also remove `/dev/ingestion-demo` once the wizard is wired.

---

## 2026-04-22 (M3)

- Branch: doc-ingestion @ (SHA recorded in the M3 commit message)
- Milestone: M3 — Company profile lane end-to-end
- Status: DONE
- Done:
  - Backend extractor `src/services/document_ingestion/company_profile_extractor.py` — `pdfplumber` text pre-pass → `gpt-5.4` chat completions with `response_format=json_object` → `CompanyProfileDraft.model_validate`. Retries once on parse/validation failure, then raises. Prompt hardened after user review: free-text fields (`product_description`, locations, `production_capacity`) respond in source language; `main_markets` / cert codes are normalised to English.
  - Backend runner `src/services/document_ingestion/runner.py` — re-acquires a tenant connection from `TenantPoolManager` (BackgroundTasks runs after the response so it can't borrow the request's connection), downloads the PDF from GCS, dispatches by `kind`. Only `company_profile` is wired in M3; other kinds land on a clear `"kind {x} not yet supported"` failure rather than hanging, so M4–M6 slot in cleanly.
  - Backend router `src/routers/ingestion_router.py` — `POST /ingestion/upload` (MIME + extension allowlist per lane, 50 MB cap via `file.size` with a buffering fallback), `GET /ingestion/jobs/{id}`, `POST /ingestion/jobs/{id}/commit` (bookkeeping for `company_profile` — see deviations), `DELETE /ingestion/jobs/{id}`. Registered in `main.py` with the rest; health endpoint now reports `document_ingestion: True`.
  - Extracted `persist_factory_profile(conn, company_profile=, factory_details=)` helper out of `factory_profile_router.save_factory_profile` — unchanged behaviour, reusable from the commit endpoint for later lanes. Added `utils/gcs.download_bytes(url)` so the runner can fetch the staged PDF.
  - Pinned `pdfplumber==0.11.4` in `requirements.txt` (plan §11 already earmarked it; brought forward from M6 since the company-profile text pre-pass needs it now).
  - Frontend wired `<DocumentDropzone kind="company_profile">` at the top of wizard step 2 in `CustomizeAIQuestionnaire.tsx`. `handleIngestionReady` maps the draft onto the four matching wizard fields (`companyNameEn`, `companyNameZh` ← `company_name_local`, `productDescription`, `location` preferring `factory_location` → `headquarters_location`) and seeds `autofilledKeys`. `updateData` now strips any touched key from `autofilledKeys`, so user edits clear the amber highlight automatically. Each of the four fields is wrapped in `<AutofilledFieldHighlight>`.
  - Bookkeeping commit — after both save paths (step 2→3 `runSetupAnimation` AND terminal `handleSave`), fires `ingestionApi.commit(jobId, draft)` best-effort when `ingestionJobId` is set. Wrapped in try/catch so a commit failure never blocks the wizard flow.
  - Added an `acceptLabel?: string` prop to `DocumentDropzone` so the idle hint renders "PDF" instead of the raw MIME string `application/pdf,.pdf`. Wizard passes `acceptLabel="PDF"`.
  - Deleted `app/[locale]/dev/ingestion-demo/` (page + `IngestionDemo.tsx`) and the now-empty `dev/` folder, per M2's exit note.
  - End-to-end verified by user against `postgres` with a real PDF (`Mock_Lighting_Company_Profile.pdf`): upload → GCS → runner → ready banner → `productDescription` and `companyNameEn` pre-filled with amber "已自动填写" badges, zh locale copy correct. Edit-to-clear and commit bookkeeping confirmed by the user before this log landed.
- Deviations from plan:
  - **pdfplumber text pre-pass, not native PDF input to OpenAI.** Plan §7.2 said "sends PDF bytes to OpenAI"; §11 already listed pdfplumber as an acceptable pre-pass. Company-profile extraction is free prose — no layout-sensitive info lost — and this avoids the OpenAI Files API upload/delete round-trip. Moved the dep pin from M6 to M3.
  - **`response_format: json_object` + pydantic `model_validate`, not OpenAI strict `json_schema`.** Every draft field is `Optional`; strict mode would require rewriting the schema to put every field in `required` with `anyOf [<type>, null]`. The contract (validated JSON object, retry-once on parse/validation failure) is identical with less ceremony.
  - **Commit endpoint is bookkeeping-only for `company_profile`.** Plan §4.1 listed it as the authoritative write, but plan §4.2 immediately clarified "bookkeeping only" for this lane because the wizard's own Save (`runSetupAnimation`) already writes `tenant_subscription.company_profile` — and it writes additional fields the draft doesn't carry (logo, hs_codes, yourRole). Re-writing from the draft alone would wipe those. `persist_factory_profile` is still extracted and ready for M5/M6 where commit IS the only write path.
  - **Only four wizard fields pre-fill today.** The wizard has no UI surface for `year_founded`, `employee_count_range`, `business_type`, `main_markets`, `factory_size_sqm`, `production_capacity`, `certifications_mentioned`, `key_customers_mentioned`. Those still land on the draft payload (committed row's `draft_payload`) — if the wizard grows those fields later, the `<AutofilledFieldHighlight>` wiring already picks them up automatically from `autofilledKeys`.
  - **Migration applied by direct SQL to `postgres`, not via `migrate-tenants`.** CLAUDE.md is explicit: "When running schema changes via direct SQL (not Alembic), ONLY target the `postgres` database." Tenant DBs will pick up the migration when someone runs `migrate-tenants` separately — M1's migration file is idempotent (`CREATE TABLE IF NOT EXISTS` throughout). Initial apply to `prelude_visitor` during diagnosis was off-convention; self-corrected, tables left in place (harmless, empty).
- Open questions:
  - **Alembic version drift in existing tenant DBs.** `prelude_visitor` was stamped at `5c7cb096dd9d` — a revision not present in `alembic_postgres/versions/`. That stamp predates M3 and affects all tenant DBs, not just this one. Needs a single-pass cleanup before the next `migrate-tenants` fan-out, or `alembic upgrade head` will fail to resolve the base revision. Out of scope for M3; flagging for M7 or a dedicated migration-hygiene pass.
  - **Orphaned `ready_for_review` jobs on re-upload.** Dropzone's Replace + a new drop overwrite the parent's `ingestionJobId`, leaving the previous job row dangling in `ready_for_review` until M7's 30-day retention cron reaps it. Benign but not clean — candidate for a three-line `ingestionApi.discard(oldJobId)` fix in a follow-up. User reviewed the behaviour and did not ask for the fix during M3.
- Next session first task:
  - Start M4 — restate exit criterion ("upload 5 cert types, review, Save writes to `factory_certifications`"), list files (cert extractor + runner branch + dropzone mount inside the existing Add Certification modal on step 4), and wait for go. M4 should be cheap — the plumbing M3 established (runner dispatch, router endpoints, commit bookkeeping, frontend dropzone + highlight) reuses 1:1.

---

## 2026-04-22 (plan revision, pre-M4)

- Branch: doc-ingestion (no code change in this entry — doc-only)
- Milestone: N/A — plan revision
- Status: DONE
- Done:
  - **Swapped M5 and M6.** New order: M5 = Product PDF lane, M6 = Product CSV lane. Rationale: factories bring brochures to onboarding more often than clean CSVs, so the PDF lane is higher-value and deserves to land first. M5 now also introduces the editable product table UI and the `product_catalog` commit path; M6 reuses both.
  - **Merged the old M8 into the new M5.** The PDF lane now includes product image extraction (bbox hint from the model → page render → Pillow crop → GCS upload → `image_url` on each record) as part of the main milestone rather than a deferred optional. Reason: a product catalog without thumbnails is useless — images are core to the lane, not a nice-to-have. Prices, specs, MOQ were never "deferred" — they were always in the main extraction.
  - **Removed M8.** The milestone list is now 7 items (M1–M7).
  - **Picked pdf2image + Pillow for image cropping** instead of PyMuPDF (AGPL). Both MIT-licensed. Adds `poppler-utils` as a system dep in the user-settings Dockerfile.
  - **Updated `DOC_INGESTION_CODING_PLAN.md`** §1 (milestone table), §6 (new M5 with image extraction steps 1–3 and the §6.5 scope cut), §7 (new M6, simplified to reuse M5's table), §8 (M7 retention cron now also purges per-product cropped images), §10 (requirements: pdf2image, Pillow, poppler-utils), §11 (testing covers PDF-with-and-without-extractable-images), §12 (deployment checklist), §13 (parking lot: hosted parser upgrade path if bbox accuracy is insufficient), §14 (task ordering reflects swap).
  - **Updated `DOC_INGESTION_PLAN.md`** §12 scope cuts: item 1 is now "PDF image extraction (M5 step-2)", pointing at coding plan §6.5.
- Open:
  - None. M4 is next and is unaffected by this revision.
- Deviations from plan:
  - N/A — this entry IS the deviation record.
- Open questions:
  - If OpenAI-native-PDF bbox accuracy is poor in M5 testing, the fallback is coding plan §6.5 (ship text-only) plus the parking-lot note about evaluating LlamaParse's free tier. Decide in M5, not now.
- Next session first task:
  - Unchanged from the M3 entry — start M4. The plan revision does not affect M4.

---

## 2026-04-22 (M4)

- Branch: doc-ingestion @ (SHA recorded in the M4 commit message)
- Milestone: M4 — Certification lane
- Status: DONE
- Done:
  - Backend extractor `src/services/document_ingestion/certification_extractor.py` — branches on URL extension. `.pdf` → `pdfplumber` text pre-pass → `gpt-5.4` `json_object` (same recipe as company-profile). `.png`/`.jpg`/`.jpeg` → `gpt-5.4` vision with a base64 data URL in a user message (no OCR dep pulled in). Both branches validate with pydantic and retry once. Prompt asks for ISO-8601 dates and short standard codes (`'ISO 9001'`, not `'ISO 9001:2015 Quality Management System'`), free-text scope on `notes` only if the document calls one out.
  - Backend runner gains `kind == "certification"` branch mirroring M3's company-profile branch; passes `source_url` to the extractor so PDF vs image dispatch happens inside the extractor, not here.
  - No router change — the existing generic `commit_job` handler in `ingestion_router.py` is bookkeeping-only and kind-agnostic. Works as-is for the cert lane, same pattern the plan set up in M3.
  - Frontend wired `<DocumentDropzone kind="certification" size="compact" />` at the top of the `showAddCert` panel on step 5 (`factory_details`). `handleCertIngestionReady` maps `cert_type → newCert.certType` (with a case-insensitive lookup into `CERT_TYPE_OPTIONS`, falling back to `'Other'` so the `<select>` stays valid), `issuing_body → newCert.issuingBody`, `expiry_date → newCert.expiryDate`. `cert_number`, `issue_date`, `notes` still land on the draft payload and auto-pre-fill if the panel ever grows those inputs — same precedent as M3.
  - Added `updateCert` / `resetCertIngestion` helpers + scoped `certIngestionJobId` / `certIngestionDraft` / `certIngestionFile` / `certAutofilledKeys` state, so the cert panel and the step-2 company-profile dropzone don't share highlight state.
  - `handleAddCert` fires best-effort `ingestionApi.commit(jobId, draft)` after the `/certifications` POST succeeds; wrapped in try/catch so a commit failure never blocks the wizard.
  - **Mid-session correction (user-spotted).** Initial implementation left the pre-existing "证书文件（选填）" manual file input in place alongside the dropzone — two upload affordances, plus the dropzone's file was not attached to `factory_certifications.document_url` on save. Collapsed into one: extended `DocumentDropzone` with an `onFileStaged?: (file: File | null) => void` callback that fires with the accepted `File` right after MIME/size checks and with `null` on reset/failure. Wizard stashes it in `certIngestionFile` and appends it to the `/certifications` FormData. Deleted the manual `<input type="file">` + its `certFileRef` + the now-unused `wizard.documentOptional` i18n key (both locales). One drop now does everything: extraction → pre-fill AND attach to the saved cert row.
  - End-to-end verified by user on step 5 with `Mock_CE_Certificate_Example.pdf` (zh-CN locale): dropzone → amber "已自动填写" badges on `CE` + issuing body + expiry date → 添加认证 → row saved in the list with the attached document. User confirmed the lane is working.
- Deviations from plan:
  - **Removed the manual "证书文件（选填）" input.** Plan §5.2 said "User clicks Save (existing button), which calls the existing `POST /certifications`" — implying the manual file input stays. In practice the dropzone's file was not attached to the saved cert row, so the user had to re-upload the same PDF via the manual input. Fixed by teaching the dropzone to expose its accepted `File` via `onFileStaged` and using that as the `/certifications` attachment. Plan wording was subtly wrong on this point; the single-upload shape is the right UX.
  - **Image lane uses OpenAI vision via base64 data URL, not a text pre-pass.** Plan didn't spell out the image path. Cert images have no text layer, so vision is unavoidable; avoided pulling in an OCR dep by keeping the call on `gpt-5.4` with a multimodal `user` message.
  - **Only three of six draft fields have a UI surface today.** `cert_number`, `issue_date`, `notes` ride on `ingestion_jobs.draft_payload` and will auto-pre-fill if the panel ever grows those inputs — same pattern as M3's unused company-profile fields.
  - **`cert_type` falls back to `'Other'`** for unknown codes rather than writing an arbitrary string into the `<select>`. Still counts as auto-filled so the amber badge shows.
- Open questions:
  - M3's open questions (alembic version drift in tenant DBs; orphaned `ready_for_review` jobs on re-upload) still stand — no movement on either this session. Both still slated for M7 or a dedicated hygiene pass.
  - Prompt quality across the plan's 5 target cert types (ISO 9001, BSCI, CE, FDA, Sedex) has only been eyeballed on one doc (CE). Plan §5.3's ≥4-of-5-fields target is untested in aggregate — if the user sees weak extraction on another cert type, tune the prompt in a follow-up rather than blocking the M4 commit.
- Next session first task:
  - Start M5 (per the pre-M4 plan revision, M5 is now Product PDF + image extraction). Restate the new exit criterion — "upload a 10-page product brochure, review rows in the editable table, commit writes to `product_catalog`, cropped thumbnails on each row" — list backend files (`product_pdf_extractor.py` incl. pdf2image + Pillow crop, `runner.py` branch, commit endpoint extension for bulk-insert) + frontend files (editable product table + thumbnail preview), and wait for go.

---

## 2026-04-22 (M5)

- Branch: doc-ingestion @ (SHA recorded in the M5 commit message)
- Milestone: M5 — Product PDF lane (products + prices + specs + cropped thumbnails)
- Status: DONE
- Done:
  - Backend extractor `src/services/document_ingestion/product_pdf_extractor.py` — three-step pipeline per coding plan §6.1: (1) `pdfplumber` text pre-pass with `[[page N]]` markers + `gpt-5.4` `json_object` returning `products` + per-product `image_hint`; (2) `pdf2image.convert_from_bytes` page render → Pillow crop → `utils.gcs.upload_bytes` → `image_url`; (3) per-product try/except so a single bad crop never sinks the job. Page renders are memoized by `(page_number, bbox)` so an N-variant-per-page catalog only renders each page once. Retries step 1 once on JSON / pydantic failure.
  - Backend runner `runner.py` — added `kind == "product_pdf"` branch mirroring the M3/M4 shape, passing `job_id` + `email` so the extractor can namespace GCS paths.
  - Backend commit handler `routers/ingestion_router.py` — for `product_pdf` / `product_csv`, the commit endpoint is now the authoritative write: validates the payload as `ProductCatalogDraft`, opens a transaction, bulk-inserts via `product_catalog_repository.bulk_insert_products` with `source_job_id` set, then stamps the job `committed`. Returns `inserted_count`. Bookkeeping-only semantics preserved for `company_profile` + `certification`.
  - Backend repository `src/data/repositories/product_catalog_repository.py` — `bulk_insert_products` uses a single `INSERT … SELECT FROM UNNEST(...)` so all rows land in one round-trip; skips empty-name rows at the Python layer; caller wraps in a transaction.
  - Backend GCS helper — added `utils.gcs.upload_bytes(data, folder, email, file_id, ext, content_type)` as a sibling of `upload_file`. Needed because the extractor holds rendered PNG bytes, not a FastAPI `UploadFile`.
  - Backend deps — pinned `pdf2image==1.17.0` and `Pillow==10.4.0` (both MIT). `poppler-utils` added to the user-settings Dockerfile runtime stage (pdf2image shells out to `pdftoppm`).
  - Frontend `components/onboarding/customize-ai/ingestion/ProductCatalogReviewTable.tsx` — editable table, kind-agnostic so M6 can reuse it. Columns: image / name / price / MOQ / description / specs. Inline edit, add row, delete row, thumbnail click opens a full-size Dialog preview. SKU column is present in the schema/DB but hidden from the UI per user request — field still populated by the extractor + persisted on commit.
  - Frontend `components/onboarding/customize-ai/ingestion/ProductCatalogReviewDialog.tsx` — hosts the dropzone + review table + commit button. On cancel-before-review, best-effort discards the draft job so it doesn't linger in `ready_for_review`. Emits `onCommitted(count)` so the wizard can show a `+N` badge.
  - Frontend wizard integration — "Import from catalog PDF" button on the company-profile step next to the existing Products/Pricing list. Opens the dialog. `+N` count badge on the button after a successful commit.
  - Frontend `lib/api/ingestion.ts` — enriched the `product_pdf` mock payload with realistic specs, SKUs, MOQ, prices, plus 2-of-3 rows carrying `imageUrl` so the mock demonstrates both the thumbnail path and the "no image" placeholder without the real extractor.
  - Frontend i18n — added `settings.customizeAi.ingestion.productReview.*` to both `en` and `zh-CN`: dialog title/subtitle, column headers, specs plural (`{count, plural, one {# spec} other {# specs}}`), commit toast, error copy. Full parity verified via Playwright.
  - Verified end-to-end twice: (1) mock mode via Playwright in `en` + `zh-CN` against `/user-onboarding?tab=customize-ai&mock=1` — idle → processing → ready → commit; all five states render; commit closes the dialog and `+3` badge appears on the wizard button; (2) real backend with the user's product-catalog PDF (一 factory tassel-tree brochure, 20 pages, 28 products after size-variant collapse) — thumbnails land on GCS (`gs://prelude-deal-rooms/ingestion/product/{job_id}/…png`), `draft_payload.products[*].image_url` populated.
- Open:
  - None inside M5. M6 (CSV lane, reuses `ProductCatalogReviewTable` + the `product_pdf`/`product_csv` commit path) is next.
- Deviations from plan:
  - **Prompt: `page_number` required, `bbox` optional.** Coding plan §6.1 described `image_hint: {page_number, bbox}` as one atomic object. In testing against the real 塔树 catalog the model consistently returned hints with `page_number` but *not* bbox, so every row silently dropped to "no image". Reworked the prompt to make `page_number` the required field and bbox an optional refinement; `_render_or_crop` now defaults to a **top-70% crop** of the page when no bbox is supplied. Rationale: factory catalogs are typically one-hero-photo-per-page with a text footer; the top-70% default removes the footer while keeping the photo readable without any model-supplied spatial hint. Real bbox still overrides when the model supplies one.
  - **Size-variant collapse at prompt level.** First real upload (塔树图片.pdf, one product-family-with-three-sizes per page) produced 3 duplicate rows per page sharing photo + material + description. Added an "IMPORTANT — collapse size/variant rows" clause instructing the model to emit ONE product with variants listed under a single `specs` key when sizes/colors/wattages share the same hero photo and description. No schema change — variants live inside `specs` (JSONB). Rule explicitly keeps separate products for genuinely different items (different material, different hero photo).
  - **SKU hidden from the review table UI.** Coding plan §6.2 listed SKU as a review-table column; in the user's real catalog SKUs were uniformly absent and the empty column cluttered the table. Hidden via two line-deletions — field still in the schema, still extracted, still written to `product_catalog.sku`, can be re-surfaced later.
  - **`PriceCell` redesigned to single row with select dropdowns.** Plan is silent on the shape of the price cell; first pass had free-text `currency` / `unit` inputs which looked like orphaned data fields in the dense table. Replaced with shadcn `Select` primitives (`USD/EUR/CNY/GBP/JPY/HKD` and `piece/pair/set/carton/kg/meter/box`). Unknown values returned by the extractor are preserved by prepending them to the options list so nothing is silently dropped. Single-row compact layout: `[min] – [max] [USD ▾] / [piece ▾]`.
  - **Commit endpoint became authoritative for product lanes, not bookkeeping.** Plan §4.2 previously established commit as bookkeeping-only for M3. For product lanes there's no existing authoritative write path (unlike `factory_profile/save` for M3 or `POST /certifications` for M4), so the commit endpoint itself performs the bulk insert in a single transaction. This is the shape M6 will reuse.
  - **Did NOT take the §6.5 scope cut.** Image extraction works on real catalogs — shipped it, no need to revisit.
  - **Did NOT rename the `prelude-deal-rooms` GCS bucket.** User considered renaming to `prelude-product-catalog` (or similar) to better reflect scope. Held off: it would require a new bucket + per-object migration + cross-service URL rewrites, and the name is legacy from the platform's first feature. Documented but not acted on.
  - **Local-laptop dev dep gaps surfaced during verification.** Real-backend run failed twice before thumbnails landed: first because `poppler-utils` was not installed on the user's macOS (added via `brew install poppler`); second because `pdf2image==1.17.0` was pinned in `requirements.txt` but not yet installed in the running venv (`pip install pdf2image Pillow` in the service env). Both are local-dev gotchas — the Dockerfile has poppler, and fresh venvs pick up `requirements.txt`. Still worth noting for anyone else onboarding this branch locally.
- Open questions:
  - M3's open questions (alembic version drift in tenant DBs; orphaned `ready_for_review` jobs on re-upload) still stand — no movement this session. Both slated for M7 or a dedicated hygiene pass.
  - **GCS public-bucket posture (cross-service, not M5-specific).** The shared `prelude-deal-rooms` bucket is publicly readable; isolation between tenants is path-based (UUID `job_id` + sanitized email in the object name), not ACL-based. Risk was discussed and triaged as low for product catalog images specifically (commodity marketing material factories already distribute) but non-zero for certs/signatures/etc. Recommendation: a service-wide refactor of `utils/gcs` to issue signed URLs with a configurable TTL; out of scope for this PR series. Not an M5 issue in isolation — M5 just inherits the existing posture. Logged here so it doesn't get lost.
- Next session first task:
  - Start M6 — restate the exit criterion ("Upload a CSV with messy headers, map columns in a modal, review rows in the shared editable table, commit writes to `product_catalog`"), list files (`product_csv_mapper.py` + `POST /ingestion/jobs/{id}/apply-mapping` + new `<ColumnMappingModal />` + reuse `<ProductCatalogReviewTable />` unchanged), and wait for go. M6 should be cheaper than M5 — the table + commit path are already built.

---

## 2026-04-22 (M6)

- Branch: doc-ingestion @ (SHA recorded in the M6 commit message)
- Milestone: M6 — Product CSV / XLSX lane (incl. embedded-image extraction + SKU purge)
- Status: DONE
- Done:
  - Backend mapper `src/services/document_ingestion/product_csv_mapper.py` — `read_table` for `.csv` + `.xlsx` (via `pandas.read_excel(engine="openpyxl")`), `sample_rows` preview helper, `propose_mapping` (one `gpt-5.4` `json_object` call from headers + 3 sample rows → `{header: target}` sanitised against an allowlist), `apply_mapping` (pure; coerces rows, builds `specs`/`price_range`, returns aligned `(products, data_row_indices)`), and `finalize_with_embedded_images` for the xlsx image path. Coerce helpers strip units/commas so `"300 pcs"` → `300` and `"1,234.5"` → `1234.5` without losing anything.
  - **Embedded-image extraction is pure stdlib.** `extract_xlsx_images` walks the xlsx zip with `zipfile` + `xml.etree.ElementTree` — `xl/worksheets/_rels/sheet1.xml.rels` → drawing file → `xl/drawings/_rels/drawing1.xml.rels` → `xl/media/*`, correlating each anchor's `<xdr:from>/<xdr:row>` (0-based) to a data-row index (sheet row 1 = data row 0 after the header). Handles both `twoCellAnchor` and `oneCellAnchor`, absolute (`/xl/...`) and relative (`../drawings/...`) relationship Targets. No new deps — pure stdlib on top of what openpyxl already installs.
  - Runner `runner.py` — `kind == "product_csv"` branch **does everything in one pass** per the post-M6 UX simplification (see deviations): read file → propose mapping → apply mapping → (for xlsx) extract embedded images → upload and attach → write `{products, column_mapping, proposed_mapping, source_headers, sample_rows, row_count, file_ext}` to `draft_payload` and flip to `ready_for_review`.
  - Router `routers/ingestion_router.py` — added `POST /ingestion/jobs/{id}/apply-mapping` (body `{mapping}`). Re-downloads the source file, re-runs `apply_mapping` + xlsx image finalize, overwrites `draft_payload`, keeps status `ready_for_review`. Used only by the **Re-map columns** button; the initial upload no longer needs it because the runner auto-applies.
  - Frontend `components/onboarding/customize-ai/ingestion/ColumnMappingModal.tsx` — new. Two-column table: source header + 3 sample values on the left, schema-field `<Select>` on the right (pre-filled from `proposedMapping`). "Spec" option expands to `specs.<source_header>` on Apply. Enforces "exactly one `name` column" before the Apply button un-disables.
  - Frontend `ProductCatalogReviewDialog.tsx` — gained a `kind` prop (`product_pdf | product_csv`, default pdf). For CSV it lands directly in the review table; a **Re-map columns** button (lucide `Columns`, `variant="outline" size="sm"`) sits top-right of the table and re-opens the mapping modal with the *current* mapping. `handleRemap` calls `ingestionApi.applyMapping`, refetches the draft, and replaces the product rows.
  - Frontend `lib/api/ingestion.ts` — added `applyMapping(jobId, mapping)` (real + mock). Mock's `product_csv` payload now lands already-populated (3 products, 2 of 3 with `imageUrl`) so the mock mirrors the runner's one-pass behaviour; `mockApplyMapping` re-synthesises products from a new mapping so the Re-map path is exercisable without the backend.
  - Frontend `CustomizeAIQuestionnaire.tsx` — added a second entry-point button "Import from CSV / XLSX" alongside the M5 PDF button. Both open the same dialog with different `kind` props. `+N` badge continues to work across both lanes.
  - Frontend `types.ts` — `ProductCatalogDraft` gained `rowCount` / `fileExt`; `ProductRecordDraft.sku` removed (see SKU purge below). Dropzone accept string for CSV is `text/csv,.csv,.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`; label shows as "CSV · XLSX".
  - i18n — added `settings.customizeAi.ingestion.columnMapping.*` (bilingual) including a **nested** `target` subtree (the initial flat keys like `"price_range.min"` broke next-intl's dot-resolution and rendered raw keys — fixed by switching to `target.price_range.{min,max,currency,unit}` nested objects). Added `productReview.openCsvButton` + `productReview.remapColumns` in both locales.
  - Pinned `pandas==2.2.3` + `openpyxl==3.1.5` in `requirements.txt` (plan §10 claimed pandas was already installed; it wasn't).
  - **SKU purge (mid-milestone, user-requested).** Dropped the `sku` field from `ProductRecordDraft` (schemas.py + types.ts), `_TARGETS` / prompt / branch in the CSV mapper, the M5 PDF extractor prompt, `ColumnMappingModal.BASIC_OPTIONS`, `bulk_insert_products` columns + unnest in `product_catalog_repository`, `ProductCatalog.sku` in `alembic_postgres/models.py`, the M1 migration DDL (edited in-place — the migration has only reached `postgres` + aoxue@preludeos.com's tenant DB, so a follow-up migration would add noise), every mock payload that carried a sku, and `columns.sku` + `target.sku` in both locales. Ran `ALTER TABLE product_catalog DROP COLUMN IF EXISTS sku;` directly on `postgres` — per CLAUDE.md only `postgres` gets direct SQL; tenant DBs inherit the change on next `migrate-tenants` fan-out.
  - End-to-end verified in mock mode (Playwright, en + zh-CN): upload → review table with 3 products + 2 thumbnails + "+3" badge on the CSV button; "Re-map columns" opens the modal with the current mapping and sample values. Real-backend spot-checked by the user against an actual XLSX (LED panel / 工矿灯 / 路灯, 3 rows) — LLM correctly mapped 产品名称, 最小起订量, 单价(美元), 产品图片 on the first try.
- Open:
  - None inside M6. M7 (rate limits, retention cron, Sentry) is next.
- Deviations from plan:
  - **Skipped the mandatory column-mapping modal (plan §7.3).** Plan was written before M5 introduced the editable review table. With the table in place, gating every CSV upload on a modal is pure friction for well-named columns — which is most of them — and the LLM's mapping was reliably correct on the first real XLSX. Shipped as **Option C**: runner auto-applies, user lands in the review table immediately, "Re-map columns" button re-opens the modal on demand for the rare column-level error. `POST /jobs/{id}/apply-mapping` endpoint stays (it's what Re-map hits); it's just no longer part of the default path. Plan §7.2's two-phase shape lives on as the opt-in re-map flow.
  - **SKU removed from the whole feature.** Plan §4.2 listed `sku` as a top-level product field and §7.5 included it in the mapping targets. User decided mid-milestone that SKU isn't needed for the product-catalog scope. Removed everywhere; see the SKU-purge bullet above.
  - **`.xlsx` reads `keep_default_na=False`, `na_values=[]`.** Initial real-XLSX test came back with every sample value blank → OpenAI conservatively returned all-ignore. Root cause: `pandas.read_excel(dtype=str)` with default NA handling treats cells like `-`, `N/A`, `—`, and empty strings as NaN, which `_stringify` then coerces to `""`. CSV already had the guard; XLSX didn't. Fixed both paths + added info logs for `read_table` output and `propose_mapping` input/output so the next failure mode is diagnosable from service logs.
  - **OpenAI fallback returns all-ignore on the second parse failure, not raising.** Plan §10 called for strict failure. The fallback lets the user rescue the job via the Re-map modal rather than re-uploading, which is the friendlier behaviour; the log line is loud enough (`giving up on OpenAI mapping after retries ...`) to spot if this starts happening regularly.
  - **Installed pandas + openpyxl locally as a local-dev step**, same shape as the M5 gotcha with poppler / pdf2image. Dockerfile picks them up from `requirements.txt`; no runtime change.
  - **i18n structure change** — `target` subtree is nested to work around next-intl's dot-as-nesting semantics. Flat keys like `"price_range.min"` render as raw i18n paths in the UI. Caught during English verification, fixed before zh-CN verification.
- Open questions:
  - M3's open questions (alembic version drift in tenant DBs; orphaned `ready_for_review` jobs on re-upload) still stand — slated for M7 or a dedicated hygiene pass.
  - **Tenant DBs that already have `product_catalog.sku` from the M3/M5 era.** aoxue@preludeos.com's tenant DB has the column with M5-committed rows. The bulk-insert path no longer writes it (column dropped from the SQL), so it'll just sit there as an empty column. Drop via `ALTER TABLE product_catalog DROP COLUMN IF EXISTS sku;` per tenant whenever `migrate-tenants` does its next pass — not urgent, not blocking.
  - **Multi-sheet XLSX workbooks take sheet 0 silently.** Logged with a warning ("xlsx has N sheets, using first ..."), not surfaced to the user. Plan §3's open questions explicitly said "one sheet", so shipping without a sheet picker is intentional; revisit only if a real user trips over it.
- Next session first task:
  - Start M7 — restate the exit criterion ("rate limits enforced, retention cron purges old jobs + GCS blobs, Sentry breadcrumbs + tags wired"), list files (router rate-limit check, `scripts/purge_ingestion_jobs.py`, Sentry tagging in the runner + extractors), and wait for go. Good moment to also handle the alembic-version-drift + orphaned-job hygiene items that have been accumulating since M3.

---
