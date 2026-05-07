'use client'

import React, { createContext, useState, useContext, useCallback, useEffect, useRef } from 'react'
import leadsApiService from '@/lib/api/leads'
import { useAuth } from '@/hooks/useAuth'
import { getCachedData, getCachedDataWithTimestamp, setCachedData, clearCachedData } from '@/utils/data-cache'
import type { Lead, LeadStats, LeadContextValue, LeadProviderProps } from '@/types/leads'

const LeadContext = createContext<LeadContextValue | undefined>(undefined)

const CACHE_EXPIRATION_TIME = 30 * 60 * 1000

export const useLeadContext = () => {
  const context = useContext(LeadContext)
  if (!context) {
    throw new Error('useLeadContext must be used within a LeadProvider')
  }
  return context
}

const DEFAULT_LEAD_STATS: LeadStats = {
  total: 0,
  qualified: 0,
  hot: 0,
  totalPersonnel: 0,
  companiesWithPersonnel: 0,
  avgPersonnelPerCompany: 0,
}

const MANUAL_SOURCES = ['csv_upload', 'manual_entry', 'importyeti']
const WORKFLOW_SOURCES = ['yellowpages', 'linkedin', 'web_scraping', 'api_import']

function hydrateLeadCache(userEmail: string | undefined) {
  if (typeof window === 'undefined' || !userEmail) {
    return { manual: [] as Lead[], workflow: [] as Lead[], stats: DEFAULT_LEAD_STATS, timestamp: null as number | null }
  }

  const preloaded = getCachedDataWithTimestamp<{ leads?: Lead[] }>(
    'leads_all',
    CACHE_EXPIRATION_TIME,
    userEmail
  )

  const leadsArray = Array.isArray(preloaded?.data?.leads) ? preloaded!.data.leads! : []

  const matchesSource = (lead: any, sources: string[]) =>
    sources.includes(lead.source || '') || sources.includes(lead.source?.toLowerCase() || '')

  const manual = leadsArray.filter((lead: any) => matchesSource(lead, MANUAL_SOURCES))
  const workflow = leadsArray.filter((lead: any) => matchesSource(lead, WORKFLOW_SOURCES))

  const stats =
    getCachedData<LeadStats>('leads_stats', CACHE_EXPIRATION_TIME, userEmail) ?? DEFAULT_LEAD_STATS

  return { manual, workflow, stats, timestamp: preloaded?.timestamp ?? null }
}

