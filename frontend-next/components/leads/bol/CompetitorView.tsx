'use client'

import React, { useState } from 'react'
import { useTranslations } from 'next-intl'
import { useParams } from 'next/navigation'
import { useCompetitors } from '@/hooks/useCompetitors'
import { CompetitorTable } from './CompetitorTable'
import CompetitorDetailPage from './CompetitorDetailPage'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { KpiValue } from '@/components/ui/KpiValue'
import Tooltip from '@/components/ui/tooltip'
import { EmptyState } from '@/components/ui/states/EmptyState'
import { TrendingDown, X, Shield, Info } from 'lucide-react'

export default function CompetitorView() {
  const t = useTranslations('leads')
  const params = useParams()
  const workspaceId = params?.workspaceId as string
  const { competitors, kpis, alerts, loading, error, dismissAlert } = useCompetitors()
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null)

  return (
    <div className="mx-auto max-w-[1400px] p-6">
      {/* Opportunity banners — accent-framed, "declining competitors = opportunity for us" */}
      {alerts.length > 0 && (
        <div className="mb-4 flex flex-col gap-1.5">
          {alerts.map((alert, i) => (
            <div
              key={`${alert.supplierSlug}-${alert.type}-${i}`}
              className="flex items-center gap-2.5 rounded-md border border-l-[3px] border-rule border-l-accent bg-accent-lo px-3.5 py-2.5 text-[13px] leading-[1.4] text-ink"
            >
              <TrendingDown className="h-4 w-4 flex-shrink-0 text-accent" />
              <div className="min-w-0 flex-1">
                {alert.type === 'volume_drop' ? (
                  <>
                    <span className="font-medium text-deep">{alert.supplierName}</span>{' '}
                    {t('bol.competitors.alertVolumeDrop', {
                      name: '',
                      pct: Math.abs(alert.trendYoy ?? 0).toFixed(0),
                    }).replace(/^\s*[,，]?\s*/, '')}
                  </>
                ) : (
                  alert.message
                )}
              </div>
              <button
                onClick={() => dismissAlert(i)}
                aria-label="Dismiss"
                className="flex-shrink-0 rounded-sm p-0.5 text-mute transition-colors hover:bg-accent/12 hover:text-ink"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* KPI strip — matches Buyers editorial serif style */}
      {loading ? (
        <div className="mb-4 grid grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="flex min-h-[96px] flex-col justify-between rounded-xl border border-rule bg-bone p-5"
            >
              <Skeleton className="h-2.5 w-20" />
              <Skeleton className="h-9 w-16" />
              <Skeleton className="h-2.5 w-24" />
            </div>
          ))}
        </div>
      ) : kpis ? (
        <div className="mb-4 grid grid-cols-4 gap-4">
          <KpiCard
            label={t('bol.competitors.kpiCompetitors')}
            value={kpis.totalCompetitors.toLocaleString()}
            sub={t('bol.competitors.kpiSameHsCode')}
          />
          <KpiCard
            label={t('bol.competitors.kpiTopVolume')}
            value={`~${kpis.topVolumeShipments.toLocaleString()}`}
            sub={kpis.topVolumeName}
          />
          <KpiCard
            label={t('bol.competitors.kpiSharedBuyers')}
            value={kpis.sharedBuyersCount.toLocaleString()}
            sub={t('bol.competitors.kpiOverlap')}
          />
          <KpiCard
            label={t('bol.competitors.kpiVulnerable')}
            value={kpis.vulnerableCount.toLocaleString()}
            sub={t('bol.competitors.kpiDeclining')}
            tooltip={t('bol.competitors.kpiVulnerableTooltip')}
            accent={kpis.vulnerableCount > 0}
          />
        </div>
      ) : null}

      {/* Error */}
      {error && (
        <div className="mb-4 rounded-md border border-rule bg-bone px-4 py-3 text-[13px] text-threat">
          {error}
        </div>
      )}

      {/* Competitor table or empty state */}
      {!loading && competitors.length === 0 ? (
        <div className="rounded-xl border border-rule bg-bone">
          <EmptyState
            icon={Shield}
            title={t('bol.competitors.emptyTitle')}
            description={t('bol.competitors.emptyDescription')}
          />
        </div>
      ) : (
        <>
          <CompetitorTable
            competitors={competitors}
            loading={loading}
            onSelect={(c) => {
              if (!c.isBlurred) setSelectedSlug(c.supplierSlug)
            }}
          />
          {competitors.some((c) => c.isBlurred) && (
            <div className="mt-3 flex items-center justify-between rounded-md border border-rule bg-paper px-4 py-3">
              <p className="text-[13px] text-mute">
                {t('bol.competitors.upgradeBanner', {
                  visible: competitors.filter((c) => !c.isBlurred).length,
                  total: competitors.length,
                })}
              </p>
              <a
                href="mailto:sales@prelude.so?subject=Upgrade%20Plan"
                className="text-[13px] font-medium text-deep underline underline-offset-2 hover:text-accent"
              >
                {t('bol.competitors.upgradePlan')}
              </a>
            </div>
          )}
        </>
      )}

      <Dialog open={!!selectedSlug} onOpenChange={(open) => !open && setSelectedSlug(null)}>
        <DialogContent className="h-[95vh] w-full max-w-full overflow-y-auto p-0">
          {selectedSlug && (
            <CompetitorDetailPage slug={selectedSlug} />
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}

function KpiCard({
  label,
  value,
  sub,
  tooltip,
  accent,
}: {
  label: string
  value: string | number
  sub: string
  tooltip?: string
  accent?: boolean
}) {
  const labelEl = (
    <span className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.12em] text-mute">
      {label}
      {tooltip && <Info className="h-2.5 w-2.5" />}
    </span>
  )
  return (
    <div className="flex min-h-[96px] flex-col justify-between rounded-xl border border-rule bg-bone p-5">
      {tooltip ? (
        <Tooltip content={tooltip} position="top" showIcon={false}>
          {labelEl}
        </Tooltip>
      ) : (
        labelEl
      )}
      <KpiValue accent={accent ? 'accent' : 'deep'}>{value}</KpiValue>
      <span className="text-[12px] leading-[1.35] text-mute">{sub}</span>
    </div>
  )
}
