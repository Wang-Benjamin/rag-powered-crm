'use client'

import { create } from 'zustand'
import leadsApiService from '@/lib/api/leads'
import type { Entitlements } from '@/types/leads/bol'

const DEFAULT_ENTITLEMENTS: Entitlements = {
  buyers: { visibleLimit: 0 },
  competitors: { visibleLimit: 0 },
  showBuyerEmails: false,
  trial: { durationDays: 10 },
}

interface SubscriptionState {
  tier: string
  trialDaysRemaining?: number
  creditsUsedThisMonth: number
  monthlyCreditsRemaining: number
  entitlements: Entitlements
  isLoading: boolean
  hasFetched: boolean
  fetchSubscription: () => Promise<void>
  refreshSubscription: () => Promise<void>
}

export const useSubscription = create<SubscriptionState>()((set, get) => ({
  tier: 'trial',
  trialDaysRemaining: undefined,
  creditsUsedThisMonth: 0,
  monthlyCreditsRemaining: 0,
  entitlements: DEFAULT_ENTITLEMENTS,
  isLoading: true,
  hasFetched: false,

  fetchSubscription: async () => {
    if (get().hasFetched) return
    set({ isLoading: true })
    try {
      const data = await leadsApiService.getSubscription()
      set({
        tier: data.tier || 'trial',
        trialDaysRemaining: data.trialDaysRemaining,
        creditsUsedThisMonth: data.creditsUsedThisMonth || 0,
        monthlyCreditsRemaining: data.monthlyCreditsRemaining || 0,
        entitlements: data.entitlements || DEFAULT_ENTITLEMENTS,
        isLoading: false,
        hasFetched: true,
      })
    } catch (error) {
      console.error('Failed to fetch subscription:', error)
      set({ isLoading: false, hasFetched: true })
    }
  },

  refreshSubscription: async () => {
    set({ hasFetched: false })
    await get().fetchSubscription()
  },
}))
