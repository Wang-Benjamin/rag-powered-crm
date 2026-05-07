'use client'

import React, { useState } from 'react'
import { useTranslations } from 'next-intl'
import { Package } from 'lucide-react'

interface BuyerSupplierInfoProps {
  importContext: {
    totalSuppliers?: number
    topSuppliers?: string[]
  } | null
  supplierContext: {
    suppliers?: Array<{
      name: string
      country: string
      share: number
      shipments12M: number
      shipments1224M: number
      trend: number
      weightKg?: number
      teu?: number
    }>
    enrichedAt?: string
    bolCompanySlug?: string
  } | null
}

export default function BuyerSupplierInfo({
  importContext,
  supplierContext,
}: BuyerSupplierInfoProps) {
  const t = useTranslations('leads')
  const suppliers = supplierContext?.suppliers ?? []
  const [showAll, setShowAll] = useState(false)

  // Empty state — fall back to importContext for non-enriched leads
  if (
    suppliers.length === 0 &&
    !importContext?.totalSuppliers &&
    !importContext?.topSuppliers?.length
  ) {
    return (
      <div className="flex flex-col items-center justify-center py-6 text-center">
        <Package className="mb-1.5 h-5 w-5 text-mute" />
        <p className="text-xs text-mute">{t('buyerDetail.noSupplierData')}</p>
      </div>
    )
  }

  const hasSupplierBars = suppliers.length > 0
  const visibleSuppliers = showAll ? suppliers : suppliers.slice(0, 6)

  return (
    <div className="space-y-3">
      {/* Supplier shares — hero #1 gold, #2+ muted flat rows. */}
      {hasSupplierBars ? (
        <div>
          {/* Hero row — #1 dominant supplier, name on top, metric row below */}
          {visibleSuppliers[0] && (
            <div className="pb-2.5">
              <div className="title-block truncate" title={visibleSuppliers[0].name}>
                {visibleSuppliers[0].name}
              </div>
              <div className="mt-1 grid grid-cols-[1fr_auto_auto] items-center gap-3">
                <div className="relative h-2 rounded-full bg-cream">
                  <div
                    className="h-full rounded-full bg-gold"
                    style={{ width: `${Math.max(visibleSuppliers[0].share, 1)}%` }}
                  />
                </div>
                <span className="font-mono text-sm tabular-nums text-gold">
                  {visibleSuppliers[0].share}%
                </span>
                <span className="font-mono text-[11px] tabular-nums text-mute">
                  {visibleSuppliers[0].teu && visibleSuppliers[0].teu > 0
                    ? `${Math.round(visibleSuppliers[0].teu).toLocaleString()} TEU`
                    : ''}
                </span>
              </div>
            </div>
          )}

          {/* Muted rows — #2..N flat grid */}
          <div className="space-y-1 border-t border-rule pt-2">
            {visibleSuppliers.slice(1).map((supplier) => (
              <div
                key={supplier.name}
                className="grid grid-cols-[1fr_80px_44px_64px] items-center gap-2 py-1"
              >
                <span className="truncate text-xs text-mute" title={supplier.name}>
                  {supplier.name}
                </span>
                <div className="relative h-1.5 rounded-full bg-cream">
                  <div
                    className="h-full rounded-full bg-mute/40"
                    style={{ width: `${Math.max(supplier.share, 1)}%` }}
                  />
                </div>
                <span className="text-right font-mono text-[11px] tabular-nums text-mute">
                  {supplier.share}%
                </span>
                <span className="text-right font-mono text-[10px] tabular-nums text-mute">
                  {supplier.teu && supplier.teu > 0
                    ? `${Math.round(supplier.teu).toLocaleString()} TEU`
                    : ''}
                </span>
              </div>
            ))}
          </div>

          {suppliers.length > 6 && (
            <button
              type="button"
              onClick={() => setShowAll((prev) => !prev)}
              className="mt-2 cursor-pointer text-[11px] text-mute transition-colors hover:text-ink"
            >
              {showAll ? '收起 ▾' : `显示全部 ${suppliers.length} 家 ▸`}
            </button>
          )}

          {/* Panel caption — design's "6 家主供应商 · 全部 22 家" */}
          <div className="mt-3 border-t border-rule/60 pt-2.5 font-mono text-[12px] text-mute">
            {t('buyerDetail.supplierPanelCaption', {
              shown: visibleSuppliers.length,
              total:
                importContext?.totalSuppliers ?? suppliers.length,
            })}
          </div>
        </div>
      ) : importContext?.topSuppliers && importContext.topSuppliers.length > 0 ? (
        <div className="space-y-1.5">
          {importContext.topSuppliers.map((name) => (
            <div key={name} className="py-1 text-xs text-ink">
              {name}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}
