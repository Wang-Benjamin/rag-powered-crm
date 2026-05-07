# Storefront (店铺) — Frontend Port Record

Handoff doc for the new "店铺 / Storefront" page under the Pipeline section
(alongside 我的线索 and 交易室). This branch ships the **frontend UI only**
against in-memory mock data. Backend wiring is the next phase — see
"Backend work required" at the bottom.

Source mock: `prelude/prelude-user-settings/src/docs/Storefront.html` —
an 8,354-line standalone HTML/CSS/JS prototype from design. The prototype
is a self-contained page with three stateful views (Draft / Pending / Live),
Prelude design-kit tokens, vanilla JS interactions, and mock product imagery.

## What shipped

### Route & navigation
- New route: `/[locale]/workspace/[workspaceId]/storefront`
  - Sits outside the `(crm)` route group so it doesn't inherit the CRM
    subscription gate or `CRMProvider`. Uses the standard workspace layout
    (sidebar + content shell).
- Sidebar entry: third flat item in the Pipeline section of
  `components/layout/sidebar/SidebarMenu.tsx`, route `/storefront`. No
  `requiresPaid` flag — open to everyone on the workspace.
- Language toggle wiring: already handled by the existing sidebar language
  switch; the page re-renders in the selected locale automatically.

### i18n
- New namespace `storefront`, registered in `i18n/request.ts` and in the
  `Messages` type in `global.d.ts` so `useTranslations('storefront')` is
  type-safe.
- Translation files:
  - `messages/zh-CN/storefront.json` — source Chinese, ported from the HTML mock.
  - `messages/en/storefront.json` — English translation (no pre-existing
    English copy; translated during this port; review recommended).
- Added `items.storefront` ("店铺" / "Storefront") to both
  `messages/zh-CN/navigation.json` and `messages/en/navigation.json`.

### Component tree
All under `components/storefront/`:

| File | Purpose |
| --- | --- |
| `StorefrontClient.tsx` | Top-level client shell — state tabs, view routing, submit zone, mock-data state |
| `StorefrontDraftView.tsx` | Draft form — company info, certifications, business terms, factory photos, contact |
| `StorefrontCatalog.tsx` | Pending + Live catalog (shared component, takes `status` prop) — search, bulk-action bar, grid |
| `ProductCard.tsx` | Single product card — select checkbox, status pin, name, category, spec line, action buttons |
| `ProductMedia.tsx` | Unsplash image with graceful fallback to inline SVG illustration |
| `productIllustrations.tsx` | 11 hand-inlined SVG silhouettes (pan / pot / wok / saucepan / cast / steamer / set / bakeware / utensil / mixingbowl / kettle) |
| `primitives.tsx` | Reusable small pieces: `SectionShell`, `Dropzone`, `FileChip`, `Disclosure`, `Field`, `TextInput`, `TextArea`, `Notice`, `FieldRow` |
| `mockData.ts` | All seed data — products, certifications, company fields, business terms, contact, factory photo URLs |
| `types.ts` | `Product`, `ProductKind`, `ProductStatus`, `StorefrontView` |

Page entry: `app/[locale]/workspace/[workspaceId]/storefront/page.tsx` —
thin server wrapper that renders `<StorefrontClient />`.

### Styling decisions
Initial port used Prelude design-kit tokens (`bg-bone`, `bg-paper`,
`text-deep`, Instrument Serif display font, mono tracking-wider labels).
That looked inconsistent with the rest of the app, which is still on the
zinc palette. Final pass re-skinned everything to the app baseline while
keeping the layout identical:

- Page bg: `bg-zinc-50`. Card bg: `bg-white` with `border border-zinc-200`.
- Text: `text-zinc-900` / `text-zinc-700` / `text-zinc-500` (primary /
  label / muted). No `font-display` — default Geist sans everywhere.
- Primary button: `bg-zinc-900 text-white hover:bg-zinc-800`.
- Status pins: live = `bg-green-100 text-green-700`, pending =
  `bg-yellow-100 text-yellow-700`.
- Yellow-500 accent left border on any warning-flavored notice
  (e.g. "请勿填写价格" business-terms notice).
