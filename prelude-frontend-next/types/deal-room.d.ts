/**
 * Deal Room Public Types
 * Tight contract for the public deal room renderer (app/deal/[token]/page.tsx).
 * Distinct from the loose internal Deal.quoteData used by the CRM listing.
 *
 * Note: Backend returns camelCase for deal room responses (no ApiClient conversion
 * needed — the public deal room endpoint builds camelCase keys directly).
 */

export interface PublicQuoteOption {
  label: string
  origin: string
  currency: string
  fobPrice: number
  landedPrice: number
  costBreakdown?: {
    oceanFreight?: number
    insurance?: number
    customsBrokerage?: number
    dutyRatePct?: number
    dutyAmount?: number
    dutyNotes?: string
    otherFees?: number
    otherFeesNotes?: string
  }
  incoterm?: string
  moq?: number
  leadTimeDays?: string
  notes?: string
}

export interface PublicQuoteData {
  productName: string
  hsCode: string
  quantity: number
  moq: number
  options: PublicQuoteOption[]
  validUntil?: string
}
