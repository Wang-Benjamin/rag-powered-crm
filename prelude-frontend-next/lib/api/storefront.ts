import type { QuoteRequestPayload } from '@/components/storefront/RequestQuoteModal'

export interface PublicStorefrontHeroStats {
  yearFounded: string | null
  staff: string | null
  capacity: string | null
  exportShare: string | null
}

export interface PublicStorefrontKeyFacts {
  moq: string | null
  leadTime: string | null
  samplePolicy: string | null
  shipping: string | null
  payment: string | null
}

export interface PublicStorefrontCertification {
  certId: string
  certType: string | null
  certNumber: string | null
  issuingBody: string | null
  expiryDate: string | null
  notes: string | null
}

export interface PublicStorefrontContact {
  name: string | null
  title: string | null
  languages: string[]
}

export interface PublicStorefrontProductPriceRange {
  min?: number | null
  max?: number | null
  currency?: string | null
}

export interface PublicStorefrontProduct {
  productId: string
  name: string
  description: string | null
  specs: Record<string, string>
  imageUrl: string | null
  moq: number | null
  priceRange: PublicStorefrontProductPriceRange | null
  hsCode: string | null
  publishedAt: string | null
}

export interface PublicStorefront {
  sellerName: string
  sellerSlug: string
  sellerLogoUrl: string | null
  factoryPhotoUrl: string | null
  tagline: string | null
  heroStats: PublicStorefrontHeroStats
  keyFacts: PublicStorefrontKeyFacts
  certifications: PublicStorefrontCertification[]
  contact: PublicStorefrontContact
  products: PublicStorefrontProduct[]
}

export class StorefrontApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
    this.name = 'StorefrontApiError'
  }
}

export async function fetchPublicStorefront(slug: string): Promise<PublicStorefront> {
  const res = await fetch(`/api/storefront/${encodeURIComponent(slug)}`, {
    method: 'GET',
    headers: { Accept: 'application/json' },
    cache: 'no-store',
  })
  if (!res.ok) {
    throw new StorefrontApiError(res.status, `Failed to load storefront (${res.status})`)
  }
  // Backend returns the camelCase shape verbatim — the storefront proxy is a
  // hand-rolled passthrough that does not auto-convert keys.
  return (await res.json()) as PublicStorefront
}

export async function submitQuoteRequest(
  slug: string,
  payload: QuoteRequestPayload,
  sellerEmail?: string | null
): Promise<void> {
  const res = await fetch(`/api/storefront/${encodeURIComponent(slug)}/quote-request`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: payload.email,
      name: payload.name,
      company: payload.company,
      quantity: payload.quantity,
      message: payload.message,
      product_name: payload.productName,
      product_sku: payload.productSku,
      seller_email: sellerEmail || undefined,
    }),
  })
  if (res.status === 429) {
    throw new Error('rate_limited')
  }
  if (!res.ok) {
    throw new StorefrontApiError(res.status, `Quote request failed (${res.status})`)
  }
}
