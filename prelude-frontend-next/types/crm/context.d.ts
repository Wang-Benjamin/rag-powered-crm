/**
 * CRM Context and Store Type Definitions
 * Context and store state types for CRM management
 */

import type { Customer } from './customer'
import type { Employee } from './employee'
import type { Deal } from './deal'
import type { CustomerFilters as BaseCustomerFilters } from './filters'
import type { CachedSummary as BaseCachedSummary } from './activity'

/**
 * Analytics insights interface (store-specific)
 */
export interface AnalyticsInsights {
  insights?: string
  summary?: string
  [key: string]: any
}

/**
 * Extended cached summary with index signature for store flexibility
 */
export interface CachedSummary extends BaseCachedSummary {
  [key: string]: any
}

/**
 * Extended filter interface with index signature for store flexibility
 */
export interface CustomerFilters extends BaseCustomerFilters {
  [key: string]: any
}

/**
 * CRM store filters interface
 */
export interface Filters {
  search?: string
  status?: string
  churnRisk?: string
  [key: string]: any
}

/**
 * CRM Store State interface
 * Used by Zustand CRM store
 */
export interface CRMState {
  // Initialization state
  isInitialized: boolean
  initializationError: string | null
  hasInitialLoad: boolean
  isLoadedFromCache: boolean

  // Customer data
  customers: Customer[]
  customersLoading: boolean
  customersError: string | null
  customersLastFetch: number | null
  activeFilters: CustomerFilters

  // Employee data
  employees: Employee[]
  employeesLoading: boolean
  employeesError: string | null
  employeesLastFetch: number | null

  // Deals data
  deals: Deal[]
  dealsLoading: boolean
  dealsError: string | null
  dealsLastFetch: number | null

  // Analytics insights
  analyticsInsights: AnalyticsInsights | null
  insightsLoading: boolean
  insightsError: string | null
  insightsLastFetch: number | null

  // Cached summaries
  cachedSummaries: Record<string | number, CachedSummary>
  summariesLoading: boolean
  summariesError: string | null
  summariesLastFetch: number | null

  // Actions - Initialization
  setIsInitialized: (initialized: boolean) => void
  setInitializationError: (error: string | null) => void
  setHasInitialLoad: (hasLoad: boolean) => void
  setIsLoadedFromCache: (fromCache: boolean) => void

  // Actions - Customers
  setCustomers: (customers: Customer[] | ((prev: Customer[]) => Customer[])) => void
  setCustomersLoading: (loading: boolean) => void
  setCustomersError: (error: string | null) => void
  setCustomersLastFetch: (timestamp: number | null) => void
  setActiveFilters: (filters: CustomerFilters) => void
  addCustomer: (customer: Customer) => void
  updateCustomer: (updatedCustomer: Customer) => void
  deleteCustomerLocal: (customerId: string | number) => void

  // Actions - Employees
  setEmployees: (employees: Employee[]) => void
  setEmployeesLoading: (loading: boolean) => void
  setEmployeesError: (error: string | null) => void
  setEmployeesLastFetch: (timestamp: number | null) => void

  // Actions - Deals
  setDeals: (deals: Deal[] | ((prev: Deal[]) => Deal[])) => void
  setDealsLoading: (loading: boolean) => void
  setDealsError: (error: string | null) => void
  setDealsLastFetch: (timestamp: number | null) => void
  updateDeal: (updatedDeal: Deal) => void
  deleteDealLocal: (dealId: string | number) => void

  // Actions - Analytics
  setAnalyticsInsights: (insights: AnalyticsInsights | null) => void
  setInsightsLoading: (loading: boolean) => void
  setInsightsError: (error: string | null) => void
  setInsightsLastFetch: (timestamp: number | null) => void

  // Actions - Cached Summaries
  setCachedSummaries: (summaries: Record<string | number, CachedSummary>) => void
  setSummariesLoading: (loading: boolean) => void
  setSummariesError: (error: string | null) => void
  setSummariesLastFetch: (timestamp: number | null) => void

  // Helper methods
  clearCache: () => void
  isCacheValid: (lastFetch: number | null) => boolean
  clearFilters: () => void
}

/**
 * CRM Context Type - provided by CRMProvider
 * Used by useCRM hook consumers
 */
export interface CRMContextType {
  // Initialization state
  isInitialized: boolean
  initializationError: string | null
  hasInitialLoad: boolean
  isLoadedFromCache: boolean

  // Customer data
  customers: Customer[]
  customersLoading: boolean
  customersError: string | null
  setCustomers: React.Dispatch<React.SetStateAction<Customer[]>>
  activeFilters: Filters
  setActiveFilters: (filters: Filters) => void
  loadCustomers: (forceRefresh?: boolean, filters?: Filters) => Promise<void>

  // Employee data
  employees: Employee[]
  employeesLoading: boolean
  employeesError: string | null
  loadEmployees: (forceRefresh?: boolean) => Promise<void>

  // Deals data
  deals: Deal[]
  dealsLoading: boolean
  dealsError: string | null
  setDeals: React.Dispatch<React.SetStateAction<Deal[]>>
  loadDeals: (forceRefresh?: boolean) => Promise<void>
  deleteDeal: (dealId: string) => Promise<void>

  // Cached summaries
  cachedSummaries: Record<string, CachedSummary>
  summariesLoading: boolean
  summariesError: string | null
  loadCachedSummaries: (forceRefresh?: boolean) => Promise<void>

  // Analytics insights
  analyticsInsights: AnalyticsInsights | null
  insightsLoading: boolean
  insightsError: string | null
  loadAnalyticsInsights: (forceRefresh?: boolean) => Promise<void>
  refreshAnalytics: () => Promise<void>

  // Additional methods
  updateCustomer: (customerId: string, updates: Partial<Customer>) => Promise<void>
  updateDeal: (dealId: string, updates: Partial<Deal>) => Promise<void>
  refreshAllData: () => Promise<void>

  // Customer management methods
  refreshCustomers: () => Promise<void>
  addCustomer: (
    customerData: Partial<Customer>
  ) => Promise<{ success: boolean; customer?: Customer; error?: string }>
  deleteCustomer: (
    customerId: string
  ) => Promise<{ success: boolean; message?: string; error?: string }>
}
