'use client'

import React from 'react'
import { useTranslations } from 'next-intl'
import { signalTextClass, trendTier } from '@/lib/design/signal'

interface BuyerKpiStripProps {
  supplierCount: number | null
  chinaConcentration: number | null
  growth12mPct: number | null
  totalShipments: number | null
}

/**
 * Design-matched 4-KPI strip: {Suppliers} · {China concentration} · {12m growth} · {Total tonnage TEU}.
 * Layout mirrors the design's `.kpi-strip` with a serif numeric face and uppercase small label.
 * Cells only render when the underlying value is non-null, with vertical rules between populated cells.
 */
export default function BuyerKpiStrip({
  supplierCount,
  chinaConcentration,
  growth12mPct,
  totalShipments,
}: BuyerKpiStripProps) {
  const t = useTranslations('leads.buyerDetail')

  const cells: Array<React.ReactNode> = []
  if (supplierCount != null) {
    cells.push(
      <KpiCell
        key="suppliers"
        value={<span className="tabular-nums">{supplierCount}</span>}
        label={t('kpiSuppliers')}
      />,
    )
  }
  if (chinaConcentration != null) {
    cells.push(
      <KpiCell
        key="china"
        value={<span className="tabular-nums">{chinaConcentration.toFixed(1)}%</span>}
        label={t('kpiChinaShort')}
      />,
    )
  }
  if (growth12mPct != null) {
    const sign = growth12mPct > 0 ? '+' : ''
    cells.push(
      <KpiCell
        key="growth"
        value={
          <span className={`tabular-nums ${signalTextClass(trendTier(growth12mPct))}`}>
            {sign}
            {growth12mPct.toFixed(0)}%
          </span>
        }
        label={t('kpiGrowth12mShort')}
      />,
    )
  }
  if (totalShipments != null && totalShipments > 0) {
    cells.push(
      <KpiCell
        key="shipments"
        value={<span className="tabular-nums">{totalShipments.toLocaleString()}</span>}
        label={t('shipmentsTotal')}
      />,
    )
  }

  if (cells.length === 0) return null

  return (
    <div className="grid gap-5 border-y border-rule py-5 sm:grid-cols-2 lg:grid-cols-4">
      {cells.map((cell, i) => (
        <div key={i}>{cell}</div>
      ))}
    </div>
  )
}

function KpiCell({ value, label }: { value: React.ReactNode; label: string }) {
  return (
    <div className="py-0.5">
      <div className="font-display text-3xl leading-tight text-deep">{value}</div>
      <div className="mt-0.5 font-mono text-[11px] tracking-[0.04em] text-mute uppercase">{label}</div>
    </div>
  )
}
