'use client'

import { useSubscription } from '@/stores/subscriptionStore'

export interface TrialStatus {
  isExpired: boolean
  tier: string
}

export function useTrialStatus(): TrialStatus {
  const { tier } = useSubscription()
  return {
    isExpired: tier === 'expired',
    tier,
  }
}
