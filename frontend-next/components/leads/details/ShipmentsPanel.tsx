'use client'

import React, { useEffect, useMemo, useState } from 'react'
import { useTranslations } from 'next-intl'
import { ChevronLeft, ChevronRight, Ship } from 'lucide-react'
import leadsApiService from '@/lib/api/leads'
import type { BolDetailContext, RecentBol } from '@/types/leads/bol'

interface ShipmentsPanelProps {
  leadId: string
  bolDetailContext: BolDetailContext | null
}

type ChartRange = 12 | 24 | 'all'
type FilterKey = 'all' | 'recent' | 'competitors' | `hs:${string}`

const PAGE_SIZE = 18

function parseDdMmYyyy(s: string): Date | null {
  const parts = s.split('/')
  if (parts.length !== 3) return null
  const [dd, mm, yyyy] = parts.map((x) => Number(x))
  if (!dd || !mm || !yyyy) return null
  const d = new Date(yyyy, mm - 1, dd)
  return isNaN(d.getTime()) ? null : d
}

function toIsoDisplay(s: string): string {
  const parts = s.split('/')
  if (parts.length !== 3) return s
  const [dd, mm, yyyy] = parts
  return `${yyyy}-${mm}-${dd}`
}

function normalize(s: string): string {
  return s.toLowerCase().trim()
}

