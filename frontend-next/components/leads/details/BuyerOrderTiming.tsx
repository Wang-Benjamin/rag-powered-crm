'use client'

import React, { useMemo } from 'react'
import { useTranslations } from 'next-intl'
import { useLocale } from 'next-intl'
import { AlertTriangle, ArrowRight, Clock } from 'lucide-react'

interface BuyerOrderTimingProps {
  importContext: {
    totalShipments?: number
    matchingShipments?: number
    mostRecentShipment?: string // dd/mm/yyyy format
    topPorts?: string[]
    topProducts?: string[]
    hsCodes?: string[]
    totalSuppliers?: number
    topSuppliers?: string[]
  } | null
  timingData?: {
    daysSinceLastShipment?: number
    avgOrderCycleDays?: number
    cyclePct?: number
    reorderWindow?: 'now' | 'approaching' | 'early'
  } | null
}

function parseDdMmYyyy(dateStr: string): Date | null {
  const parts = dateStr.split('/')
  if (parts.length !== 3) return null
  const day = parseInt(parts[0], 10)
  const month = parseInt(parts[1], 10)
  const year = parseInt(parts[2], 10)
  if (isNaN(day) || isNaN(month) || isNaN(year)) return null
  const date = new Date(year, month - 1, day)
  if (isNaN(date.getTime())) return null
  return date
}

function daysBetween(a: Date, b: Date): number {
  const ms = Math.abs(b.getTime() - a.getTime())
  return Math.floor(ms / (1000 * 60 * 60 * 24))
}

function formatDate(date: Date, locale?: string): string {
  return date.toLocaleDateString(locale === 'zh-CN' ? 'zh-CN' : 'en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

const BuyerOrderTiming: React.FC<BuyerOrderTimingProps> = ({ importContext, timingData }) => {
  const t = useTranslations('leads')
  const locale = useLocale()

  const parsed = useMemo(() => {
    if (!importContext?.mostRecentShipment) return null
    const date = parseDdMmYyyy(importContext.mostRecentShipment)
    if (!date) return null
    const days = daysBetween(date, new Date())
    return { date, days, formatted: formatDate(date, locale) }
  }, [importContext?.mostRecentShipment, locale])

  const daysSince = timingData?.daysSinceLastShipment ?? parsed?.days ?? null
  const avgCycle = timingData?.avgOrderCycleDays ?? null
  const hasDeepTiming = timingData != null && avgCycle != null

  const overdueDays =
    timingData?.daysSinceLastShipment != null && timingData?.avgOrderCycleDays != null
      ? timingData.daysSinceLastShipment - timingData.avgOrderCycleDays
      : null

  const primaryHsCode = importContext?.hsCodes?.[0] ?? null

  // Empty state
  if (!importContext || !importContext.mostRecentShipment) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-center">
        <Clock className="mb-2 h-5 w-5 text-mute" />
        <p className="text-xs text-mute">{t('buyerDetail.noTimingData')}</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* Main metrics flow */}
      <div className="flex items-baseline justify-between">
        {/* Days since last import */}
        <div className="flex flex-col items-center">
          <span className="text-3xl font-bold text-deep tabular-nums">
            {daysSince ?? '—'}
          </span>
          <span className="mt-0.5 text-[11px] text-mute">
            {t('buyerDetail.daysSinceLastImport')}
          </span>
        </div>

        {hasDeepTiming && (
          <>
            {/* Arrow connector */}
            <ArrowRight className="mx-1 h-5 w-5 shrink-0 text-mute" />

            {/* Average order cycle */}
            <div className="flex flex-col items-center">
              <span className="text-3xl font-bold text-deep tabular-nums">
                ~{avgCycle}
              </span>
              <span className="mt-0.5 text-[11px] text-mute">
                {t('buyerDetail.avgCycleDays')}
              </span>
            </div>

            {/* Arrow connector */}
            <ArrowRight className="mx-1 h-5 w-5 shrink-0 text-mute" />

            {/* Overdue days */}
            <div className="flex flex-col items-center">
              <span
                className={`flex items-center gap-1 text-3xl font-bold tabular-nums ${
                  overdueDays != null && overdueDays > 0
                    ? 'text-gold'
                    : 'text-deep'
                }`}
              >
                {overdueDays != null ? Math.abs(overdueDays) : '—'}
                {overdueDays != null && overdueDays > 0 && (
                  <AlertTriangle className="h-4 w-4 text-gold" />
                )}
              </span>
              <span className="mt-0.5 text-[11px] text-mute">
                {overdueDays != null && overdueDays > 0
                  ? t('buyerDetail.daysOverdue')
                  : t('buyerDetail.daysRemaining')}
              </span>
            </div>
          </>
        )}
      </div>

      {/* Footer: last shipment date + primary HS code */}
      {parsed && (
        <div className="flex items-center justify-between text-xs text-mute">
          <span>{parsed.formatted}</span>
          {primaryHsCode && <span className="tabular-nums">HS {primaryHsCode}</span>}
        </div>
      )}
    </div>
  )
}

export default BuyerOrderTiming
