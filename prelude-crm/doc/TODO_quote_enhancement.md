# Quote Page Enhancement Plan

## Current State vs Complete Quote

| Field | Trade Profile Has | Quote Shows | Gap |
|---|---|---|---|
| Company Logo | `company_profile.logoUrl` | Yes (header) | — |
| Company Name | `company_profile.companyNameEn/Zh` | Yes (header) | — |
| Company Address | `company_profile.location` | Yes (header) | — |
| Contact Info (email/phone) | No | No | **New field** |
| Product Name | `deal_name` | Yes | — |
| Product Spec/Description | `company_profile.productDescription` (generic) | No | **New per-deal field** |
| Product Images | `factory_details.photoUrls` (factory photos) | Factory photos only | **New product images** |
| FOB Price | `deals.fob_price` | Yes | — |
| Landed Price | `deals.landed_price` | Yes | — |
| Currency | `deals.fob_currency` | Yes | — |
| Incoterm (FOB/CIF/DDP) | No | Frontend interface exists but no data | **New field** |
| MOQ | `factory_details.moq` (global) | Not in quote | **New deal-level field** |
| Payment Terms (T/T, L/C) | No | No | **New field** |
| Lead Time | `factory_details.leadTime` (global) | Not in quote | **New deal-level field** |
| Quote Validity | Frontend has `validUntil` interface but no data | No | **New field** |
| Quantity | `deals.quantity` | Yes | — |
| Certifications | `factory_certifications` | Yes | — |
| HS Code | `deals.hs_code` | Yes | — |

## New Fields to Add

### A. Deal-level columns (`deals` table)

| Field | Column | Type | Description |
|---|---|---|---|
| MOQ | `moq` | `INTEGER` | Min order quantity for this deal |
| Incoterm | `incoterm` | `VARCHAR(10)` | FOB / CIF / DDP / EXW / CFR |
| Payment Terms | `payment_terms` | `VARCHAR(100)` | T/T 30%, L/C at sight, etc. |
| Lead Time | `lead_time_days` | `VARCHAR(50)` | "30-45" days |
| Quote Validity | `valid_until` | `DATE` | Quote expiry date |
| Product Description | `product_description` | `TEXT` | Product spec for this deal |
| Product Images | `product_images` | `JSONB` | `["url1", "url2"]` GCS URLs |

### B. Company-level new fields (`user_preferences.company_profile` JSONB)

| Field | Key | Description |
|---|---|---|
| Contact Email | `contactEmail` | Public-facing contact email |
| Contact Phone | `contactPhone` | Public-facing contact phone |

## Image Handling

**Product image upload flow:**
1. Reuse existing GCS upload logic (same as factory photos, logo)
2. Storage path: `product-images/{userEmail}/{dealId}/{filename}`
3. Upload via new CRM endpoint during deal room creation/edit
4. URLs stored in `deals.product_images` JSONB array
5. Displayed as image carousel in quote page header area

**New endpoints:**
```
POST /api/crm/deals/{deal_id}/upload-image   → Upload product image to GCS
DELETE /api/crm/deals/{deal_id}/images/{idx}  → Delete an image
```

## Data Source Priority

When deal-level field is empty, fall back to trade profile:

| Field | Priority 1 (Deal) | Priority 2 (Trade Profile) |
|---|---|---|
| MOQ | `deals.moq` | `factory_details.moq` |
| Lead Time | `deals.lead_time_days` | `factory_details.leadTime` |
| Product Description | `deals.product_description` | `company_profile.productDescription` |
| Contact Info | — | `company_profile.contactEmail/Phone` |

## Files to Modify

**Backend:**
1. `alembic_postgres/models.py` — Add new columns to Deals model
2. `deals_router.py` — Deal/CreateDealRequest/UpdateDealRequest add new fields, all SQL add new columns
3. `deal_room_service.py` — `get_deal_room()` return new fields
4. `public_deal_room_router.py` — Query new columns, build complete quoteData, pass contact info
5. CRM service new image upload endpoint (reuse GCS utils)

**Frontend:**
6. `types/crm/deal.d.ts` — Add new fields to Deal type
7. `app/deal/[token]/page.tsx` — Quote section render new fields (incoterm, MOQ, payment terms, lead time, validity, product description, product images, contact info)
8. `DealDetailModal.tsx` — Deal room creation/edit form add new field inputs
9. `EditableDealsTableV2.tsx` — Optional: add MOQ, Incoterm columns to dashboard table
10. `messages/en/crm.json` + `messages/zh-CN/crm.json` — i18n keys

**Database:**
11. All tenant databases ALTER TABLE to add new columns

## Implementation Checklist

- [ ] ALTER TABLE deals add `moq`, `incoterm`, `payment_terms`, `lead_time_days`, `valid_until`, `product_description`, `product_images` to all tenant databases
- [ ] Update `alembic_postgres/models.py` Deals model with new columns
- [ ] Update `deals_router.py` — Deal model, CreateDealRequest, UpdateDealRequest, _row_to_deal, all SQL SELECT, INSERT, field_mapping
- [ ] Update `deal_room_service.py` — get_deal_room query and return new fields
- [ ] Update `public_deal_room_router.py` — query new columns, build complete quoteData (with incoterm, moq, leadTimeDays, paymentTerms, validUntil), pass contact info to frontend
- [ ] CRM service new product image upload endpoint `POST /deals/{deal_id}/upload-image`
- [ ] Update `company_profile` JSONB add `contactEmail`, `contactPhone` (trade profile settings page and public_deal_room_router only)
- [ ] Update `types/crm/deal.d.ts` add new fields
- [ ] Update `DealDetailModal.tsx` — deal room creation form add new field inputs (incoterm dropdown, payment_terms, lead_time, valid_until, product_description, product image upload)
- [ ] Update `app/deal/[token]/page.tsx` — Quote page render new fields (incoterm badge, MOQ, lead time, payment terms, validity countdown, product image carousel, product description, contact info)
- [ ] Update i18n files `en/crm.json` and `zh-CN/crm.json`
- [ ] Optional: `EditableDealsTableV2.tsx` add MOQ, Incoterm columns
