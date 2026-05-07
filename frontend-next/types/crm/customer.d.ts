/**
 * Customer Type Definitions
 * Consolidated from multiple sources across the codebase
 * Based on backend model: prelude-crm/models/crm_models.py
 *
 * Note: Backend returns snake_case which is auto-converted to camelCase
 * by ApiClient. Only camelCase properties are needed here.
 */

export interface Customer {
  // Primary identifiers
  id: string | number
  clientId?: string | number

  // Company info
  company: string
  name?: string
  clientEmail?: string
  phone?: string
  location?: string
  website?: string

  // Contact info (via personnel records)
  clientName?: string

  // Status
  status?: string
  clientType?: string

  // Financial metrics (computed from deals.value_usd)
  totalDealValue?: number
  arr?: number
  totalRevenue?: number
  revenue?: string | number

  // Health and risk metrics
  healthScore?: number
  renewalProbability?: number
  expansionProbability?: number

  // Assignment
  assignedEmployeeName?: string
  assignedEmployeeId?: number | null
  assignedTo?: string

  // Activity tracking
  lastContact?: string
  lastActivity?: string

  // Progress and status
  currentStage?: string

  // Additional data
  recentActivities?: any[]
  notes?: string
  source?: string
  customFields?: Record<string, any>
  contacts?: any[]
  personnel?: any[]
  timeline?: any[]

  // Deal-related (for customer views)
  dealValue?: number
  dealCount?: number
  employeeCount?: number

  // Timestamps
  createdAt?: string
  updatedAt?: string

  // Legacy fields
  recentNotes?: string
  recentTimeline?: string

  // New CRM columns
  signal?: { level: string; label: string } | null
  stage?: string // new, contacted, replied, engaged, quoting

  // Trade intelligence (BoL data + deal aggregation)
  tradeIntel?: {
    topProducts?: string[]
    hsCodes?: string[]
    totalShipments?: number
    totalSuppliers?: number
    reorderWindow?: string
    chinaConcentration?: number
    growth12mPct?: number
    enrichedAt?: string
    dealProducts?: string[]
    dealHsCodes?: string[]
    fobMin?: number
    fobMax?: number
    moqMin?: number
    activeDeals?: number
  } | null
}
