# Storefront Quote Request — MVP Plan

## Goal

Buyer opens a seller's storefront link → clicks **Request Quote / 报价** on a product card → fills a short form → a deal appears in the seller's 交易室 (`/crm` deals page) with `room_status = quote_requested`, attributed to the buyer's email.

Mirrors the existing deal-room share-link pattern, but at the storefront level.

## Scope Cuts (explicit, MVP only)

- **No share token, no shared-DB changes.** URL is `/storefront/{seller_slug}` where `seller_slug == db_name`. Routing happens via the path param, not via a `prelude_user_analytics` lookup.
- **No new tables, no migrations.** Reuses existing `clients`, `personnel`, `deals`, `interaction_details`.
- **No revocation / no expiry.** Storefront link is permanent for now.
- **Product list is mock.** Public GET returns the same hardcoded catalog the seller's frontend already uses (`components/storefront/mockData.ts`). Real product persistence is a later concern.
- **English-primary buyer page.** No locale switcher on the public route.
- **No email notification to seller.** They'll see the new deal on next refresh of `/crm`.

## End-to-end demo after MVP

1. Seller logs in → opens `/workspace/[wid]/storefront`
2. Clicks **Share storefront** → URL `prelude.trade/storefront/{their_db_name}` copied to clipboard
3. Opens that URL in incognito (no auth) → sees seller header + product grid
4. Clicks 报价 on a product → modal opens (matches design screenshot)
5. Fills name / company / email / quantity / message → submits
6. Modal shows success state, closes after 2s
7. Seller switches to `/crm` → refreshes → new deal "Quote: 14" Carbon Steel Wok" with buyer email, status `quote_requested`

---

## Backend Changes

Total: **~80 lines, no migrations.**

### 1. New file: `prelude/prelude-crm/routers/public_storefront_router.py`

Two unauthenticated endpoints. Mirrors `public_deal_room_router.py` for rate-limit + connection patterns.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/crm/public/storefront/{seller_slug}` | Returns `{seller_name, products[]}` — opens connection to `seller_slug` DB, reads seller display name from `company_profile`, returns hardcoded product list. |
| POST | `/api/crm/public/storefront/{seller_slug}/quote-request` | Body: `{email, name?, company?, quantity?, message?, productName, productSku}`. In one tenant-DB transaction: find-or-create customer by email → insert deal → insert `interaction_details` row. |

**Quote-request transaction logic:**
```
BEGIN
  customer = SELECT * FROM clients WHERE primary_email = :email LIMIT 1
  IF NOT customer:
    INSERT INTO clients (name, primary_email, source) VALUES (
      :company OR domain_of(:email), :email, 'storefront_quote_request'
    ) RETURNING id
    INSERT INTO personnel (client_id, name, email, is_primary) VALUES (...)

  INSERT INTO deals (
    deal_name='Quote: ' || :productName,
    client_id=customer.id,
    product_name=:productName,
    quantity=:quantity,
    room_status='quote_requested',
    source='storefront'
  ) RETURNING id

  INSERT INTO interaction_details (
    deal_id, type='quote_request', content=JSON({email, name, company, quantity, message, productSku})
  )
