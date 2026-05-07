/**
 * CRM Filter Type Definitions
 * CRM-specific filter configuration
 */

export interface CRMFilters {
  search?: string
  status?: string
  churnRisk?: string
  assignedEmployee?: string
  location?: string
  minRevenue?: number
  maxRevenue?: number
  lastContactFrom?: string
  lastContactTo?: string
}

// Alias for backward compatibility with lib/api/crm.ts
export type CustomerFilters = CRMFilters
