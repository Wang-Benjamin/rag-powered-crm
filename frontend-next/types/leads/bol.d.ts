/** Types for the BoL (Bill of Lading) Find Buyers feature. */

// Time series entry (monthly shipment data from ImportYeti)
export interface TimeSeriesEntry {
  shipments: number
  weight: number
  teu: number
  chinaShipments?: number
  chinaWeight?: number
  chinaTeu?: number
}

// Recent BoL record from deep enrichment
export interface RecentBol {
  dateFormatted: string
  productDescription: string
  hsCode: string
  quantity: string
  quantityUnit: string
  weightInKg: string
  teu?: string
  shipperName: string
  consigneeName: string
  country?: string
  countryCode?: string
}

// Scoring signal breakdown
export interface ScoringSignal {
  points: number
  max: number
}

export interface ScoringSignals {
  reorderWindow: ScoringSignal
  supplierDiversification: ScoringSignal
  competitiveDisplacement: ScoringSignal
  volumeFit: ScoringSignal
  recencyActivity: ScoringSignal
  hsRelevance: ScoringSignal
  shipmentScale: ScoringSignal
  switchingVelocity: ScoringSignal
  buyerGrowth: ScoringSignal
  supplyChainVulnerability: ScoringSignal
  orderConsistency: ScoringSignal
}

// Deep enrichment context stored on leads table for buyer detail view
export interface BolDetailContext {
  timeSeries: Record<string, TimeSeriesEntry>
  recentBols: RecentBol[]
  chinaConcentration: number | null
  growth12mPct: number | null
  aiActionBrief: string | null
  aiInsightCondensed: string | null
  scoringSignals: ScoringSignals
}

export interface SupplierEntry {
  supplierName: string
  country: string
  shipments: number
  shipmentsPercentsCompany: number
  shipments12m: number
  shipments1224m: number
  weightKg: number
  teu: number
  mostRecentShipment: string
  isNewSupplier: boolean
}

export interface BolCompany {
  id: string
  importyetiSlug: string
  companyName: string

  // List-level data (from PowerQuery — 0.1 credit/result)
  companyTotalShipments?: number
  totalSuppliers?: number
  address?: string
  state?: string
  city?: string
  country?: string
  website?: string
  contactEmails?: string[]
  contactPhones?: string[]
  shippingPorts?: string[]
  portsOfEntry?: string[]
  productDescriptions?: string[]
  hsCodes?: string[]

  // Per-query data (from bol_search_results)
  matchingShipments?: number
  relevanceScore?: number
  weightKg?: number
  teu?: number
  specialization?: number

  // Scoring
  quickScore?: number // 0-100 preliminary from bol_search_results, soft-capped at 80 by the scoring model
  enrichedScore?: number // 0-100 from bol_companies (after deep enrichment, all 5 signals)

  // FREE enrichment data (from /company/search — 0 credits)
  mostRecentShipment?: string
  topSuppliers?: string[]

  // Deep enrichment data (from /company/{company} — 1 credit)
  phoneNumber?: string
  alsoKnownNames?: string[]
  timeSeries?: Record<string, any>
  supplierBreakdown?: SupplierEntry[]
  recentBols?: Record<string, any>
  otherContacts?: Record<string, any>
  aiActionBrief?: string

  // Status
  enrichmentStatus: 'pending' | 'free_enriched' | 'detail_enriched'

  // Trial gating
  isBlurred?: boolean
}

export interface BolSearchRequest {
  hsCodes: string[]
  maxResults?: number
  supplierCountry?: string
}

export interface FeatureEntitlement {
  visibleLimit?: number
}

export interface Entitlements {
  buyers: FeatureEntitlement
  competitors: FeatureEntitlement
  showBuyerEmails: boolean
  trial: { durationDays: number }
}

