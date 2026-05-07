# Storefront — Phase 2: Replace MVP Mocks

Follow-up to `storefront_quote_request_plan.md`. The MVP shipped intentionally on hardcoded data so the quote-request plumbing could go in without product-persistence work blocking it. This doc is the punch list to swap each mock out for real per-tenant data.

## Current state (what is mock, where it lives)

### 1. Product catalog — **highest priority**

| Layer | File | Symbol |
|---|---|---|
| Backend | `prelude/prelude-crm/routers/public_storefront_router.py` | `_MOCK_PRODUCTS` (10 items, 4 with `status='live'`) |
| Frontend (seller draft view) | `prelude/prelude-frontend-next/components/storefront/mockData.ts` | `INITIAL_PRODUCTS` |
| Frontend (visual lookup) | same file | `REAL_IMG`, `BG_MAP` |
| Frontend (illustrations) | `prelude/prelude-frontend-next/components/storefront/productIllustrations.tsx` | per-`kind` SVG illustrations |

**Effect today:** Every public storefront — `postgres`, `prelude_visitor`, anyone — shows the same four live products. The storefront isn't actually multi-tenant.

**Effect on quote-requests:** `deals.product_name` is whatever the buyer's modal sent, which is whatever the buyer clicked from the mock catalog. So the deal name like `"Quote: 14" Carbon Steel Wok"` reflects mock data, not what the seller actually sells.

### 2. Seller's draft-tab content (all of `未上架`)

`mockData.ts` exports the following and `StorefrontDraftView.tsx` reads them directly. Submitting the draft does **not** persist anywhere:

- `DEFAULT_COMPANY_FIELDS` — name, tagline, year, headcount, capacity, export share
- `DEFAULT_BUSINESS_TERMS` — MOQ, lead time, sample policy, shipping, payment
- `DEFAULT_CONTACT` — name, title, email, phone
- `INITIAL_CERT_FILES` — six fake filenames + sizes
- `COMPANY_PDF` — placeholder
- `FACTORY_IMAGES` — eight Unsplash stock URLs

The buyer-facing public page doesn't render any of this today — it shows only `tenant_subscription.company_profile` (seller name) and the mock product grid. So even if the seller "filled in" the draft, buyers never see it.

### 3. `LAST_UPDATED_AT`

Hardcoded string `'2026-04-22 14:30'` in `mockData.ts`. Surfaced in the seller's submit-zone caption (`captionPending` / `captionLive`).

### 4. Dead exports (safe to delete)

- `LIVE_STOREFRONT_URL` in `mockData.ts` — no longer imported anywhere after the 查看店铺 button started reading from JWT claims.

### 5. Hardcoded English buyer copy

`PublicStorefrontView.tsx` has `"Browse products below and request a quote — the supplier will reply by email."` and `"Storefront"` / `"Products"` labels in plain English. Intentional per MVP plan; only matters if Phase 2 wants a bilingual buyer page.

---

## Replacement plan

### Phase 2A — Real product persistence (unblocks multi-tenant storefront)

**Schema** (Alembic migration on `alembic_postgres`):

```sql
CREATE TABLE storefront_products (
  product_id     uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  sku            varchar(64)   NOT NULL,
  kind           varchar(32)   NOT NULL,    -- pan/pot/wok/...
  name_en        text          NOT NULL,
  name_zh        text,
  category_en    varchar(64),
  category_zh    varchar(64),
  spec_en        text,
  spec_zh        text,
  status         varchar(16)   NOT NULL DEFAULT 'pending',  -- pending|live
  published_at   timestamptz,
  created_at     timestamptz   NOT NULL DEFAULT now(),
  updated_at     timestamptz   NOT NULL DEFAULT now(),
  UNIQUE (sku)
);
CREATE INDEX idx_storefront_products_status ON storefront_products(status);
```

This must land on every tenant DB (`migrate-tenants` skill).

**Backend changes:**

- `public_storefront_router.py` GET `/public/storefront/{slug}`: `SELECT * FROM storefront_products WHERE status='live' ORDER BY published_at DESC` instead of returning `_MOCK_PRODUCTS`. Delete `_MOCK_PRODUCTS`.
- New auth'd router (`storefront_admin_router.py` or extend `public_storefront_router.py`):
  - `GET /api/crm/storefront/products` — seller lists all (pending + live)
  - `POST /api/crm/storefront/products` — create
  - `PUT /api/crm/storefront/products/{id}` — edit
  - `POST /api/crm/storefront/products/{id}/publish` — flip status to `live` and stamp `published_at`
  - `DELETE /api/crm/storefront/products/{id}`

