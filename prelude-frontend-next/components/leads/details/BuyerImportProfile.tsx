'use client'

import React, { useMemo } from 'react'
import { useTranslations } from 'next-intl'
import { PackageSearch } from 'lucide-react'

interface BuyerImportProfileProps {
  importContext: object | null
  bolDetailContext?: {
    timeSeries: Record<
      string,
      { shipments: number; weight: number; teu: number; chinaShipments?: number }
    >
  } | null
}

/** Parse dd/mm/yyyy into a sortable Date */
function parseDdMmYyyy(key: string): Date {
  const [dd, mm, yyyy] = key.split('/')
  return new Date(Number(yyyy), Number(mm) - 1, Number(dd))
}

/** Format a dd/mm/yyyy key to a short month label like "Jan" or "Jul" */
function toMonthLabel(key: string): string {
  const d = parseDdMmYyyy(key)
  return d.toLocaleDateString('en-US', { month: 'short' }).slice(0, 3)
}

export default function BuyerImportProfile({
  importContext,
  bolDetailContext,
}: BuyerImportProfileProps) {
  const t = useTranslations('leads')

  // Prepare sparkline data
  const sparklineData = useMemo(() => {
    const ts = bolDetailContext?.timeSeries
    if (!ts) return null

    const entries = Object.entries(ts)
    if (entries.length === 0) return null

    // Sort by date ascending
    const sorted = entries.sort(
      ([a], [b]) => parseDdMmYyyy(a).getTime() - parseDdMmYyyy(b).getTime()
    )

    // Take last 12 months (design shows May → Apr as a rolling window)
    const sliced = sorted.slice(-12)

    const maxShipments = Math.max(...sliced.map(([, v]) => v.shipments), 1)

    return sliced.map(([key, val]) => ({
      key,
      shipments: val.shipments,
      chinaShipments: val.chinaShipments ?? 0,
      heightPct: (val.shipments / maxShipments) * 100,
      chinaPct: val.shipments > 0 ? ((val.chinaShipments ?? 0) / val.shipments) * 100 : 0,
    }))
  }, [bolDetailContext])

  if (!importContext) {
    return (
      <div className="flex flex-col items-center justify-center py-6 text-center">
        <PackageSearch className="mb-1.5 h-5 w-5 text-mute" />
        <p className="text-xs text-mute">{t('buyerDetail.noImportData')}</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* 12-bar CSS chart — China stacked on Other, per-month axis labels. */}
      {sparklineData && (
        <div>
          <div className="flex h-20 items-end gap-1">
            {sparklineData.map((bar) => (
              <div
                key={bar.key}
                className="flex min-w-[6px] flex-1 flex-col justify-end"
                style={{ height: '100%' }}
              >
                <div
                  className="flex w-full flex-col-reverse overflow-hidden rounded-t-sm"
                  style={{ height: `${Math.max(bar.heightPct, 2)}%` }}
                >
                  {bar.chinaPct > 0 ? (
                    <>
                      {/* China portion (bottom, via flex-col-reverse) */}
                      <div className="w-full bg-accent" style={{ flexGrow: bar.chinaPct }} />
                      {/* Non-China portion (top) */}
                      <div className="w-full bg-fog" style={{ flexGrow: 100 - bar.chinaPct }} />
                    </>
                  ) : (
                    <div className="w-full bg-fog" style={{ flexGrow: 1 }} />
                  )}
                </div>
              </div>
            ))}
          </div>
          {/* Every-month axis (3-letter) */}
          <div className="mt-1 flex gap-1">
            {sparklineData.map((bar) => (
              <div key={bar.key} className="min-w-[6px] flex-1 text-center">
                <span className="text-[9px] text-mute uppercase">{toMonthLabel(bar.key)}</span>
              </div>
            ))}
          </div>
          {/* Legend */}
          <div className="mt-2 flex items-center gap-4">
            <div className="flex items-center gap-1.5">
              <div className="h-2.5 w-2.5 rounded-sm bg-accent" />
              <span className="text-[10px] text-mute">{t('buyerDetail.legendChina')}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="h-2.5 w-2.5 rounded-sm bg-fog" />
              <span className="text-[10px] text-mute">{t('buyerDetail.legendOther')}</span>
            </div>
          </div>
          {/* Caption — design's "近 12 个月 · TEU" */}
          <div className="mt-3 border-t border-rule/60 pt-2.5 font-mono text-[12px] text-mute">
            {t('buyerDetail.importTrendPanelCaption')}
          </div>
        </div>
      )}

    </div>
  )
}
