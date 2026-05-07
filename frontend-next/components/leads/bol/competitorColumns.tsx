'use client'

import React from 'react'
import { ColumnDef } from '@tanstack/react-table'
import { useTranslations } from 'next-intl'
import Tooltip from '@/components/ui/tooltip'
import { SortableHeader } from '@/components/ui/data-table'
import { THREAT_DESCRIPTION_KEYS, THREAT_LEVEL_KEYS } from './bol-shared'
import type { Competitor, ThreatLevel } from '@/types/leads/bol'

// Competitors render at 56px rows to match the compact Buyers density.
// All cells are left-aligned per product preference, overriding Competitors.html's
// .num right-align.
const CELL = 'h-14 align-middle'

// Threat chip — inverted for competitors: gold = threat (to us), accent = opportunity
// (for us). Kit-native styling, not via Badge variants.
const THREAT_CHIP: Record<ThreatLevel, string> = {
  HIGH: 'bg-gold-lo text-gold border-gold/40',
  GROWING: 'bg-gold-lo text-gold border-gold/40',
  MODERATE: 'bg-bone text-ink border-rule',
  LOW: 'bg-cream text-mute border-rule',
  DECLINING: 'bg-accent-lo text-accent-hi border-accent/30',
}

export function buildCompetitorColumns(
  t: ReturnType<typeof useTranslations<'leads'>>
): ColumnDef<Competitor, any>[] {
  return [
    // 1. Competitor — always two lines: {CJK or Latin name} / {Latin alias · Location}.
    // Mirrors the Buyers company cell so row heights stay uniform across mixed
    // CJK/Latin tenants. Replaces the separate Location column.
    {
      accessorKey: 'supplierName',
      header: ({ column }) => (
        <SortableHeader column={column} label={t('bol.competitors.columnCompetitor')} />
      ),
      cell: ({ row }) => {
        const c = row.original
        const primary = c.supplierNameCn || c.supplierName
        const latinAlias = c.supplierNameCn ? c.supplierName : null
        const locationLabel = c.city
          ? `${c.city}, ${c.country}`
          : c.country || c.countryCode || ''
        const secondaryParts = [latinAlias, locationLabel].filter(Boolean) as string[]
        const secondary = secondaryParts.join(' · ')
        return (
          <div className="flex min-w-0 flex-col gap-[2px]">
            <span
              className="truncate text-[13.5px] font-medium leading-[1.2] text-deep"
              title={primary}
            >
              {primary}
            </span>
            {secondary && (
              <span
                className="truncate text-[12.5px] leading-[1.2] text-mute"
                title={secondary}
              >
                {secondary}
              </span>
            )}
          </div>
        )
      },
      meta: {
        headerClassName: 'min-w-[260px] max-w-[360px]',
        cellClassName: `${CELL} max-w-[360px]`,
      },
    },

    // 2. HS overlap — first N codes + "+N" pill for overflow
    {
      id: 'hsCodes',
      header: ({ column }) => (
        <SortableHeader column={column} label={t('bol.competitorDrawer.hsCodes')} />
      ),
      accessorFn: (row: Competitor) => row.hsCodes?.length ?? 0,
      cell: ({ row }) => {
        const codes = row.original.hsCodes || []
        if (!codes.length) return <span className="text-[12px] text-mute">{'—'}</span>
        const visible = codes.slice(0, 2)
        const extra = codes.length - visible.length
        return (
          <span className="inline-flex items-center gap-1.5 font-mono text-[11.5px] tabular-nums text-ink">
            <span className="truncate">{visible.join(', ')}</span>
            {extra > 0 && (
              <span className="inline-flex h-[18px] items-center rounded-full border border-rule bg-bone px-1.5 text-[10.5px] text-mute">
                +{extra}
              </span>
            )}
          </span>
        )
      },
      sortingFn: 'basic',
      meta: {
        headerClassName: 'min-w-[170px] w-[200px]',
        cellClassName: `${CELL} w-[200px]`,
      },
    },

    // 3. Shared buyers — ratio {overlap} / {their-total-buyers}
    {
      accessorKey: 'overlapCount',
      header: ({ column }) => (
        <SortableHeader column={column} label={t('bol.competitors.columnOverlap')} />
      ),
      cell: ({ row }) => {
        const c = row.original
        const hasTotal = c.totalCustomers != null && c.totalCustomers > 0
        const tooltipContent =
          c.customerCompanies?.length > 0
            ? c.customerCompanies.slice(0, 5).join(', ') +
              (c.customerCompanies.length > 5 ? ` +${c.customerCompanies.length - 5} more` : '')
            : ''
        const body = (
          <span className="inline-flex items-baseline font-mono text-[12.5px] tabular-nums">
            <span className="font-medium text-ink">{c.overlapCount}</span>
            {hasTotal && (
              <>
                <span className="mx-[2px] text-mute">/</span>
                <span className="text-mute">{c.totalCustomers}</span>
              </>
            )}
          </span>
        )
        if (tooltipContent) {
          return (
            <Tooltip content={tooltipContent} position="top" showIcon={false}>
              <span className="cursor-help border-b border-dotted border-rule">{body}</span>
            </Tooltip>
          )
        }
        return body
      },
      sortingFn: 'basic',
      meta: {
        headerClassName: 'min-w-[100px] w-[110px]',
        cellClassName: `${CELL} w-[110px]`,
      },
    },

    // 4. Trend — INVERTED for competitor context:
    //    up = gold (threat), down = accent (opportunity), flat = mute.
    //    See DESIGN.md §2 signal mapping "Competitor growing/declining" rows.
    {
      accessorKey: 'trendYoy',
      header: ({ column }) => (
        <SortableHeader column={column} label={t('bol.competitors.columnTrend')} />
      ),
      cell: ({ getValue }) => {
        const value = getValue() as number | null | undefined
        if (value == null) {
          return <span className="font-mono text-[12.5px] text-mute">{'—'}</span>
        }
        const rounded = Math.round(value)
        if (rounded === 0) {
          return <span className="font-mono text-[12.5px] text-mute tabular-nums">→ 0%</span>
        }
        const isUp = rounded > 0
        return (
          <span
            className={`whitespace-nowrap font-mono text-[12.5px] tabular-nums ${isUp ? 'text-gold' : 'text-accent'}`}
          >
            {isUp ? '↗ +' : '↘ −'}
            {Math.abs(rounded)}%
          </span>
        )
      },
      sortingFn: 'basic',
      meta: {
        headerClassName: 'min-w-[100px] w-[110px]',
        cellClassName: `${CELL} w-[110px]`,
      },
    },

    // 5. Volume — matchingShipments (kept from current schema; list-level data)
    {
      accessorKey: 'matchingShipments',
      header: ({ column }) => (
        <SortableHeader column={column} label={t('bol.competitors.columnVolume')} />
      ),
      cell: ({ row }) => {
        const c = row.original
        const matching = c.matchingShipments ?? null
        if (matching == null) {
          return <span className="font-mono text-[12.5px] text-mute">{'—'}</span>
        }
        const total = c.totalShipments ?? null
        return (
          <span className="font-mono text-[12.5px] text-ink tabular-nums">
            ~{matching.toLocaleString()}
            {total !== null && total > 0 && total !== matching && (
              <span className="ml-1 text-[11px] text-mute">
                / {total.toLocaleString()}
              </span>
            )}
          </span>
        )
      },
      sortingFn: 'basic',
      meta: {
        headerClassName: 'min-w-[120px] w-[140px]',
        cellClassName: `${CELL} w-[140px]`,
      },
    },

    // 6. Threat — kit-native chip (no Badge variants), semantics inverted per
    //    DESIGN.md signal mapping (DECLINING = opportunity for us = accent).
    {
      accessorKey: 'threatScore',
      header: ({ column }) => (
        <SortableHeader column={column} label={t('bol.competitors.columnThreat')} />
      ),
      cell: ({ row }) => {
        const threat = (row.original.threatLevel || 'LOW') as ThreatLevel
        const chipClass = THREAT_CHIP[threat]
        return (
          <Tooltip
            content={t(THREAT_DESCRIPTION_KEYS[threat])}
            position="left"
            showIcon={false}
          >
            <span
              className={`inline-flex h-[22px] items-center rounded-full border px-2.5 text-[11.5px] font-medium leading-none ${chipClass}`}
            >
              {t(THREAT_LEVEL_KEYS[threat])}
            </span>
          </Tooltip>
        )
      },
      sortingFn: 'basic',
      meta: {
        headerClassName: 'min-w-[90px] w-[100px]',
        cellClassName: `${CELL} w-[100px]`,
      },
    },
  ]
}
