'use client'

import React, { useState } from 'react'
import { useTranslations } from 'next-intl'
import { signalTextClass, scoreTier } from '@/lib/design/signal'

interface BuyerScoreCardProps {
  score?: number
  bolDetailContext?: {
    scoringSignals: {
      reorderWindow: { points: number; max: number }
      supplierDiversification: { points: number; max: number }
      competitiveDisplacement: { points: number; max: number }
      volumeFit: { points: number; max: number }
      recencyActivity: { points: number; max: number }
      hsRelevance: { points: number; max: number }
      shipmentScale: { points: number; max: number }
      switchingVelocity: { points: number; max: number }
      buyerGrowth: { points: number; max: number }
      supplyChainVulnerability: { points: number; max: number }
      orderConsistency: { points: number; max: number }
    }
  } | null
}

const SIGNAL_KEYS: Record<string, string> = {
  reorderWindow: 'signalReorderWindow',
  supplierDiversification: 'signalSupplierDiv',
  competitiveDisplacement: 'signalCompDisplacement',
  volumeFit: 'signalVolumeFit',
  recencyActivity: 'signalRecency',
  hsRelevance: 'signalHsRelevance',
  shipmentScale: 'signalShipmentScale',
  switchingVelocity: 'signalSwitchVelocity',
  buyerGrowth: 'signalBuyerGrowth',
  supplyChainVulnerability: 'signalSupplyChainVuln',
  orderConsistency: 'signalOrderConsistency',
}

export default function BuyerScoreCard({ score, bolDetailContext }: BuyerScoreCardProps) {
  const t = useTranslations('leads')
  const [expanded, setExpanded] = useState(false)

  if (score == null) {
    return (
      <div className="flex flex-col items-center py-4">
        <span className="text-5xl font-bold text-mute tabular-nums">—</span>
      </div>
    )
  }

  const scoreColor = signalTextClass(scoreTier(score))
  const priorityLabel =
    score >= 80
      ? t('buyerDetail.priorityHigh')
      : score >= 50
        ? t('buyerDetail.priorityMedium')
        : t('buyerDetail.priorityLow')

  return (
    <div className="flex flex-col items-start">
      <span className={`font-display text-5xl leading-none tabular-nums ${scoreColor}`}>
        {score}
      </span>
      <span className="mt-2 rounded-full border border-rule bg-cream px-2 py-0.5 text-xs font-medium text-ink">
        {priorityLabel}
      </span>

      {bolDetailContext?.scoringSignals && (
        <div className="mt-3 w-full">
          <button
            type="button"
            onClick={() => setExpanded((prev) => !prev)}
            className="cursor-pointer text-[11px] text-mute transition-colors hover:text-ink"
          >
            {expanded ? t('buyerDetail.collapseScoring') : t('buyerDetail.viewScoringDetail')}
          </button>

          {expanded && (
            <div className="mt-2 space-y-1.5">
              {Object.entries(bolDetailContext.scoringSignals).map(([key, signal]) => {
                const tKey = SIGNAL_KEYS[key]
                const label = tKey ? t(`buyerDetail.${tKey}` as any) : key
                const fillPercent = signal.max > 0 ? (signal.points / signal.max) * 100 : 0

                return (
                  <div key={key} className="flex items-center gap-2">
                    <span className="w-[100px] shrink-0 text-[11px] text-ink">{label}</span>
                    <div className="h-1.5 flex-1 rounded-full bg-cream">
                      <div
                        className="h-1.5 rounded-full bg-fog"
                        style={{ width: `${Math.min(fillPercent, 100)}%` }}
                      />
                    </div>
                    <span className="w-[36px] text-right text-[10px] text-mute tabular-nums">
                      {signal.points}/{signal.max}
                    </span>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
