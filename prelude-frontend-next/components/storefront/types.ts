import type { PriceRange } from '@/components/onboarding/customize-ai/ingestion/types'

export type StorefrontView = 'draft' | 'pending' | 'live'

export type ProductStatus = 'pending' | 'live'

/**
 * Seller-side product record. The buyer-facing storefront reads from
 * `lib/api/storefront.PublicStorefrontProduct` instead — that shape is
 * the API contract for the public page. The `nameEn`/`nameZh`/`kindLabel`
 * fields below are vestigial fallbacks from the pre-real-data buyer mock
 * and remain optional for backwards compatibility with seller-side
 * fallback chains (`p.name ?? p.nameEn ?? ''`).
 */
export interface Product {
  // Catalog lean fields
  productId?: string
  name?: string
  description?: string | null
  specs?: Record<string, string>
  imageUrl?: string | null
  moq?: number | null
  priceRange?: PriceRange | null
  hsCode?: string | null

  // Vestigial fallback fields used by seller-side catalog rendering.
  id?: string
  kindLabel?: string
  nameEn?: string
  nameZh?: string
  categoryEn?: string
  categoryZh?: string
  specEn?: string
  specZh?: string

  // Shared
  status: ProductStatus
  publishedAt?: string | null
}

export type { PriceRange }
