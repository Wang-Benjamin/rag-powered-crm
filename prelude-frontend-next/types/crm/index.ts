/**
 * CRM Type Definitions - Barrel Export
 * Consolidated TypeScript type definitions for the CRM domain
 */

export * from './customer'
export * from './deal'
export * from './employee'
export * from './activity'
export * from './filters'
export * from './metrics'
export * from './feedback'
export * from './meeting'

// Export context types explicitly to avoid naming conflicts
export type {
  AnalyticsInsights,
  CachedSummary,
  CustomerFilters,
  Filters,
  CRMState,
  CRMContextType,
} from './context'
