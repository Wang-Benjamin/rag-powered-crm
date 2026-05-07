/**
 * Lead Context and Store Type Definitions
 * Context and store state types for Lead management
 */

import type { Lead, LeadStats } from './index'

/**
 * Lead Store State interface
 * Used by Zustand lead store
 */
export interface LeadState {
  // Lead data states
  leads: Lead[]
  workflowLeads: Lead[]
  leadStats: LeadStats

  // Cache and loading states
  lastFetchTime: number | null
  isLoading: boolean
  hasInitialLoad: boolean
  isLoadedFromCache: boolean

  // Actions - Data Management
  setLeads: (leads: Lead[]) => void
  setWorkflowLeads: (leads: Lead[]) => void
  setLeadStats: (stats: LeadStats) => void
  addLead: (lead: Lead, isWorkflow?: boolean) => void
  updateLead: (updatedLead: Lead) => void
  deleteLead: (leadId: string | number) => void
  removeLeadFromState: (leadId: string | number) => void

  // Actions - Status Management
  updateLeadStatus: (leadId: string | number, newStatus: Lead['status']) => void

  // Actions - Loading States
  setLastFetchTime: (time: number | null) => void
  setIsLoading: (loading: boolean) => void
  setHasInitialLoad: (hasLoad: boolean) => void
  setIsLoadedFromCache: (fromCache: boolean) => void

  // Helper methods
  clearCache: () => void
  isCacheValid: () => boolean
  getCachedData: (key: string, userEmail?: string) => any
  setCachedData: (key: string, data: any, userEmail?: string) => void
  getAllLeads: () => Lead[]
  getLeadById: (leadId: string | number) => Lead | undefined
  recalculateStats: () => void
}

/**
 * Lead Context Value - provided by LeadProvider
 * Used by useLeadContext hook consumers
 */
export interface LeadContextValue {
  leads: Lead[]
  workflowLeads: Lead[]
  leadStats: LeadStats
  isLoading: boolean
  leadsError: string | null
  authLoading: boolean
  hasInitialLoad: boolean
  isLoadedFromCache: boolean
  loadLeads: (force?: boolean) => Promise<void>
  clearCache: () => void
  updateLead: (updatedLead: Lead) => Promise<boolean>
  updateLeadStatus: (leadId: string | number, newStatus: string) => Promise<boolean>
  deleteLead: (leadId: string | number) => Promise<boolean>
  removeLeadFromState: (leadId: string | number) => boolean
  lastFetchTime: number | null
  isCacheValid: boolean
}

/**
 * Lead Provider Props
 */
export interface LeadProviderProps {
  children: React.ReactNode
}