export interface SubscriptionInfo {
  tier: 'trial' | 'paid' | 'expired'
  onboardingStatus: 'pending' | 'enriching' | 'competitors' | 'complete' | 'failed'
  trialDaysRemaining?: number
  creditsUsedThisMonth: number
  monthlyCreditsRemaining: number
  entitlements?: Entitlements
  onboarding?: {
    phase?: string | null
    buyersTarget?: number | null
    buyersReady?: number | null
    competitorsTarget?: number | null
    competitorsReady?: number | null
    warningCode?: string | null
    warningMeta?: Record<string, any> | null
    lastTransitionAt?: string | null
    lastErrorCode?: string | null
    lastErrorMeta?: Record<string, any> | null
    attemptCount?: number | null
  }
}

export interface BolSearchResponse {
  companies: BolCompany[]
  source: 'internal_db' | 'importyeti_api' | 'warming_cache'
  apiCreditsUsed: number
  totalCached: number
  subscription?: SubscriptionInfo
  creditCapMessage?: string
  inProgress?: boolean
}

export interface HsCode {
  code: string
  description: string
  confidence?: number
  selected?: boolean
  confirmed?: boolean
}

export interface BolFilters {
  state: string
  minScore: number
  sortBy: 'score' | 'shipments' | 'suppliers' | 'name'
}

/** Types for the BoL Competitor Analysis feature. */

export type ThreatLevel = 'HIGH' | 'GROWING' | 'DECLINING' | 'MODERATE' | 'LOW'

/** A customer/buyer entry from the competitor's companies_table (deep enrich). */
export interface CompetitorCustomer {
  companyName: string
  companyAddress?: string
  companyAddressCountry?: string
  country?: string
  countryCode?: string
  key?: string
  totalShipmentsSupplier: number
  shipmentsPercentsSupplier: number
  totalShipmentsCompany: number
  shipmentsPercentsCompany: number
  shipments12m: number
  shipments1224m: number
  topSuppliers?: Array<{ companyName: string; shipments12m: number; totalShipments: number }>
  totalWeight?: number
  totalTeus?: number
  mostRecentShipment?: string
  firstShipment?: string
  isNewCompany?: boolean
  businessLength?: string
  productDescriptions?: string[]
  hsCodeChapters?: Array<{
    chapter: string
    name: string
    shipments: number
    shipmentsPerc: number
  }>
  internal?: boolean
}

export interface Competitor {
  id: string
  supplierSlug: string
  supplierName: string
  country: string
  countryCode: string
  address: string
  city?: string
  supplierNameCn?: string
  hsCodes: string[]
  totalShipments: number
  matchingShipments: number
  totalCustomers: number
  specialization: number
  weightKg: number
  customerCompanies: string[]
  productDescriptions: string[]
  overlapCount: number
  overlapBuyerSlugs: string[]
  threatLevel: ThreatLevel
  threatScore: number
  trendYoy: number | null
  isTracked: boolean
  timeSeries?: Record<string, any> | any[]
  notes?: string
  firstSeenAt?: string
  lastUpdatedAt?: string
  alsoKnownNames?: string[]
  companiesTable?: CompetitorCustomer[]
  carriersPerCountry?: Record<string, string[]>
  customerConcentration?: {
    topBuyerName: string
    topBuyerShare: number
    top3Share: number
    totalActiveBuyers: number
  } | null
  recentBols?: Array<{
    billOfLading: string
    consigneeName: string
    dateFormatted: string
    hsCode: string
    quantity: string
    quantityUnit: string
    weightInKg: string
    productDescription?: string
    shippingRoute?: string
    supplierAddressLoc?: string
    country?: string
    countryCode?: string
    lcl?: boolean
    containersCount?: number
  }>
  carriers?: string[]
  isBlurred?: boolean
}

export interface CompetitorAlert {
  type: 'volume_drop' | 'new_entrant' | 'buyer_lost'
  message?: string
  supplierSlug: string
  supplierName: string
  trendYoy?: number
}

export interface CompetitorKpis {
  totalCompetitors: number
  topVolumeName: string
  topVolumeShipments: number
  sharedBuyersCount: number
  vulnerableCount: number
}

export interface CompetitorListResponse {
  competitors: Competitor[]
  kpis: CompetitorKpis
  alerts: CompetitorAlert[]
  totalCompetitors?: number
  visibleLimit?: number
}

export interface CompetitorSharedBuyer {
  buyerSlug: string
  buyerName: string
  buyerScore?: number
}