export default function ShipmentsPanel({
  leadId,
  bolDetailContext,
}: ShipmentsPanelProps) {
  const t = useTranslations('leads.buyerDetail')
  const bols = bolDetailContext?.recentBols ?? []
  const timeSeries = bolDetailContext?.timeSeries ?? {}

  // Fetch competitor names (for the competitors-only filter).
  const [competitorNames, setCompetitorNames] = useState<Set<string>>(new Set())
  useEffect(() => {
    let cancelled = false
    leadsApiService
      .getLeadCompetitors(leadId)
      .then((list) => {
        if (cancelled) return
        setCompetitorNames(new Set((list ?? []).map((c) => normalize(c.supplierName))))
      })
      .catch(() => {
        // Silently fail — filter just won't show any matches.
      })
    return () => {
      cancelled = true
    }
  }, [leadId])

  const [chartRange, setChartRange] = useState<ChartRange>(12)
  const [filter, setFilter] = useState<FilterKey>('all')
  const [page, setPage] = useState(0)

  // Top HS codes by count (for filter pills — up to 2).
  const topHsCodes = useMemo(() => {
    const counts = new Map<string, number>()
    for (const b of bols) {
      const hs = (b.hsCode || '').trim()
      if (!hs) continue
      counts.set(hs, (counts.get(hs) ?? 0) + 1)
    }
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 2)
      .map(([hs, count]) => ({ hs, count }))
  }, [bols])

  // Monthly chart data from timeSeries (sparse months filled with zero).
  const chartBars = useMemo(() => {
    const entries = Object.entries(timeSeries)
      .map(([k, v]) => ({ key: k, date: parseDdMmYyyy(k), v }))
      .filter((e): e is { key: string; date: Date; v: typeof timeSeries[string] } => e.date !== null)
      .sort((a, b) => a.date.getTime() - b.date.getTime())
    const window = chartRange === 'all' ? entries : entries.slice(-chartRange)
    const max = Math.max(1, ...window.map((e) => e.v.shipments))
    return { window, max }
  }, [timeSeries, chartRange])

  // Filter + paginate rows
  const filteredBols = useMemo(() => {
    const now = Date.now()
    const twelveMonthsAgo = now - 365 * 24 * 60 * 60 * 1000
    return bols
      .filter((b) => {
        if (filter === 'all') return true
        if (filter === 'recent') {
          const d = parseDdMmYyyy(b.dateFormatted)
          return d ? d.getTime() >= twelveMonthsAgo : false
        }
        if (filter === 'competitors') {
          return competitorNames.has(normalize(b.shipperName || ''))
        }
        if (filter.startsWith('hs:')) {
          const hs = filter.slice(3)
          return (b.hsCode || '').trim() === hs
        }
        return true
      })
      .sort((a, b) => {
        const ad = parseDdMmYyyy(a.dateFormatted)?.getTime() ?? 0
        const bd = parseDdMmYyyy(b.dateFormatted)?.getTime() ?? 0
        return bd - ad
      })
  }, [bols, filter, competitorNames])

  // Reset page whenever filter changes.
  useEffect(() => {
    setPage(0)
  }, [filter])

  const pageStart = page * PAGE_SIZE
  const pageRows = filteredBols.slice(pageStart, pageStart + PAGE_SIZE)
  const totalPages = Math.max(1, Math.ceil(filteredBols.length / PAGE_SIZE))

  if (!bols.length) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Ship className="mb-2 h-6 w-6 text-mute" />
        <p className="text-sm text-mute">{t('deepEnrichRequired')}</p>
      </div>
    )
  }

  const allFilterKey: FilterKey = 'all'
  const recentFilterKey: FilterKey = 'recent'
  const competitorsFilterKey: FilterKey = 'competitors'

  return (
    <div className="space-y-4 p-5">
      {/* Monthly chart */}
      {chartBars.window.length > 0 && (
        <div className="rounded-lg border border-rule bg-bone p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-[11px] font-medium tracking-wider text-mute uppercase">
              {t('chartTitle')}
            </span>
            <div className="flex items-center gap-0.5 rounded-md border border-rule bg-paper p-0.5 text-[11px]">
              {([12, 24, 'all'] as const).map((r) => (
                <button
                  key={r}
                  onClick={() => setChartRange(r)}
                  className={`rounded px-2 py-0.5 transition-colors ${
                    chartRange === r ? 'bg-bone text-ink shadow-sm' : 'text-mute hover:text-ink'
                  }`}
                >
                  {r === 12 ? t('chartRange12m') : r === 24 ? t('chartRange24m') : t('chartRangeAll')}
                </button>
              ))}
            </div>
          </div>
          <div className="flex h-24 items-end gap-[3px]">
            {chartBars.window.map((e) => {
              const heightPct = (e.v.shipments / chartBars.max) * 100
              const chinaPct =
                e.v.shipments > 0 ? ((e.v.chinaShipments ?? 0) / e.v.shipments) * 100 : 0
              return (
                <div
                  key={e.key}
                  className="flex h-full min-w-[3px] flex-1 flex-col justify-end"
                  title={`${e.key}: ${e.v.shipments}`}
                >
                  <div
                    className="flex w-full flex-col-reverse overflow-hidden rounded-t-sm"
                    style={{ height: `${Math.max(heightPct, 2)}%` }}
                  >
                    {chinaPct > 0 ? (
                      <>
                        <div className="w-full bg-accent/70" style={{ flexGrow: chinaPct }} />
                        <div className="w-full bg-fog" style={{ flexGrow: 100 - chinaPct }} />
                      </>
                    ) : (
                      <div className="w-full bg-fog" style={{ flexGrow: 1 }} />
                    )}
                  </div>
                </div>
              )
            })}
          </div>
          <div className="mt-2 flex items-center gap-4">
            <div className="flex items-center gap-1.5">
              <div className="h-2 w-2 rounded-sm bg-accent/70" />
              <span className="text-[10px] text-mute">{t('chinaConcentration').split(' ')[0]}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="h-2 w-2 rounded-sm bg-fog" />
              <span className="text-[10px] text-mute">·</span>
            </div>
          </div>
        </div>
      )}

      {/* Filter pills */}
      <div className="flex flex-wrap items-center gap-2">
        <FilterPill
          active={filter === allFilterKey}
          onClick={() => setFilter(allFilterKey)}
          label={t('filterAll')}
          count={bols.length}
        />
        <FilterPill
          active={filter === recentFilterKey}
          onClick={() => setFilter(recentFilterKey)}
          label={t('filterRecent')}
        />
        {topHsCodes.map((h) => {
          const key: FilterKey = `hs:${h.hs}`
          return (
            <FilterPill
              key={h.hs}
              active={filter === key}
              onClick={() => setFilter(key)}
              label={`${t('hsFilterPrefix')} ${h.hs}`}
              count={h.count}
            />
          )
        })}
        {competitorNames.size > 0 && (
          <FilterPill
            active={filter === competitorsFilterKey}
            onClick={() => setFilter(competitorsFilterKey)}
            label={t('filterCompetitorsOnly')}
            gold
          />
        )}
      </div>

      {/* Shipments table */}
      <div className="overflow-x-auto rounded-lg border border-rule bg-bone">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-rule bg-paper text-left text-[11px] tracking-wider text-mute uppercase">
              <th className="px-3 py-2 font-medium">{t('bolDate')}</th>
              <th className="px-3 py-2 font-medium">{t('bolProduct')}</th>
              <th className="px-3 py-2 font-medium">{t('bolShipper')}</th>
              <th className="px-3 py-2 font-medium">{t('bolHsCode')}</th>
              <th className="px-3 py-2 text-right font-medium">{t('bolQuantity')}</th>
              <th className="px-3 py-2 text-right font-medium">{t('bolWeight')}</th>
              <th className="px-3 py-2 text-right font-medium">TEU</th>
              <th className="px-3 py-2 font-medium">{t('shipmentsColOrigin')}</th>
            </tr>
          </thead>
          <tbody>
            {pageRows.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-3 py-10 text-center text-xs text-mute">
                  {t('shipmentsEmpty')}
                </td>
              </tr>
            ) : (
              pageRows.map((bol, i) => (
                <ShipmentRow key={`${pageStart + i}`} bol={bol} isCompetitor={competitorNames.has(normalize(bol.shipperName || ''))} />
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pager */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-xs text-mute">
          <span className="tabular-nums">
            {t('shipmentsPager', {
              start: pageStart + 1,
              end: Math.min(pageStart + PAGE_SIZE, filteredBols.length),
              total: filteredBols.length,
            })}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              aria-label={t('prevPage')}
              className="rounded border border-rule bg-paper p-1 transition-colors enabled:hover:bg-cream disabled:opacity-40"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </button>
            <span className="px-2 tabular-nums">
              {page + 1} / {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              aria-label={t('nextPage')}
              className="rounded border border-rule bg-paper p-1 transition-colors enabled:hover:bg-cream disabled:opacity-40"
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function FilterPill({
  active,
  onClick,
  label,
  count,
  gold,
}: {
  active: boolean
  onClick: () => void
  label: string
  count?: number
  gold?: boolean
}) {
  const base =
    'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] transition-colors'
  const stateClass = active
    ? gold
      ? 'border-gold bg-gold-lo text-ink'
      : 'border-ink bg-ink text-bone'
    : gold
      ? 'border-gold/40 bg-bone text-gold hover:bg-gold-lo'
      : 'border-rule bg-bone text-mute hover:text-ink'
  return (
    <button onClick={onClick} className={`${base} ${stateClass}`}>
      <span>{label}</span>
      {count != null && <span className="tabular-nums opacity-70">{count}</span>}
    </button>
  )
}

function ShipmentRow({ bol, isCompetitor }: { bol: RecentBol; isCompetitor: boolean }) {
  return (
    <tr
      className={`border-b border-rule transition-colors last:border-0 hover:bg-paper ${
        isCompetitor ? 'bg-gold-lo/40' : ''
      }`}
    >
      <td className="px-3 py-2 font-mono text-xs text-mute tabular-nums">
        {toIsoDisplay(bol.dateFormatted)}
      </td>
      <td className="max-w-[280px] px-3 py-2 text-xs text-ink" title={bol.productDescription}>
        <div className="truncate">{bol.productDescription || '—'}</div>
      </td>
      <td className="max-w-[200px] px-3 py-2 text-xs text-ink" title={bol.shipperName}>
        <div className="truncate">{bol.shipperName || '—'}</div>
      </td>
      <td className="px-3 py-2 font-mono text-xs text-mute">{bol.hsCode || '—'}</td>
      <td className="px-3 py-2 text-right text-xs text-mute tabular-nums">
        {bol.quantity ? `${Number(bol.quantity).toLocaleString()} ${bol.quantityUnit ?? ''}`.trim() : '—'}
      </td>
      <td className="px-3 py-2 text-right text-xs text-mute tabular-nums">
        {bol.weightInKg ? Number(bol.weightInKg).toLocaleString(undefined, { maximumFractionDigits: 0 }) : '—'}
      </td>
      <td className="px-3 py-2 text-right text-xs text-mute tabular-nums">
        {bol.teu ? Number(bol.teu).toLocaleString(undefined, { maximumFractionDigits: 1 }) : '—'}
      </td>
      <td className="px-3 py-2 font-mono text-[11px] text-mute">
        {bol.countryCode || bol.country || '—'}
      </td>
    </tr>
  )
}
