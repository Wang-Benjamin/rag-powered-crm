'use client'

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
  ReactNode,
} from 'react'
import { useAuth } from '@/hooks/useAuth'
import {
  getCachedData,
  getCachedDataWithTimestamp,
  setCachedData,
  clearCachedData,
} from '@/utils/data-cache'
import { crmApiClient, ApiClientError } from '@/lib/api/client'
import type { Customer, Employee, Deal } from '@/types/crm'
import type { CachedSummary, AnalyticsInsights, Filters, CRMContextType } from '@/types/crm/context'

const CRMContext = createContext<CRMContextType | null>(null)

const CACHE_DURATION = 60 * 60 * 1000 // 1 hour

/**
 * Validate that cached deals have the expected camelCase shape.
 * Returns the data if valid, empty array + clears cache if stale.
 *
 * Stale cache happens when: code is updated (git pull) but the browser
 * still holds deals from the old API format. Since loadDeals() skips the
 * API call when cache TTL is valid, the broken objects stay until they
 * expire. Bumping CACHE_VERSION or detecting missing fields fixes this.
 */
function validateCachedDeals(data: any[], userEmail: string | null): Deal[] {
  if (!Array.isArray(data) || data.length === 0) return data as Deal[]
  const sample = data[0]
  const isStale =
    // snake_case keys from an old API format
    (sample.deal_id !== undefined && sample.dealId === undefined) ||
    // missing dealId entirely (object from a different source/version)
    sample.dealId == null
  if (isStale) {
    clearCachedData('crm_deals', userEmail)
    return []
  }
  return data as Deal[]
}

export const useCRM = () => {
  const context = useContext(CRMContext)
  if (!context) {
    throw new Error('useCRM must be used within a CRMProvider')
  }
  return context
}

