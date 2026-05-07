'use client'

import { useState, useEffect, useCallback } from 'react'
import leadsApiService from '@/lib/api/leads'
import type {
  Competitor,
  CompetitorKpis,
  CompetitorAlert,
  CompetitorListResponse,
} from '@/types/leads/bol'

interface UseCompetitorsReturn {
  competitors: Competitor[]
  kpis: CompetitorKpis | null
  alerts: CompetitorAlert[]
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
  dismissAlert: (index: number) => void
}

export function useCompetitors(): UseCompetitorsReturn {
  const [competitors, setCompetitors] = useState<Competitor[]>([])
  const [kpis, setKpis] = useState<CompetitorKpis | null>(null)
  const [alerts, setAlerts] = useState<CompetitorAlert[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const data = (await leadsApiService.getCompetitors()) as CompetitorListResponse
      setCompetitors(data.competitors ?? [])
      setKpis(data.kpis ?? null)
      setAlerts(data.alerts ?? [])
    } catch (err: any) {
      const message = err?.response?.data?.detail || err?.message || 'Failed to load competitors'
      setError(message)
      setCompetitors([])
      setKpis(null)
      setAlerts([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetch()
  }, [fetch])

  const dismissAlert = useCallback((index: number) => {
    setAlerts((prev) => prev.filter((_, i) => i !== index))
  }, [])

  return { competitors, kpis, alerts, loading, error, refresh: fetch, dismissAlert }
}