COMMIT
```

**Rate limit:** 5/min per IP (copy from `public_deal_room_router.py`).

### 2. Wire router into `main.py`

Add `app.include_router(public_storefront_router.router)` next to the existing public deal-room router include.

### 3. No changes to:

- `models.py` (no schema changes)
- Alembic (no migration)
- `prelude_user_analytics` (untouched)
- Any other router or service file

---

## Frontend Changes

Total: **~250 lines new + ~30 lines edited.**

### 1. New: `components/storefront/RequestQuoteModal.tsx`

Match the design screenshot exactly:

- Heading "Request a Quote" — Instrument Serif, deep token
- 2-col row: **Your Name** | **Company**
- **Email \*** (required)
- **Quantity of Interest** (numeric, optional)
- **Message** (textarea, optional, placeholder "Questions about pricing, specifications, or samples...")
- Full-width submit button — `bg-accent`, `text-bone`, "Request Quote"
- Bone background, rule borders, focus ring in `--accent`
- Internal success state ("Quote request sent! The seller will review and reply via email.") — mirror `MessageModal` in `app/deal/[token]/page.tsx:285-463`
- Auto-close 2s after success

Props:
```ts
{
  open: boolean
  onOpenChange: (next: boolean) => void
  product: { name: string; sku: string }
  onSubmit: (payload: QuoteRequestPayload) => Promise<void>
}
```

### 2. New: `components/storefront/PublicStorefrontView.tsx`

Renders the buyer-facing page. Loads via `GET /api/storefront/{slug}` proxy, renders header + product grid using `ProductCard` in `mode="public"` (hides 编辑 + 上线/报价 swap; shows only 报价).

### 3. New page: `app/storefront/[slug]/page.tsx`

Public, unauthenticated. Wraps `PublicStorefrontView`. Mirror structural conventions from `app/deal/[token]/page.tsx`.

### 4. New proxy routes

- `app/api/storefront/[slug]/route.ts` — GET → forward to backend `GET /api/crm/public/storefront/{slug}`
- `app/api/storefront/[slug]/quote-request/route.ts` — POST → forward to backend `POST /api/crm/public/storefront/{slug}/quote-request`

No JWT pass-through (these are public).

### 5. New: `lib/api/storefront.ts`

```ts
export async function fetchPublicStorefront(slug: string) { ... }
export async function submitQuoteRequest(slug: string, payload: QuoteRequestPayload) { ... }
```

### 6. Edit: `components/storefront/ProductCard.tsx`

- Add prop `onRequestQuote?: (product: Product) => void`
- Add prop `mode?: 'seller' | 'public'` (default `'seller'`)
- Replace line 117 `onClick={(e) => e.preventDefault()}` with `onClick={() => onRequestQuote?.(product)}`
- In `mode='public'`, hide the 编辑 button and the seller-only 已上线/待上线 status badge stays visible

### 7. Edit: `components/storefront/StorefrontCatalog.tsx`

- Own modal open-state and selected-product state
- Pass `onRequestQuote` callback to each card
- Render single `<RequestQuoteModal>` instance

### 8. Edit: seller's storefront page (next to 查看店铺 button)

Add **Share storefront** button. On click:
- Compute URL client-side: `${window.location.origin}/storefront/${session.dbName}` (or pull `dbName` from JWT decoder already in use)
- Copy to clipboard, show toast "Link copied"
- No backend call needed (deterministic)

### 9. i18n

Add to `messages/en/storefront.json` + `messages/zh-CN/storefront.json`:

```json
"shareStorefront": "Share storefront" / "分享店铺",
"shareStorefrontCopied": "Link copied" / "已复制",
"requestQuoteModal": {
  "title": "Request a Quote" / "请求报价",
  "yourName": "YOUR NAME" / "您的姓名",
  "company": "COMPANY" / "公司",
  "email": "EMAIL" / "邮箱",
  "emailRequired": "Required" / "必填",
  "quantity": "QUANTITY OF INTEREST" / "意向数量",
  "quantityPlaceholder": "10,000",
  "message": "MESSAGE" / "留言",
  "messagePlaceholder": "Questions about pricing, specifications, or samples..." / "关于价格、规格、样品的问题...",
  "submit": "Request Quote" / "提交报价请求",
  "successTitle": "Quote request sent!" / "已发送",
  "successBody": "The seller will review your request and respond via email." / "卖家将通过邮件回复您。"
}
```

Public buyer page uses English keys regardless of `useLocale()`.

---

## Implementation Order

1. **Backend** — `public_storefront_router.py` + wire into `main.py`. Test with curl: POST a fake quote-request and verify the deal lands in a tenant DB.
2. **Frontend modal** — build `RequestQuoteModal` standalone, hook to existing 报价 button on seller's view (still using stub callback). Visually iterate against the screenshot.
3. **Public route** — build `app/storefront/[slug]/page.tsx` + proxy routes + `PublicStorefrontView`. Hardcode mock products. Wire modal submit to `submitQuoteRequest`.
4. **Share button** — add to seller's storefront page; verify the copied URL opens the public route.
5. **End-to-end** — open the link in incognito, submit a quote, refresh `/crm`, confirm deal exists.

---

## Verification Checklist

- [ ] Public GET `/api/storefront/{slug}` returns 200 with seller name + products for a real seller_slug
- [ ] Public GET returns 404 for an invalid seller_slug (DB doesn't exist)
- [ ] POST `/api/storefront/{slug}/quote-request` with new email → creates new customer + deal
- [ ] POST with existing customer email → reuses customer, creates new deal only
- [ ] Rate limit kicks in at 6th request from same IP within 60s
- [ ] Seller's `/crm` deals page shows the new deal with `status = quote_requested` and buyer email visible
- [ ] Modal validates email format client-side before submit
- [ ] Modal blocks double-submit (button disables during in-flight request)
- [ ] Modal success state shows for 2s then auto-closes
- [ ] `interaction_details` row visible in deal's activity panel with the buyer's message

---

## Out of Scope (Phase 2+)

- Storefront token + revocation (add `storefront_share_token` to `user_profiles` if private-share semantics are needed later)
- Real product persistence (replace mock with `storefront_products` table)
- Storefront customization (hero image, factory bio, custom message)
- Buyer-side analytics (view tracking, time-on-page)
- Email notification to seller on new quote request
- Bilingual buyer UI (currently English-primary only)
- Storefront publish/unpublish toggle