**Frontend changes:**

- `StorefrontClient.tsx`: replace `useState<Product[]>(INITIAL_PRODUCTS)` with a fetcher hook (`useStorefrontProducts()`) that hits the new auth'd endpoint.
- `StorefrontCatalog`'s **Publish** button: wire to `POST /products/{id}/publish` instead of in-memory mutation.
- `mockData.ts`: delete `INITIAL_PRODUCTS`, `LAST_UPDATED_AT`, `LIVE_STOREFRONT_URL`.
- `productIllustrations.tsx` and `REAL_IMG`/`BG_MAP` lookups can stay — they're keyed by `kind`, which is data, not mock content.

**Quote-request impact:** `deals.product_name` and `interaction_details.content.product_sku` already flow through verbatim from the modal — no backend changes needed once products come from the new table.

### Phase 2B — Persist seller's company / business-terms / contact / certs

The data already has a home: `tenant_subscription.company_profile` and `tenant_subscription.factory_details` are existing JSONB columns. The seller's draft form should write into them; the public storefront GET should also surface them so buyers see real factory info, not just a name.

**Schema:** No migration needed — JSONB extension only.

Suggested shape:

```jsonc
// tenant_subscription.company_profile
{
  "companyNameEn": "...",
  "companyNameZh": "...",
  "tagline": "...",
  "yearEstablished": 2008,
  "headcount": 120,
  "annualCapacity": "180万件",
  "exportShare": "92%",
  "logoUrl": "...",
  "businessTerms": {
    "moq": "...",
    "leadTime": "...",
    "samplePolicy": "...",
    "shipping": "...",
    "payment": "..."
  },
  "primaryContact": {
    "name": "...",
    "title": "...",
    "email": "...",
    "phone": "..."
  }
}
```

**Backend:**

- `factory_profile_router.py` (in `prelude-user-settings`) already handles `company_profile` GET/PUT for the auth'd seller. Extend its schema to accept the new fields above.
- `public_storefront_router.py` GET response: add `companyProfile` and `factoryDetails` blocks (already parsed in the GET — see `_parse_jsonb`/`_seller_display_name`). Surface terms + contact for the buyer page.

**Frontend:**

- `StorefrontDraftView.tsx`: replace local-state-only fields with values from `useFactoryProfile()` (or equivalent existing hook). Persist on save via the existing factory-profile PUT.
- `PublicStorefrontView.tsx`: render company tagline, terms, primary contact, factory photos when present.
- `mockData.ts`: delete `DEFAULT_COMPANY_FIELDS`, `DEFAULT_BUSINESS_TERMS`, `DEFAULT_CONTACT`.

**Cert files + factory images:** Reuse existing `factory_certifications` table for certs (already populated in some tenants). For factory images, either:
- (Simpler) JSONB array of URLs in `factory_details.photoUrls` — already in use for the deal-room.
- (Cleaner) New `factory_photos` table with display order.

### Phase 2C — Real `last_updated_at`

Cheapest path: read `MAX(updated_at)` across `storefront_products` and `tenant_subscription.updated_at`, return as `lastUpdatedAt` in the auth'd seller-side fetch and the public GET. Replace `LAST_UPDATED_AT` constant in `mockData.ts`.

### Phase 2D — Cleanup

- Delete `LIVE_STOREFRONT_URL` and any other unused exports from `mockData.ts`.
- If the file ends up empty/near-empty, delete it.
- Decide on bilingual buyer page (currently English-only by design).

---

## Out of scope (still phase 3+)

- Storefront token + revocation (private share links). Today the slug is the public `db_name`.
- Buyer analytics (view tracking, time-on-page) — deal-room has this; storefront could mirror.
- Email notification to seller on new quote-request — currently they see it on next `/crm` load (the deals page already auto-refreshes on mount).
- Storefront publish/unpublish toggle (per-tenant kill switch).
- Per-product images managed by the seller (today we key off `kind` and use a fixed Unsplash URL).

---

## Verification checklist for Phase 2A

- [ ] Two tenants with different `storefront_products` rows show different products on their public storefront.
- [ ] Publishing a product flips `status` and timestamp; buyer sees it on next GET.
- [ ] Quote-request still creates a deal whose `product_name` matches what the buyer clicked.
- [ ] Deleting a product removes it from the public storefront immediately.
- [ ] Mock arrays no longer imported anywhere (`grep -rn "INITIAL_PRODUCTS\|_MOCK_PRODUCTS"` returns nothing).