export function CRMProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading: authLoading, user } = useAuth()

  // Get user email for cache isolation
  const userEmail = user?.email

  // Load initial data from localStorage cache immediately (user-specific)
  const initialCustomersCache = getCachedDataWithTimestamp(
    'crm_customers',
    CACHE_DURATION,
    userEmail
  )
  const initialEmployeesCache = getCachedDataWithTimestamp(
    'crm_employees',
    CACHE_DURATION,
    userEmail
  )
  const initialDealsCache = getCachedDataWithTimestamp('crm_deals', CACHE_DURATION, userEmail)

  const initialCachedCustomers = initialCustomersCache?.data || []
  const initialCachedEmployees = initialEmployeesCache?.data || []
  const initialCachedDeals = validateCachedDeals(initialDealsCache?.data || [], userEmail ?? null)

  // Initialization state
  const [isInitialized, setIsInitialized] = useState(false)
  const [initializationError, setInitializationError] = useState<string | null>(null)
  const [hasInitialLoad, setHasInitialLoad] = useState(initialCachedCustomers.length > 0)
  const [isLoadedFromCache, setIsLoadedFromCache] = useState(initialCachedCustomers.length > 0)

  // Customer data - initialize from cache
  const [customers, setCustomers] = useState<Customer[]>(initialCachedCustomers)
  const [customersLoading, setCustomersLoading] = useState(false)
  const [customersError, setCustomersError] = useState<string | null>(null)
  const [customersLastFetch, setCustomersLastFetch] = useState<number | null>(
    initialCustomersCache?.timestamp || null
  )
  const [activeFilters, setActiveFilters] = useState<Filters>({})

  // Use refs to access current values without adding to dependencies
  const customersRef = useRef(customers)
  const customersLastFetchRef = useRef(customersLastFetch)
  const customersLoadingRef = useRef(customersLoading)

  // Update refs when state changes
  useEffect(() => {
    customersRef.current = customers
    customersLastFetchRef.current = customersLastFetch
    customersLoadingRef.current = customersLoading
  }, [customers, customersLastFetch, customersLoading])

  // Employee data - initialize from cache
  const [employees, setEmployees] = useState<Employee[]>(initialCachedEmployees)
  const [employeesLoading, setEmployeesLoading] = useState(false)
  const [employeesError, setEmployeesError] = useState<string | null>(null)
  const [employeesLastFetch, setEmployeesLastFetch] = useState<number | null>(
    initialEmployeesCache?.timestamp || null
  )

  // Refs for stable loadEmployees callback
  const employeesRef = useRef(employees)
  const employeesLoadingRef = useRef(employeesLoading)
  const employeesLastFetchRef = useRef(employeesLastFetch)

  useEffect(() => {
    employeesRef.current = employees
    employeesLoadingRef.current = employeesLoading
    employeesLastFetchRef.current = employeesLastFetch
  }, [employees, employeesLoading, employeesLastFetch])

  // Analytics insights
  const [analyticsInsights, setAnalyticsInsights] = useState<AnalyticsInsights | null>(null)
  const [insightsLoading, setInsightsLoading] = useState(false)
  const [insightsError, setInsightsError] = useState<string | null>(null)
  const [insightsLastFetch, setInsightsLastFetch] = useState<number | null>(null)

  // Refs for stable loadAnalyticsInsights callback
  const analyticsInsightsRef = useRef(analyticsInsights)
  const insightsLoadingRef = useRef(insightsLoading)
  const insightsLastFetchRef = useRef(insightsLastFetch)

  useEffect(() => {
    analyticsInsightsRef.current = analyticsInsights
    insightsLoadingRef.current = insightsLoading
    insightsLastFetchRef.current = insightsLastFetch
  }, [analyticsInsights, insightsLoading, insightsLastFetch])

  // Deals data - initialize from cache
  const [deals, setDeals] = useState<Deal[]>(initialCachedDeals)
  const [dealsLoading, setDealsLoading] = useState(false)
  const [dealsError, setDealsError] = useState<string | null>(null)
  const [dealsLastFetch, setDealsLastFetch] = useState<number | null>(
    initialDealsCache?.timestamp || null
  )

  // Use refs to access current values without adding to dependencies
  const dealsRef = useRef(deals)
  const dealsLastFetchRef = useRef(dealsLastFetch)
  const dealsLoadingRef = useRef(dealsLoading)

  useEffect(() => {
    dealsRef.current = deals
    dealsLastFetchRef.current = dealsLastFetch
    dealsLoadingRef.current = dealsLoading
  }, [deals, dealsLastFetch, dealsLoading])

  // Cached summaries data
  const [cachedSummaries, setCachedSummaries] = useState<Record<string, CachedSummary>>({})
  const [summariesLoading, setSummariesLoading] = useState(false)
  const [summariesError, setSummariesError] = useState<string | null>(null)
  const [summariesLastFetch, setSummariesLastFetch] = useState<number | null>(null)

  // Refs for stable loadCachedSummaries callback
  const cachedSummariesRef = useRef(cachedSummaries)
  const summariesLoadingRef = useRef(summariesLoading)
  const summariesLastFetchRef = useRef(summariesLastFetch)

  useEffect(() => {
    cachedSummariesRef.current = cachedSummaries
    summariesLoadingRef.current = summariesLoading
    summariesLastFetchRef.current = summariesLastFetch
  }, [cachedSummaries, summariesLoading, summariesLastFetch])

  // Check if cache is valid
  const isCacheValid = (lastFetch: number | null): boolean => {
    if (!lastFetch) return false
    return Date.now() - lastFetch < CACHE_DURATION
  }

  // Load cached summaries data
  const loadCachedSummaries = useCallback(
    async (forceRefresh = false) => {
      if (summariesLoadingRef.current && !forceRefresh) return

      if (
        !forceRefresh &&
        Object.keys(cachedSummariesRef.current).length > 0 &&
        isCacheValid(summariesLastFetchRef.current)
      ) {
        return
      }

      setSummariesLoading(true)
      setSummariesError(null)

      try {
        if (!userEmail) {
          throw new Error('User email not available')
        }

        const summariesArray = await crmApiClient.get<CachedSummary[]>('/cached-summaries/batch')

        // Convert array to customerId -> summary mapping
        const summariesMap: Record<string, CachedSummary> = {}
        summariesArray.forEach((summary: CachedSummary) => {
          summariesMap[summary.customerId] = summary
        })

        setCachedSummaries(summariesMap)
        setCachedData('crm_summaries', summariesMap, userEmail)
        setSummariesLastFetch(Date.now())
      } catch (error) {
        const errorMessage =
          error instanceof ApiClientError ? error.message : (error as Error).message
        setSummariesError(errorMessage)
      } finally {
        setSummariesLoading(false)
      }
    },
    [userEmail]
  )

  // Load customers data
  const loadCustomers = useCallback(
    async (forceRefresh = false, filters: Filters = {}) => {
      if (customersLoadingRef.current && !forceRefresh) {
        return
      }

      const currentCustomers = customersRef.current
      const currentLastFetch = customersLastFetchRef.current

      if (
        !forceRefresh &&
        !Object.keys(filters).length &&
        currentCustomers.length > 0 &&
        isCacheValid(currentLastFetch)
      ) {
        return
      }

      setCustomersLoading(true)
      setCustomersError(null)

      try {
        if (!userEmail) {
          throw new Error('User email not available')
        }

        const params: Record<string, string> = {}

        if (filters.search) params.search = filters.search
        if (filters.status) params.status = filters.status
        if (filters.industry) params.industry = filters.industry
        if (filters.churnRisk) params.churnRisk = filters.churnRisk

        const data = await crmApiClient.get<Customer[]>(
          '/customers',
          Object.keys(params).length > 0 ? params : undefined
        )

        setCustomers(data)
        setCachedData('crm_customers', data, userEmail)
        setCustomersLastFetch(Date.now())
        setHasInitialLoad(true)
        setIsLoadedFromCache(false)

        // Load summaries separately
        loadCachedSummaries(forceRefresh).catch(() => {})
      } catch (error) {
        const errorMessage =
          error instanceof ApiClientError ? error.message : (error as Error).message
        setCustomersError(errorMessage)
        setCustomers([])
        setHasInitialLoad(true)
      } finally {
        setCustomersLoading(false)
      }
    },
    [userEmail, loadCachedSummaries]
  )

  // Load employees data
  const loadEmployees = useCallback(
    async (forceRefresh = false) => {
      if (employeesLoadingRef.current && !forceRefresh) return

      if (!forceRefresh && employeesRef.current.length > 0 && isCacheValid(employeesLastFetchRef.current)) {
        return
      }

      setEmployeesLoading(true)
      setEmployeesError(null)

      try {
        if (!userEmail) {
          throw new Error('User email not available')
        }

        const data = await crmApiClient.get<Employee[]>('/employees')

        setEmployees(data)
        setCachedData('crm_employees', data, userEmail)
        setEmployeesLastFetch(Date.now())
      } catch (error) {
        const errorMessage =
          error instanceof ApiClientError ? error.message : (error as Error).message
        setEmployeesError(errorMessage)
      } finally {
        setEmployeesLoading(false)
      }
    },
    [userEmail]
  )

  // Load deals data
  const loadDeals = useCallback(
    async (forceRefresh = false) => {
      if (dealsLoadingRef.current && !forceRefresh) return

      if (!forceRefresh && dealsRef.current.length > 0 && isCacheValid(dealsLastFetchRef.current)) {
        return
      }

      setDealsLoading(true)
      setDealsError(null)

      try {
        if (!userEmail) {
          throw new Error('User email not available')
        }

        const data = await crmApiClient.get<Deal[]>('/deals')

        setDeals(data)
        setCachedData('crm_deals', data, userEmail)
        setDealsLastFetch(Date.now())
      } catch (error) {
        const errorMessage =
          error instanceof ApiClientError ? error.message : (error as Error).message
        setDealsError(errorMessage)
      } finally {
        setDealsLoading(false)
      }
    },
    [userEmail]
  )

  // Load analytics insights
  const loadAnalyticsInsights = useCallback(
    async (forceRefresh = false) => {
      if (insightsLoadingRef.current && !forceRefresh) return

      if (!forceRefresh && analyticsInsightsRef.current && isCacheValid(insightsLastFetchRef.current)) {
        return
      }

      setInsightsLoading(true)
      setInsightsError(null)

      try {
        if (!userEmail) {
          throw new Error('User email not available')
        }

        const data = await crmApiClient.get<AnalyticsInsights>('/analytics/insights')

        setAnalyticsInsights(data)
        setInsightsLastFetch(Date.now())
      } catch (error) {
        const errorMessage =
          error instanceof ApiClientError ? error.message : (error as Error).message
        setInsightsError(errorMessage)
      } finally {
        setInsightsLoading(false)
      }
    },
    [userEmail]
  )

  // Refresh analytics data
  const refreshAnalytics = useCallback(() => loadAnalyticsInsights(true), [loadAnalyticsInsights])

  // Update customer data
  const updateCustomer = useCallback(
    async (customerId: string, updates: Partial<Customer>) => {
      try {
        if (!userEmail) {
          throw new Error('User email not available')
        }

        const updatedCustomer = await crmApiClient.patch<Customer>(
          `/customers/${customerId}`,
          updates
        )

        setCustomers((prev) => prev.map((c) => (c.id === customerId ? updatedCustomer : c)))
      } catch (error) {
        throw error
      }
    },
    [userEmail]
  )

  // Add new customer
  const addCustomer = useCallback(
    async (customerData: Partial<Customer>) => {
      try {
        if (!userEmail) {
          throw new Error('User email not available')
        }

        const newCustomer = await crmApiClient.post<Customer>('/customers', customerData)

        setCustomers((prev) => {
          const updated = [newCustomer, ...prev]
          setCachedData('crm_customers', updated, userEmail)
          return updated
        })
        return { success: true, customer: newCustomer }
      } catch (error) {
        const errorMessage =
          error instanceof ApiClientError ? error.message : (error as Error).message
        return { success: false, error: errorMessage }
      }
    },
    [userEmail]
  )

  // Delete customer
  const deleteCustomer = useCallback(
    async (customerId: string) => {
      try {
        if (!userEmail) {
          throw new Error('User email not available')
        }

        const result = await crmApiClient.delete<{ message: string }>(`/customers/${customerId}`)

        setCustomers((prev) => {
          const updated = prev.filter((customer) => String(customer.id) !== String(customerId))
          setCachedData('crm_customers', updated, userEmail)
          return updated
        })

        // Remove deals belonging to the deleted customer (DB cascade deletes them)
        setDeals((prev) => {
          const updated = prev.filter((deal) => String(deal.clientId) !== String(customerId))
          setCachedData('crm_deals', updated, userEmail)
          return updated
        })

        return { success: true, message: result.message }
      } catch (error) {
        const errorMessage =
          error instanceof ApiClientError ? error.message : (error as Error).message
        return { success: false, error: errorMessage }
      }
    },
    [userEmail]
  )

  // Refresh customers data
  const refreshCustomers = useCallback(
    () => loadCustomers(true, activeFilters),
    [loadCustomers, activeFilters]
  )

  // Update deal data
  const updateDeal = useCallback(
    async (dealId: string, updates: Partial<Deal>) => {
      try {
        if (!userEmail) {
          throw new Error('User email not available')
        }

        const updatedDeal = await crmApiClient.put<Deal>(`/deals/${dealId}`, updates)

        setDeals((prev) => prev.map((d) => (d.dealId === dealId ? updatedDeal : d)))
      } catch (error) {
        throw error
      }
    },
    [userEmail]
  )

  // Delete deal data
  const deleteDeal = useCallback(
    async (dealId: string) => {
      try {
        if (!userEmail) {
          throw new Error('User email not available')
        }

        await crmApiClient.delete(`/deals/${dealId}`)

        setDeals((prev) => {
          const updated = prev.filter((d) => String(d.dealId) !== dealId)
          setCachedData('crm_deals', updated, userEmail)
          return updated
        })
      } catch (error) {
        throw error
      }
    },
    [userEmail]
  )

  // Refresh all data
  const refreshAllData = useCallback(async () => {
    await Promise.all([
      loadCustomers(true),
      loadEmployees(true),
      loadDeals(true),
      loadAnalyticsInsights(true),
      loadCachedSummaries(true),
    ])
  }, [loadCustomers, loadEmployees, loadDeals, loadAnalyticsInsights, loadCachedSummaries])

  const value: CRMContextType = {
    // Initialization state
    isInitialized,
    initializationError,
    hasInitialLoad,
    isLoadedFromCache,

    // Customer data
    customers,
    customersLoading,
    customersError,
    setCustomers,
    activeFilters,
    setActiveFilters,
    loadCustomers,

    // Employee data
    employees,
    employeesLoading,
    employeesError,
    loadEmployees,

    // Deals data
    deals,
    dealsLoading,
    dealsError,
    setDeals,
    loadDeals,
    deleteDeal,

    // Cached summaries
    cachedSummaries,
    summariesLoading,
    summariesError,
    loadCachedSummaries,

    // Analytics insights
    analyticsInsights,
    insightsLoading,
    insightsError,
    loadAnalyticsInsights,
    refreshAnalytics,

    // Additional methods
    updateCustomer,
    updateDeal,
    refreshAllData,

    // Customer management methods
    refreshCustomers,
    addCustomer,
    deleteCustomer,
  }

  return <CRMContext.Provider value={value}>{children}</CRMContext.Provider>
}