- Product media fallback: neutral `bg-zinc-100` (retired the per-kind
  warm OKLCH `BG_MAP` — kept the export in `mockData.ts` but it's unused).

`@keyframes pc-enter` added to `app/styles/animations.css` for the
publish-to-live card entrance animation (matches the original mock's
0.3s ease).

### Interactivity (all client-side, mock-only)
- State tabs (Draft / Pending / Live) persist to `localStorage` under
  `storefront_page`.
- Disclosure (hide / show manual company fields) — plain `useState`.
- File chips + factory thumbnails — removable via local state.
- Language chips (中文 / 英文 / 双语) — local toggle state.
- Product selection + bulk publish + search — all in `useState` inside
  `StorefrontCatalog`.
- Publish flow: 260ms scale-down / opacity-out → status flip in state →
  card re-appears in live grid with `pc-enter` animation; bulk publish
  staggers individual moves by 60ms.
- Image fallback chain: `REAL_IMG[kind]` URL → on `onerror` swap to the
  inline SVG illustration.

### Mock data in use
Everything a backend would eventually hydrate is in `mockData.ts`:

- `INITIAL_PRODUCTS` — 10 products (6 pending, 4 live) with bilingual
  names, categories, specs.
- `INITIAL_CERT_FILES` — 6 cert PDFs with sizes.
- `COMPANY_PDF` — single staged company profile.
- `DEFAULT_COMPANY_FIELDS`, `DEFAULT_BUSINESS_TERMS`, `DEFAULT_CONTACT`
  — draft form defaults.
- `FACTORY_IMAGES` — 8 Unsplash URLs (verified 200 at port time).
- `LIVE_STOREFRONT_URL` — hard-coded `prelude.trade/storefront/yuanhe-kitchenware`.
- `LAST_UPDATED_AT` — hard-coded `2026-04-22 14:30`.
- `REAL_IMG` / `BG_MAP` — per-kind product imagery.

## Two user-driven changes post-initial-port

1. Retired the "已上线" top banner (storefront URL + last-updated block)
   from the Live view. The public-storefront link is still reachable
   through the "查看店铺" button in the catalog toolbar.
2. Added real Unsplash factory photos in the factory-images grid (was
   grey `<ImageIcon />` placeholders). `onError` fallback keeps the icon
   as a safety net if any URL ever 404s.

## Out of scope for this branch
- Real upload handling (PDFs, images) — dropzones are visual-only.
- "Add product" / "Edit product" flows — buttons present, no modals.
- Dark mode polish — zinc-palette only, matches the rest of the app.
- Any server-side persistence.
- Analytics, audit trail, validation.

## Backend work required (next phase)

### Data model
One Storefront row per tenant, plus many Products. Suggested shape:

```
storefront
  tenant_id           FK
  slug                unique, used in public URL
  company_pdf_url     S3 pointer, nullable
  company_name        text
  tagline             text
  year_established    int
  staff_count         int
  annual_capacity     text (free-form; the mock uses "180 万件")
  export_share        text (free-form; the mock uses "92%")
  moq                 text
  lead_time           text
  sample_policy       text
  shipping_terms      text
  payment_terms       text
  contact_name        text
  contact_title       text
  contact_email       text
  contact_phone       text
  contact_languages   text[]    -- ['zh', 'en', 'both']
  published_at        timestamptz nullable  -- null = draft/pending, set = live
  last_updated_at     timestamptz

storefront_certification
  storefront_id       FK
  name                text
  s3_key              text
  size_bytes          int
  uploaded_at         timestamptz

storefront_factory_image
  storefront_id       FK
  s3_key              text
  sort_order          int
  uploaded_at         timestamptz

storefront_product
  id                  FK
  storefront_id       FK
  status              enum('draft','pending','live')
  kind                text        -- matches ProductKind enum in types.ts
  name_zh             text
  name_en             text
  category_zh         text
  category_en         text
  spec_zh             text
  spec_en             text
  image_url           text        -- or FK to a product_image table
  published_at        timestamptz nullable
```

The Draft/Pending/Live view distinction maps to:
- Draft = storefront row exists but `published_at IS NULL` and no pending
  products yet (factory still filling in company info).
- Pending = storefront details filled in, products in `status='pending'`
  awaiting publish.
- Live = `published_at IS NOT NULL` AND product is `status='live'`.

### API endpoints (proposed, under `prelude-user-settings`)
- `GET  /storefront` — current tenant's storefront + products
- `PUT  /storefront` — update company info / business terms / contact
- `POST /storefront/certifications` — multipart upload (or presigned URL flow)
- `DELETE /storefront/certifications/:id`
- `POST /storefront/factory-images` — same pattern
- `DELETE /storefront/factory-images/:id`
- `POST /storefront/products` — add new product (draft)
- `PUT  /storefront/products/:id` — edit
- `DELETE /storefront/products/:id`
- `POST /storefront/products/:id/publish` — flip to `status='live'`,
  stamp `published_at=now()`
- `POST /storefront/products/publish` — bulk (take `ids[]`)
- `POST /storefront/publish` — publish the whole storefront
  (sets `published_at` on the storefront row; buyers can now hit the
  public URL)

All endpoints go through the existing `/api/proxy/user-settings/*`
pattern with automatic JWT routing (no `dbName` / `userEmail` params).

### Frontend wiring that will be deleted
In `StorefrontClient.tsx` / `StorefrontCatalog.tsx` / `StorefrontDraftView.tsx`:
- Replace `useState(INITIAL_PRODUCTS)` with a data-fetching hook
  (`useStorefrontProducts()` → `storefrontApi.listProducts()`).
- Replace the `publish()` function's local state mutation with an API call
  + optimistic update / refetch.
- Replace default-company / default-terms / default-contact with
  form-state hydrated from `GET /storefront`.
- Add error / loading states (currently none — mock data is always present).
- Wire Dropzone + file-chip remove to real upload / delete endpoints.
- Convert localStorage-backed view persistence to URL query param
  (`?view=draft|pending|live`) so it deep-links and survives sign-out.

### Things to delete entirely
- `components/storefront/mockData.ts` — retire the entire file once the
  API is live.
- `productIllustrations.tsx` and the `REAL_IMG` / `BG_MAP` fallbacks in
  `ProductMedia.tsx` — keep only if we want the illustrated fallback
  when a product has no uploaded photo; otherwise delete and just render
  a neutral placeholder.
- `FACTORY_IMAGES` constant — replaced by a `GET /storefront/factory-images` list.

### Auth / tenancy
Everything is scoped per tenant via the existing JWT pattern. One
storefront per tenant. The public-facing URL (`prelude.trade/storefront/<slug>`)
lives on a separate unauthenticated route that reads directly from the
`storefront` + `storefront_product` tables filtered to `published_at IS NOT NULL`.
Not in scope for this ticket, but worth coordinating on the slug column.

### Migrations
Add all four tables via a new Alembic migration in `alembic_postgres`
(per-tenant business DB, not `alembic_analytics`). Remember to fan the
migration out to every tenant DB via the `migrate-tenants` skill.

## Verification done on this branch
- `tsc --noEmit` clean (only pre-existing stale `.next/types` staleness
  errors, unrelated to this branch).
- Dev server renders the page at both `/zh-CN/.../storefront` and
  `/en/.../storefront` (user verified; I do not have browser access in
  this sandbox).
- Eight factory-image URLs verified via `curl` (all HTTP 200).

## Files touched on this branch
```
prelude/prelude-frontend-next/
  app/[locale]/workspace/[workspaceId]/storefront/page.tsx          (new)
  app/styles/animations.css                                         (+pc-enter)
  components/layout/sidebar/SidebarMenu.tsx                         (+storefront item)
  components/storefront/*.tsx, *.ts                                 (new module)
  global.d.ts                                                       (+storefront namespace)
  i18n/request.ts                                                   (+'storefront')
  messages/{en,zh-CN}/navigation.json                               (+items.storefront)
  messages/{en,zh-CN}/storefront.json                               (new)

prelude/prelude-user-settings/src/docs/
  STOREFRONT_FRONTEND_PORT.md                                       (this file)
```
