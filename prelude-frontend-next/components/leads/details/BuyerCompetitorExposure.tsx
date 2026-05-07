'use client'

import React, { useEffect, useState } from 'react'
import { useTranslations } from 'next-intl'
import { Shield, ArrowUp, ArrowDown } from 'lucide-react'
import { InlineLoader } from '@/components/ui/inline-loader'
import leadsApiService from '@/lib/api/leads'
import type { ThreatLevel } from '@/types/leads/bol'
import { signalTextClass, trendTier } from '@/lib/design/signal'

interface CompetitorExposureItem {
  supplierName: string
  supplierSlug: string
  threatLevel: string
  threatScore: number
  trendYoy: number | null
  matchingShipments: number
  isTracked: boolean
  buyerTeu: number
  buyerSharePct: number
}

interface BuyerCompetitorExposureProps {
  leadId: string
}

export default function BuyerCompetitorExposure({ leadId }: BuyerCompetitorExposureProps) {
  const t = useTranslations('leads.buyerDetail')
  const [competitors, setCompetitors] = useState<CompetitorExposureItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function fetch() {
      setLoading(true)
      setError(false)
      try {
        const data = await leadsApiService.getLeadCompetitors(leadId)
        if (!cancelled) setCompetitors(Array.isArray(data) ? data : [])
      } catch {
        if (!cancelled) setError(true)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    fetch()
    return () => {
      cancelled = true
    }
  }, [leadId])

  // Loading
  if (loading) {
    return (
      <div className="flex items-center justify-center py-6">
        <InlineLoader label={t('loadingCompetitors')} className="text-mute" />
      </div>
    )
  }

  // Error
  if (error) {
    return <p className="py-4 text-center text-[11px] text-mute">{t('competitorLoadError')}</p>
  }

  // Empty — good news
  if (competitors.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-6 text-center">
        <Shield className="mb-1.5 h-5 w-5 text-mute" />
        <p className="text-xs font-medium text-ink">
          {t('noCompetitorOverlap')}
        </p>
        <p className="mt-0.5 text-[11px] text-mute">
          {t('noCompetitorOverlapDesc')}
        </p>
      </div>
    )
  }

  // Risk chip label + tone mapping (design's chip-risk-high/mid/low).
  const riskForThreat = (threat: ThreatLevel) => {
    if (threat === 'HIGH' || threat === 'GROWING') {
      return { label: t('overlapRiskHigh'), cls: 'bg-threat/15 text-threat' }
    }
    if (threat === 'MODERATE' || threat === 'DECLINING') {
      return { label: t('overlapRiskMid'), cls: 'bg-gold-lo text-gold' }
    }
    return { label: t('overlapRiskLow'), cls: 'bg-cream text-mute' }
  }

  // Data — title + subtitle + horizontal overlap-row grid per design.
  return (
    <section>
      <header className="mb-3">
        <h3 className="title-panel">
          {t('overlapTitle', { count: competitors.length })}
        </h3>
        <p className="mt-0.5 text-[11px] text-mute">
          {t('overlapSubtitle', { count: competitors.length })}
        </p>
      </header>

      <div className="space-y-2.5">
        {competitors.map((c) => {
          const threat = (c.threatLevel || 'LOW') as ThreatLevel
          const pct = c.buyerSharePct ?? 0
          const hasShare = pct > 0
          const risk = riskForThreat(threat)
          return (
            <div
              key={c.supplierSlug}
              className="grid grid-cols-[minmax(180px,1.4fr)_1.6fr_auto] items-center gap-4 rounded px-1 py-1.5 transition-colors hover:bg-paper"
            >
              {/* Col 1: name + meta stacked */}
              <div className="min-w-0">
                <div className="truncate text-sm font-medium text-ink" lang="en" title={c.supplierName}>
                  {c.supplierName}
                </div>
                <div className="mt-0.5 flex items-center gap-2 text-[11px] tabular-nums text-mute">
                  {hasShare ? (
                    <span>
                      {c.buyerTeu > 0
                        ? t('overlapMeta', {
                            pct: pct.toFixed(2),
                            teu: Math.round(c.buyerTeu).toLocaleString(),
                          })
                        : t('overlapMetaNoTeu', { pct: pct.toFixed(2) })}
                    </span>
                  ) : (
                    <span>{t('competitorShipments', { count: c.matchingShipments })}</span>
                  )}
                  {c.trendYoy != null && c.trendYoy !== 0 && (
                    <span
                      className={`inline-flex items-center gap-0.5 ${signalTextClass(trendTier(c.trendYoy))}`}
                    >
                      {c.trendYoy > 0 ? (
                        <ArrowUp className="h-3 w-3" />
                      ) : (
                        <ArrowDown className="h-3 w-3" />
                      )}
                      {c.trendYoy > 0
                        ? t('yoyUp', { value: c.trendYoy })
                        : t('yoyDown', { value: c.trendYoy })}
                    </span>
                  )}
                </div>
              </div>

              {/* Col 2: bar */}
              <div className="h-1.5 rounded-full bg-cream">
                {hasShare && (
                  <div
                    className="h-full rounded-full bg-gold/80"
                    style={{ width: `${Math.min(pct, 100)}%` }}
                  />
                )}
              </div>

              {/* Col 3: risk chip */}
              <span
                className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${risk.cls}`}
              >
                {risk.label}
              </span>
            </div>
          )
        })}
      </div>
    </section>
  )
}