export function LeadProvider({ children }: LeadProviderProps) {
  const { user, isLoading: authLoading } = useAuth()
  const userEmail = user?.email || (user as any)?.userEmail

  // Synchronous cache hydration — matches CRMProvider. Child mount effects
  // (e.g. LeadManagement.loadLeads) fire before parent useEffects, so we must
  // compute hasInitialLoad at render time, not in an effect.
  const initial = hydrateLeadCache(userEmail)

  const [leads, setLeads] = useState<Lead[]>(initial.manual)
  const [workflowLeads, setWorkflowLeads] = useState<Lead[]>(initial.workflow)
  const [leadStats, setLeadStats] = useState<LeadStats>(initial.stats)

  const [lastFetchTime, setLastFetchTime] = useState<number | null>(initial.timestamp)
  const [isLoading, setIsLoading] = useState(false)
  const [leadsError, setLeadsError] = useState<string | null>(null)
  const [hasInitialLoad, setHasInitialLoad] = useState(
    initial.manual.length > 0 || initial.workflow.length > 0
  )
  const [isLoadedFromCache, setIsLoadedFromCache] = useState(
    initial.manual.length > 0 || initial.workflow.length > 0
  )
  const loadCancelledRef = useRef(false)

  // Refs for stable loadLeads callback
  const isLoadingRef = useRef(isLoading)
  const hasInitialLoadRef = useRef(hasInitialLoad)
  const lastFetchTimeRef = useRef(lastFetchTime)

  useEffect(() => {
    isLoadingRef.current = isLoading
    hasInitialLoadRef.current = hasInitialLoad
    lastFetchTimeRef.current = lastFetchTime
  }, [isLoading, hasInitialLoad, lastFetchTime])

  // Evict legacy subset-cache keys left over from the pre-consolidation code path.
  // Hydration itself is synchronous above; this effect only cleans storage quota.
  useEffect(() => {
    if (!userEmail) return
    clearCachedData('leads_manual', userEmail)
    clearCachedData('leads_workflow', userEmail)
  }, [userEmail])

  const isCacheValid = (lastFetch: number | null): boolean => {
    if (!lastFetch) return false
    return Date.now() - lastFetch < CACHE_EXPIRATION_TIME
  }

  const loadLeads = useCallback(
    async (force = false) => {
      if (!user) {
        return
      }

      if (!force && hasInitialLoadRef.current && isCacheValid(lastFetchTimeRef.current)) {
        return
      }

      if (isLoadingRef.current) return

      setIsLoading(true)
      try {
        let allLeadsResponse = { leads: [] as Lead[], totalPersonnel: 0 }

        try {
          const allLeads: Lead[] = []
          let page = 1
          let totalPersonnel = 0

          while (true) {
            const response = await leadsApiService.getLeadsWithPersonnel({ page, perPage: 1000 })
            const leads = response.leads || []

            if (leads.length === 0) break

            allLeads.push(...leads)
            totalPersonnel = response.totalPersonnel || totalPersonnel

            if (leads.length < 1000) break

            page++

            if (page > 10) break
          }

          allLeadsResponse = {
            leads: allLeads,
            totalPersonnel,
          }
        } catch {
          try {
            const allLeads: Lead[] = []
            let page = 1

            while (true) {
              const response = await leadsApiService.getLeads(page, 1000)
              const leads = response.data || []

              if (leads.length === 0) break

              allLeads.push(...leads)

              if (leads.length < 1000) break

              page++

              if (page > 10) break
            }

            allLeadsResponse = {
              leads: allLeads,
              totalPersonnel: 0,
            }
          } catch {
            allLeadsResponse = { leads: [], totalPersonnel: 0 }
          }
        }

        // If this load was cancelled (e.g. by Strict Mode remount), discard results
        if (loadCancelledRef.current) return

        const allLeads = allLeadsResponse.leads || []

        const manualSources = ['csv_upload', 'manual_entry', 'importyeti']
        const workflowSources = ['yellowpages', 'linkedin', 'web_scraping', 'api_import']

        const manualLeads = allLeads
          .filter(
            (lead: any) =>
              manualSources.includes(lead.source || '') ||
              manualSources.includes(lead.source?.toLowerCase() || '')
          )
          .map((lead: any) => ({
            ...lead,
            status: lead.status || 'new',
          }))

        const workflowLeadsFiltered = allLeads
          .filter(
            (lead: any) =>
              workflowSources.includes(lead.source || '') ||
              workflowSources.includes(lead.source?.toLowerCase() || '')
          )
          .map((lead: any) => ({
            ...lead,
            status: lead.status || 'new',
          }))

        setLeads(manualLeads)
        setWorkflowLeads(workflowLeadsFiltered)

        // Single canonical cache — manual/workflow subsets are derived from leads_all on read.
        // Writing three overlapping keys historically exceeded the localStorage quota.
        setCachedData('leads_all', allLeadsResponse, userEmail)

        const totalPersonnel = allLeadsResponse.totalPersonnel || 0
        const companiesWithPersonnel = workflowLeadsFiltered.filter(
          (l) => l.personnel?.length && l.personnel.length > 0
        ).length
        const avgPersonnelPerCompany =
          companiesWithPersonnel > 0 ? (totalPersonnel / companiesWithPersonnel).toFixed(1) : 0

        const allLeadsCount = allLeads.length
        const workflowQualified = workflowLeadsFiltered.filter(
          (l) => l.status === 'qualified'
        ).length
        const workflowHot = workflowLeadsFiltered.filter((l) => l.status === 'hot').length
        const manualQualified = manualLeads.filter((l) => l.status === 'qualified').length
        const manualHot = manualLeads.filter((l) => l.status === 'hot').length
        const allQualified = workflowQualified + manualQualified
        const allHot = workflowHot + manualHot

        const newLeadStats: LeadStats = {
          total: allLeadsCount,
          qualified: allQualified,
          hot: allHot,
          totalPersonnel,
          companiesWithPersonnel,
          avgPersonnelPerCompany,
        }

        setLeadStats(newLeadStats)
        setCachedData('leads_stats', newLeadStats, userEmail)

        setLastFetchTime(Date.now())
        setHasInitialLoad(true)
        setIsLoadedFromCache(false)
        setLeadsError(null)
      } catch (error: any) {
        setLeadsError(error.message || 'Failed to load leads')
        throw error
      } finally {
        setIsLoading(false)
      }
    },
    [user]
  )

  useEffect(() => {
    loadCancelledRef.current = false
    return () => {
      loadCancelledRef.current = true
    }
  }, [])

  const clearCache = useCallback(() => {
    setLeads([])
    setWorkflowLeads([])
    setLeadStats({
      total: 0,
      qualified: 0,
      hot: 0,
      totalPersonnel: 0,
      companiesWithPersonnel: 0,
      avgPersonnelPerCompany: 0,
    })
    setLastFetchTime(null)
    setHasInitialLoad(false)
  }, [])

  const updateLeadStatus = useCallback(async (leadId: string | number, newStatus: string) => {
    try {
      await leadsApiService.updateLeadStatus(String(leadId), newStatus)

      setLeads((prev) =>
        prev.map((lead) =>
          lead.id === leadId || lead.leadId === leadId ? { ...lead, status: newStatus } : lead
        )
      )
      setWorkflowLeads((prev) =>
        prev.map((lead) =>
          lead.id === leadId || lead.leadId === leadId ? { ...lead, status: newStatus } : lead
        )
      )

      return true
    } catch (error) {
      throw error
    }
  }, [])

  const removeLeadFromState = useCallback(
    (leadId: string | number) => {
      const leadIdStr = String(leadId)
      const matchesId = (lead: Lead) =>
        String(lead.id) === leadIdStr || String(lead.leadId) === leadIdStr

      let filteredManual: Lead[] = []
      let filteredWorkflow: Lead[] = []

      setLeads((prev) => {
        filteredManual = prev.filter((lead) => !matchesId(lead))
        return filteredManual
      })

      setWorkflowLeads((prev) => {
        filteredWorkflow = prev.filter((lead) => !matchesId(lead))
        return filteredWorkflow
      })

      setLeadStats((prev) => {
        const all = [...filteredManual, ...filteredWorkflow]
        const updated = {
          ...prev,
          total: all.length,
          qualified: all.filter((l) => l.status === 'qualified').length,
          hot: all.filter((l) => l.status === 'hot').length,
        }
        if (userEmail) setCachedData('leads_stats', updated, userEmail)
        return updated
      })

      // Update the canonical leads_all cache in place so the initializer stays warm
      // after a delete instead of forcing a full refetch on next mount.
      if (userEmail) {
        const cached = getCachedDataWithTimestamp<{ leads: Lead[]; totalPersonnel?: number }>(
          'leads_all',
          CACHE_EXPIRATION_TIME,
          userEmail
        )
        if (cached?.data) {
          const nextLeads = (cached.data.leads || []).filter((l) => !matchesId(l))
          setCachedData('leads_all', { ...cached.data, leads: nextLeads }, userEmail)
        }
      }

      return true
    },
    [userEmail]
  )

  const deleteLead = useCallback(
    async (leadId: string | number) => {
      await leadsApiService.deleteLead(String(leadId))
      removeLeadFromState(leadId)
      return true
    },
    [removeLeadFromState]
  )

  const updateLead = useCallback(async (updatedLead: Lead): Promise<boolean> => {
    const leadId = updatedLead.leadId || updatedLead.id
    if (!leadId) return false

    try {
      // Persist to backend first
      await leadsApiService.updateLead(String(leadId), updatedLead)

      // Then update local state
      setLeads((prev) =>
        prev.map((lead) =>
          lead.leadId === leadId || lead.id === leadId ? { ...lead, ...updatedLead } : lead
        )
      )

      setWorkflowLeads((prev) =>
        prev.map((lead) =>
          lead.leadId === leadId || lead.id === leadId ? { ...lead, ...updatedLead } : lead
        )
      )

      return true
    } catch (error) {
      throw error
    }
  }, [])

  const value: LeadContextValue = {
    leads,
    workflowLeads,
    leadStats,
    isLoading,
    leadsError,
    authLoading,
    hasInitialLoad,
    isLoadedFromCache,
    loadLeads,
    clearCache,
    updateLead,
    updateLeadStatus,
    deleteLead,
    removeLeadFromState,
    lastFetchTime,
    isCacheValid: isCacheValid(lastFetchTime),
  }

  return <LeadContext.Provider value={value}>{children}</LeadContext.Provider>
}
