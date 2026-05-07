'use client'

import { useMemo } from 'react'
import { useTranslations } from 'next-intl'
import { useLeadContext } from '@/contexts/LeadContext'
import { Skeleton } from '@/components/ui/skeleton'
import { KpiValue } from '@/components/ui/KpiValue'

const REORDER_WINDOW_THRESHOLD = 12 // 60% of max 20pts — buyer is in/near reorder window

export default function MetricsCards() {
  const { leads, isLoading } = useLeadContext()
  const t = useTranslations('leads')

  const metrics = useMemo(() => {
    const bolLeads = leads.filter((l) => l.source === 'importyeti')

    return {
      totalBuyers: bolLeads.length,
      hotLeads: bolLeads.filter((l) => (l.score ?? 0) >= 80).length,
      marketVolume: bolLeads.reduce(
        (sum, l) => sum + (l.importContext?.matchingShipments ?? 0),
        0
      ),
      reorderWindow: bolLeads.filter(
        (l) =>
          (l.bolDetailContext?.scoringSignals?.reorderWindow?.points ?? 0) >=
          REORDER_WINDOW_THRESHOLD
      ).length,
    }
  }, [leads])

  if (!isLoading && metrics.totalBuyers === 0) return null

  const cards = [
    {
      label: t('metrics.totalBuyers'),
      value: metrics.totalBuyers.toLocaleString(),
      subtitle: t('metrics.totalBuyersSubtitle'),
    },
    {
      label: t('metrics.hotLeads'),
      value: metrics.hotLeads.toLocaleString(),
      subtitle: t('metrics.hotLeadsSubtitle'),
      accent: metrics.hotLeads > 0,
    },
    {
      label: t('metrics.marketVolume'),
      value: metrics.marketVolume.toLocaleString(),
      subtitle: t('metrics.marketVolumeSubtitle'),
    },
    {
      label: t('metrics.reorderWindow'),
      value: metrics.reorderWindow.toLocaleString(),
      subtitle: t('metrics.reorderWindowSubtitle'),
    },
  ]

  return (
    <div className="mb-4 grid grid-cols-4 gap-4">
      {cards.map((card) => (
        <div
          key={card.label}
          className="flex min-h-[96px] flex-col justify-between rounded-xl border border-rule bg-bone p-5"
        >
          {isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-2.5 w-20" />
              <Skeleton className="h-9 w-16" />
              <Skeleton className="h-2.5 w-24" />
            </div>
          ) : (
            <>
              <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-mute">
                {card.label}
              </span>
              <KpiValue accent={card.accent ? 'accent' : 'deep'}>
                {card.value}
              </KpiValue>
              <span className="text-[12px] leading-[1.35] text-mute">
                {card.subtitle}
              </span>
            </>
          )}
        </div>
      ))}
    </div>
  )
}
