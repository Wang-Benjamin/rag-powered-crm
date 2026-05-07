'use client'

import React, { useEffect, useMemo, useState } from 'react'
import { useTranslations } from 'next-intl'
import Tooltip from '@/components/ui/tooltip'
import { EmptyState } from '@/components/ui/states/EmptyState'
import {
  MapPin,
  Shield,
  Clock,
  ChevronRight,
  Swords,
} from 'lucide-react'
import { PageLoader } from '@/components/ui/page-loader'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
} from 'recharts'
import leadsApiService from '@/lib/api/leads'
import type {
  Competitor,
  CompetitorSharedBuyer,
} from '@/types/leads/bol'
import { useDesignTokens } from '@/lib/design/tokens'
import { KpiValue } from '@/components/ui/KpiValue'

interface CompetitorDetailPageProps {
  slug: string
}

type Range = 12 | 24 | -1 // -1 = all

export default function CompetitorDetailPage({ slug }: CompetitorDetailPageProps) {
  const t = useTranslations('leads')
  const [competitor, setCompetitor] = useState<
    (Competitor & { sharedBuyers?: CompetitorSharedBuyer[] }) | null
  >(null)
  const [loading, setLoading] = useState(true)
  const [range, setRange] = useState<Range>(12)

  useEffect(() => {
    let cancelled = false
    async function fetchDetail() {
      setLoading(true)
      try {
        const result = await leadsApiService.getCompetitorDetail(slug)
        if (!cancelled) setCompetitor(result)
      } catch {
        if (!cancelled) setCompetitor(null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    fetchDetail()
    return () => {
      cancelled = true
    }
  }, [slug])

  if (loading) {
    return (
      <div className="flex h-full min-h-[400px] items-center justify-center bg-bone">
        <PageLoader label={t('bol.competitorDetail.loading')} />
      </div>
    )
  }

  if (!competitor) {
    return (
      <div className="mx-auto max-w-[1200px] bg-bone p-6">
        <EmptyState
          icon={Shield}
          title={t('bol.competitorDetail.notFound')}
          description={t('bol.competitorDetail.notFoundDescription')}
        />
      </div>
    )
  }

  return <CompetitorDetailContent competitor={competitor} range={range} setRange={setRange} />
}

function CompetitorDetailContent({
  competitor,
  range,
  setRange,
}: {
  competitor: Competitor & { sharedBuyers?: CompetitorSharedBuyer[] }
  range: Range
  setRange: (r: Range) => void
}) {
  const t = useTranslations('leads')
  const kit = useDesignTokens()
  const supplierNameCn = (competitor as any).supplierNameCn || (competitor as any).supplier_name_cn || ''
  const primaryName = supplierNameCn || competitor.supplierName
  const aliasName = supplierNameCn ? competitor.supplierName : ''
  const location = competitor.address || competitor.country || competitor.countryCode || ''
  const threatScore = competitor.threatScore ?? 0
  const aliases = (competitor as any).alsoKnownNames || (competitor as any).also_known_names || []
  const overlapSlugs = new Set(
    (competitor.overlapBuyerSlugs ?? []).map((s: string) => s.toLowerCase())
  )
  const companiesRaw =
    (competitor as any).companiesTable || (competitor as any).companies_table
  const companies: any[] = Array.isArray(companiesRaw) ? companiesRaw : []
  const concentration =
    (competitor as any).customerConcentration ||
    (competitor as any).customer_concentration
  const sharedBuyers: CompetitorSharedBuyer[] = competitor.sharedBuyers ?? []

  const lastUpdatedRaw = (competitor as any).lastUpdatedAt || (competitor as any).last_updated_at
  const lastUpdated = lastUpdatedRaw
    ? new Date(lastUpdatedRaw).toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })
    : null

  const hsCodesList = (competitor.hsCodes ?? []).slice(0, 3)

  // Chart data with range filter
  const chartData = useMemo(() => {
    let tsObj: Record<string, { shipments?: number }> | null = null
    const ts = competitor.timeSeries
    if (typeof ts === 'string') {
      try {
        tsObj = JSON.parse(ts)
      } catch {
        /* ignore */
      }
    } else if (ts && typeof ts === 'object' && !Array.isArray(ts)) {
      tsObj = ts as Record<string, { shipments?: number }>
    }
    if (!tsObj) return []
    const all = Object.entries(tsObj)
      .map(([date, d]) => ({ month: date, shipments: d?.shipments ?? 0 }))
      .sort((a, b) => new Date(a.month).getTime() - new Date(b.month).getTime())
    return range === -1 ? all : all.slice(-range)
  }, [competitor.timeSeries, range])

  // Shared buyers preview — overlap first, then top-volume, capped at 6
  const shareList = useMemo(() => {
    const annotated = companies.map((c: any) => {
      const key = (c.key || c.company_name || c.companyName || '')
        .replace('/company/', '')
        .toLowerCase()
      return { ...c, isOverlap: overlapSlugs.has(key) }
    })
    annotated.sort((a, b) => {
      if (a.isOverlap !== b.isOverlap) return a.isOverlap ? -1 : 1
      return (
        (b.shipments_percents_company ?? b.shipmentsPercentsCompany ?? 0) -
        (a.shipments_percents_company ?? a.shipmentsPercentsCompany ?? 0)
      )
    })
    return annotated.slice(0, 6)
  }, [companies, overlapSlugs])

  // Dossier banner data
  const showDossier = (competitor.trendYoy ?? 0) > 0 && (competitor.overlapCount ?? 0) > 0
  const trendPctAbs =
    competitor.trendYoy != null ? Math.abs(competitor.trendYoy).toFixed(0) : '0'
  const topTwoNames = sharedBuyers.slice(0, 2).map((b) => b.buyerName).filter(Boolean)
  const hasNamedBuyers = topTwoNames.length >= 2

  // KPI: shared-of-yours percent
  const sharedPct =
    competitor.overlapCount > 0 && competitor.totalCustomers > 0
      ? Math.round((competitor.overlapCount / competitor.totalCustomers) * 100 * 10) / 10
      : 0

  return (
    <div className="mx-auto max-w-[1200px] bg-bone">
      <div className="space-y-6 p-7">
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <h1 className="title-page">
              {primaryName}
              <span className="mx-[6px] font-normal text-mute">·</span>
              <span
                className="font-display italic font-normal"
                style={{ color: 'var(--gold)' }}
              >
                {t('bol.competitorDetail.mainThreat')}
              </span>
              <span
                className="ml-[10px] inline-flex items-center whitespace-nowrap rounded-full px-2 py-0.5 align-middle font-mono text-[11px] relative -top-[3px]"
                style={{
                  background: 'color-mix(in oklab, var(--gold) 14%, var(--bone))',
                  color: 'color-mix(in oklab, var(--gold), var(--deep) 30%)',
                }}
              >
                {t('bol.competitorDetail.growing')}
              </span>
            </h1>
            {aliasName && (
              <div className="mt-[2px] font-mono text-[13px] tracking-[0.01em] text-mute" lang="en">
                {aliasName}
              </div>
            )}
            <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] text-mute">
              {location && (
                <>
                  <span className="inline-flex items-center gap-1">
                    <MapPin className="h-3.5 w-3.5" />
                    <span lang="en">{location}</span>
                  </span>
                  <span className="text-rule">·</span>
                </>
              )}
              {lastUpdated && (
                <>
                  <span className="inline-flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {t('bol.competitorDetail.updatedAt', { date: lastUpdated })}
                  </span>
                  {hsCodesList.length > 0 && <span className="text-rule">·</span>}
                </>
              )}
              {hsCodesList.length > 0 && (
                <span className="inline-flex items-center gap-1.5">
                  <span className="font-mono text-[11px] uppercase tracking-[0.1em]">
                    {t('bol.competitorDetail.overlapHs')}
                  </span>
                  <span className="font-mono tabular-nums text-ink">
                    {hsCodesList.join(', ')}
                  </span>
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Aliases */}
        {aliases.length > 0 && (
          <div className="-mt-2 flex items-baseline gap-3">
            <span className="shrink-0 font-mono text-[11px] uppercase tracking-[0.12em] text-mute">
              {(t('bol.competitorDetail.alsoKnownAs') as string).replace(/:$/, '')}
            </span>
            <span className="font-mono text-[12.5px] leading-[1.6] text-ink" lang="en">
              {aliases.slice(0, 4).join(', ')}
              {aliases.length > 4 && (
                <Tooltip
                  content={aliases.slice(4).join(', ')}
                  position="bottom"
                  showIcon={false}
                >
                  <span className="ml-2 inline-flex cursor-help items-center rounded-full border border-rule bg-bone px-2 py-0.5 font-mono text-[11px] text-mute">
                    +{aliases.length - 4} more
                  </span>
                </Tooltip>
              )}
            </span>
          </div>
        )}

        {/* Dossier banner */}
        {showDossier && (
          <div className="flex items-start gap-3 rounded-xl bg-deep px-5 py-4 text-paper">
            <Swords className="mt-0.5 h-5 w-5 shrink-0" style={{ color: kit.gold || 'var(--gold)' }} />
            <div className="flex-1 text-[14px] leading-[1.6]">
              {hasNamedBuyers
                ? t.rich('bol.competitorDetail.dossierTemplate', {
                    name: primaryName,
                    pct: trendPctAbs,
                    newCount: competitor.overlapCount ?? 0,
                    topBuyer1: topTwoNames[0] ?? '',
                    topBuyer2: topTwoNames[1] ?? '',
                    em: (chunks) => (
                      <em className="font-semibold not-italic" style={{ color: kit.gold || 'var(--gold)' }}>
                        {chunks}
                      </em>
                    ),
                    b: (chunks) => <b className="font-semibold">{chunks}</b>,
                  })
                : t.rich('bol.competitorDetail.dossierTemplateNoNames', {
                    name: primaryName,
                    pct: trendPctAbs,
                    newCount: competitor.overlapCount ?? 0,
                    em: (chunks) => (
                      <em className="font-semibold not-italic" style={{ color: kit.gold || 'var(--gold)' }}>
                        {chunks}
                      </em>
                    ),
                    b: (chunks) => <b className="font-semibold">{chunks}</b>,
                  })}
            </div>
          </div>
        )}

        {/* KPI strip */}
        <div className="grid grid-cols-4 gap-4">
          <KpiCard
            label={t('bol.competitorDrawer.volumeToUs')}
            value={
              competitor.matchingShipments && competitor.matchingShipments > 0
                ? `~${competitor.matchingShipments.toLocaleString()}`
                : '0'
            }
            sub={
              competitor.totalShipments > 0 &&
              competitor.totalShipments !== competitor.matchingShipments
                ? `${t('bol.competitorDetail.ofTotal', { n: competitor.totalShipments.toLocaleString() })}${competitor.weightKg > 0 ? ` · ${Math.round(competitor.weightKg / 1000).toLocaleString()}t` : ''}`
                : undefined
            }
          />
          <KpiCard
            label={t('bol.competitorDrawer.usBuyers')}
            value={(competitor.totalCustomers ?? 0).toLocaleString()}
            sub={t('bol.competitorDetail.coverage')}
          />
          <KpiCard
            label={t('bol.competitorDrawer.sharedBuyers')}
            value={(competitor.overlapCount ?? 0).toLocaleString()}
            sub={
              sharedPct > 0
                ? t('bol.competitorDetail.ofYourBuyers', { pct: sharedPct })
                : undefined
            }
          />
          <KpiCard
            label={t('bol.competitors.columnThreat')}
            value={threatScore}
            accent="gold"
            threatBar={threatScore}
          />
        </div>

        {/* Trend chart */}
        <SectionBlock
          heading={t('bol.competitorDetail.trendHeading')}
          action={
            <Segmented
              options={[
                { key: '12', label: t('bol.competitorDetail.range12m'), value: 12 as Range },
                { key: '24', label: t('bol.competitorDetail.range24m'), value: 24 as Range },
                { key: 'all', label: t('bol.competitorDetail.rangeAll'), value: -1 as Range },
              ]}
              selected={range}
              onChange={setRange}
            />
          }
        >
          {chartData.length > 0 ? (
            <div className="mt-4 h-56">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="shipGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={kit.ink || '#000'} stopOpacity={0.12} />
                      <stop offset="95%" stopColor={kit.ink || '#000'} stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    strokeDasharray="2 3"
                    stroke={kit.rule || '#ddd'}
                    vertical={false}
                  />
                  <XAxis
                    dataKey="month"
                    tick={{ fontSize: 10, fill: kit.mute || '#888' }}
                    tickFormatter={(v: string) => {
                      const parts = v?.split('/') ?? []
                      return parts.length >= 3 ? `${parts[1]}/${parts[2]?.slice(2)}` : v
                    }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: kit.mute || '#888' }}
                    axisLine={false}
                    tickLine={false}
                    width={40}
                  />
                  <RechartsTooltip
                    contentStyle={{
                      fontSize: 12,
                      borderRadius: 10,
                      border: `1px solid ${kit.rule || '#ddd'}`,
                      background: kit.bone || '#fff',
                      color: kit.ink || '#333',
                      padding: '8px 12px',
                    }}
                    formatter={(value: number) => [`${value.toLocaleString()} shipments`, '']}
                  />
                  <Area
                    type="monotone"
                    dataKey="shipments"
                    stroke={kit.ink || '#333'}
                    strokeOpacity={0.8}
                    strokeWidth={1.5}
                    fill="url(#shipGradient)"
                    dot={(props) => {
                      const { cx, cy, index, payload: _p } = props as any
                      const isLast = index === chartData.length - 1
                      return isLast ? (
                        <circle
                          key={`dot-${index}`}
                          cx={cx}
                          cy={cy}
                          r={4}
                          fill={kit.gold || '#d4a017'}
                          stroke={kit.bone || '#fff'}
                          strokeWidth={2}
                        />
                      ) : (
                        <circle
                          key={`dot-${index}`}
                          cx={cx}
                          cy={cy}
                          r={2.5}
                          fill={kit.ink || '#333'}
                          opacity={0}
                        />
                      )
                    }}
                    activeDot={{
                      r: 5,
                      fill: kit.gold || '#d4a017',
                      stroke: kit.bone || '#fff',
                      strokeWidth: 2,
                    }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="mt-4 text-[13px] text-mute">{t('bol.competitorDetail.noTrendData')}</p>
          )}
          <p className="mt-2 font-mono text-[11px] tracking-[0.02em] text-mute">
            {t('bol.competitorDetail.trendCaption')}
          </p>
        </SectionBlock>

        {/* Shared buyers preview */}
        <SectionBlock
          heading={
            <span className="inline-flex items-baseline gap-2">
              {t('bol.competitorDetail.sharedPreviewHeading')}
              <span className="inline-flex items-center rounded-full border border-rule bg-bone px-2 py-0.5 font-mono text-[11px] text-mute">
                {competitor.overlapCount ?? 0}
              </span>
            </span>
          }
        >
          {shareList.length > 0 ? (
            <div className="mt-2 divide-y divide-rule">
              {shareList.map((c: any, i: number) => (
                <ShareRow
                  key={(c.key || c.company_name || c.companyName || i) + ''}
                  name={c.company_name || c.companyName || '—'}
                  country={c.country ?? c.companyAddressCountry ?? ''}
                  shipments={c.total_shipments_supplier ?? c.totalShipmentsSupplier ?? 0}
                  theirShare={c.shipments_percents_company ?? c.shipmentsPercentsCompany ?? 0}
                  isOverlap={!!c.isOverlap}
                  isNew={!!(c.is_new_company ?? c.isNewCompany)}
                  yourAccountLabel={t('bol.competitorDetail.yourAccount')}
                  newLabel={t('bol.competitorDetail.newBuyer')}
                />
              ))}
            </div>
          ) : (
            <p className="mt-4 text-[13px] text-mute">
              {t('bol.competitorDetail.noSharedOverlap')}
            </p>
          )}
        </SectionBlock>

        {/* Customer concentration */}
        {concentration && (
          <SectionBlock
            heading={
              <div className="flex items-baseline justify-between gap-3">
                <span>{t('bol.competitorDetail.customerConcentration')}</span>
                <span className="font-mono text-[12px] font-normal tracking-[0.02em] text-mute">
                  {t('bol.competitorDetail.concentrationWindow')}
                </span>
              </div>
            }
            noHeadingUpcase
          >
            <div className="mt-3 flex flex-col gap-3">
              <ConcentrationRow
                label={t('bol.competitorDetail.topBuyer')}
                value={
                  <span>
                    <span lang="en">{concentration.topBuyerName || concentration.top_buyer_name}</span>
                    <span className="mx-2 text-mute">·</span>
                    <span
                      className="tabular-nums"
                      style={{
                        color:
                          (concentration.topBuyerShare ?? concentration.top_buyer_share) > 40
                            ? 'var(--threat)'
                            : (concentration.topBuyerShare ?? concentration.top_buyer_share) > 25
                              ? 'var(--gold)'
                              : 'var(--accent)',
                      }}
                    >
                      {concentration.topBuyerShare ?? concentration.top_buyer_share}%
                    </span>
                  </span>
                }
              />
              <ConcentrationRow
                label={t('bol.competitorDetail.top3Share')}
                value={
                  <span className="tabular-nums" style={{ color: 'var(--gold)' }}>
                    {concentration.top3Share ?? concentration.top_3_share}%
                  </span>
                }
              />
              <ConcentrationRow
                label={t('bol.competitorDetail.activeBuyers')}
                value={
                  <span className="tabular-nums text-ink">
                    {concentration.totalActiveBuyers ?? concentration.total_active_buyers}
                  </span>
                }
              />
            </div>
          </SectionBlock>
        )}

        {/* Products */}
        {competitor.productDescriptions?.length > 0 && (
          <SectionBlock heading={t('bol.competitorDetail.productsHeading')} noHeadingUpcase>
            {competitor.specialization != null && competitor.specialization > 0 && (
              <p className="mt-2 font-mono text-[12.5px] tabular-nums tracking-[0.01em] text-mute">
                {t('bol.competitorDetail.specPrimary', { pct: competitor.specialization })}
              </p>
            )}
            <div className="mt-3 flex flex-wrap gap-1.5">
              {competitor.productDescriptions.slice(0, 5).map((p: string) => (
                <span
                  key={p}
                  className="inline-flex items-center rounded-full border border-rule bg-bone px-3 py-1 text-[12.5px] text-ink"
                  lang="en"
                >
                  {p}
                </span>
              ))}
            </div>
          </SectionBlock>
        )}
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------- helpers */

function SectionBlock({
  heading,
  action,
  children,
  noHeadingUpcase,
}: {
  heading: React.ReactNode
  action?: React.ReactNode
  children: React.ReactNode
  noHeadingUpcase?: boolean
}) {
  return (
    <section className="border-t border-rule pt-5">
      <div className="flex items-baseline justify-between gap-3">
        <h3
          className={
            noHeadingUpcase
              ? 'title-block'
              : 'font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-mute'
          }
        >
          {heading}
        </h3>
        {action && <div className="shrink-0">{action}</div>}
      </div>
      {children}
    </section>
  )
}

function KpiCard({
  label,
  value,
  sub,
  accent,
  threatBar,
}: {
  label: string
  value: React.ReactNode
  sub?: React.ReactNode
  accent?: 'gold'
  threatBar?: number
}) {
  return (
    <div className="flex min-h-[112px] flex-col justify-between rounded-xl border border-rule bg-bone p-5">
      <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-mute">
        {label}
      </span>
      <KpiValue
        accent={accent === 'gold' ? 'gold' : 'deep'}
        style={accent === 'gold' ? { color: 'var(--gold)' } : undefined}
      >
        {value}
      </KpiValue>
      {typeof threatBar === 'number' ? (
        <div className="flex items-center gap-2">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-fog">
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${Math.min(100, Math.max(0, threatBar))}%`,
                background: 'var(--threat)',
              }}
            />
          </div>
          <span className="font-mono text-[11px] tabular-nums text-mute">/ 100</span>
        </div>
      ) : sub ? (
        <span className="text-[12px] leading-[1.35] text-mute">{sub}</span>
      ) : (
        <span className="text-[12px] leading-[1.35] text-transparent select-none">.</span>
      )}
    </div>
  )
}

function Segmented<T extends string | number>({
  options,
  selected,
  onChange,
}: {
  options: { key: string; label: string; value: T }[]
  selected: T
  onChange: (v: T) => void
}) {
  return (
    <div className="inline-flex items-center rounded-md border border-rule bg-bone p-0.5">
      {options.map((o) => {
        const on = o.value === selected
        return (
          <button
            key={o.key}
            onClick={() => onChange(o.value)}
            className={
              on
                ? 'rounded-[5px] bg-cream px-2.5 py-1 font-mono text-[11px] tracking-[0.04em] text-deep'
                : 'rounded-[5px] px-2.5 py-1 font-mono text-[11px] tracking-[0.04em] text-mute hover:text-ink'
            }
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}

function initialsOf(name: string) {
  return name
    .split(/\s+/)
    .map((w) => w[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

function ShareRow({
  name,
  country,
  shipments,
  theirShare,
  isOverlap,
  isNew,
  yourAccountLabel,
  newLabel,
}: {
  name: string
  country: string
  shipments: number
  theirShare: number
  isOverlap: boolean
  isNew: boolean
  yourAccountLabel: string
  newLabel: string
}) {
  return (
    <div
      className={
        'group flex items-center gap-4 py-3' +
        (isOverlap ? ' -ml-4 border-l-2 border-l-accent pl-4' : '')
      }
    >
      <span
        className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-fog font-mono text-[11px] text-ink"
        aria-hidden="true"
      >
        {initialsOf(name)}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="truncate text-[14px] text-ink" lang="en" title={name}>
            {name}
          </span>
          {isOverlap && (
            <span
              className="inline-flex items-center rounded-full px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.08em]"
              style={{
                background: 'var(--accent-lo)',
                color: 'var(--accent)',
              }}
            >
              {yourAccountLabel}
            </span>
          )}
          {isNew && (
            <span className="inline-flex items-center rounded-full border border-rule bg-bone px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.08em] text-mute">
              {newLabel}
            </span>
          )}
        </div>
        {country && (
          <span className="font-mono text-[11px] tracking-[0.02em] text-mute" lang="en">
            {country}
          </span>
        )}
      </div>
      <div className="hidden min-w-[140px] text-right font-mono text-[12px] tabular-nums text-ink sm:block">
        {shipments.toLocaleString()}
        <span className="ml-1 text-mute">shipments</span>
      </div>
      {theirShare > 0 && (
        <div className="hidden w-[80px] text-right font-mono text-[12px] tabular-nums sm:block" style={{ color: 'var(--gold)' }}>
          {theirShare.toFixed(1)}%
        </div>
      )}
      <ChevronRight className="h-4 w-4 shrink-0 text-mute opacity-0 transition-opacity group-hover:opacity-100" />
    </div>
  )
}

function ConcentrationRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <span className="font-mono text-[12.5px] tracking-[0.01em] text-mute">{label}</span>
      <span className="text-right font-display text-[14px] text-ink">{value}</span>
    </div>
  )
}
