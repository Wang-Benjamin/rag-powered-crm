'use client'

import React from 'react'
import { ColumnDef } from '@tanstack/react-table'
import { useRouter } from '@/i18n/navigation'
import { Building, MapPin, AlertCircle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { leadStatusVariant, getVariant, formatStatusLabel } from '@/lib/colors/status-mappings'
import { EditableCell, SortableHeader, createSelectColumn } from '@/components/ui/data-table'
import type { FieldConfig } from '@/components/ui/data-table'
import type { Lead } from '@/types/leads'

// Columns whose data values are English (company names, emails, locations, etc.)
export const ENGLISH_DATA_COLUMNS = new Set(['company', 'location', 'website'])

// Compact 56px row — tighter than Buyers.html's 64px spec per product preference.
// NOTE: every numeric column is intentionally LEFT-aligned, overriding Buyers.html's
// .num right-align — this is a deliberate product preference.
const CELL = 'h-14 align-middle'

export type LeadFieldConfig = Record<string, FieldConfig>

export function buildLeadFieldConfig(
  t: (key: string, ...args: any[]) => string
): LeadFieldConfig {
  return {
    company: {
      type: 'text',
      label: t('leadColumns.company'),
      icon: Building,
      required: true,
      validation: (value: any) => (value?.length >= 2 ? null : t('validation.companyRequired')),
    },
    location: {
      type: 'text',
      label: t('leadColumns.location'),
      icon: MapPin,
    },
    industry: {
      type: 'text',
      label: t('leadColumns.industry'),
    },
    website: {
      type: 'text',
      label: t('leadColumns.website'),
    },
    status: {
      type: 'select',
      label: t('leadColumns.status'),
      required: true,
      options: [
        { value: 'new', label: t('status.new') },
        { value: 'synced_to_crm', label: t('status.synced_to_crm') },
        { value: 'qualified', label: t('status.qualified') },
        { value: 'not_interested', label: t('status.not_interested') },
      ],
      renderDisplay: (value: any) => {
        const key = String(value).toLowerCase().replace(/[\s]+/g, '_')
        const validKeys = ['new', 'synced_to_crm', 'qualified', 'not_interested']
        const label = validKeys.includes(key) ? t(`status.${key}` as any) : formatStatusLabel(value)
        const variant = getVariant(leadStatusVariant, value)
        return <Badge variant={variant}>{label}</Badge>
      },
    },
    shipmentVolume: {
      type: 'number',
      label: t('leadColumns.shipmentVolume'),
      readonly: true,
    },
    supplierCount: {
      type: 'number',
      label: t('leadColumns.supplierCount'),
      readonly: true,
    },
    lastShipment: {
      type: 'number',
      label: t('leadColumns.lastShipment'),
      readonly: true,
    },
    trend: {
      type: 'number',
      label: t('leadColumns.trend'),
      readonly: true,
    },
    score: {
      type: 'number',
      label: t('leadColumns.score'),
      readonly: true,
    },
  }
}

// Resolve filterable value for computed columns (used in useTableFiltering's getFilterValue)
export function getLeadFilterValue(lead: Lead, columnId: string): any {
  switch (columnId) {
    case 'shipmentVolume': {
      const total = lead.importContext?.totalShipments
      return total != null ? Math.round(total / 15) : null
    }
    case 'supplierCount': {
      const suppliers = (lead.supplierContext as any)?.suppliers
      if (suppliers?.length) {
        const active = suppliers.filter((s: any) => s.shipments12M > 0).length
        return active > 0 ? active : suppliers.length
      }
      return lead.importContext?.totalSuppliers ?? null
    }
    case 'lastShipment': {
      const dateStr = lead.importContext?.mostRecentShipment
      if (!dateStr) return null
      const parts = dateStr.split('/')
      if (parts.length !== 3) return null
      const shipDate = new Date(+parts[2], +parts[1] - 1, +parts[0])
      return Math.round((Date.now() - shipDate.getTime()) / (1000 * 60 * 60 * 24))
    }
    case 'trend': {
      const sups = (lead.supplierContext as any)?.suppliers
      if (!sups?.length) return null
      const active = sups.filter((s: any) => s.shipments12M > 0 || s.shipments1224M > 0)
      if (!active.length) return null
      const totalShare = active.reduce((sum: number, s: any) => sum + (s.share || 0), 0)
      if (totalShare === 0) return null
      return Math.round(
        active.reduce(
          (sum: number, s: any) => sum + (s.trend || 0) * ((s.share || 0) / totalShare),
          0
        )
      )
    }
    default:
      return (lead as any)[columnId]
  }
}

interface BuildLeadColumnsOptions {
  t: (key: string, ...args: any[]) => string
  router: ReturnType<typeof useRouter>
  workspaceId: string
  fieldConfig: LeadFieldConfig
  showBuyerEmails?: boolean
}

export function buildLeadColumns({
  t,
  router,
  workspaceId,
  fieldConfig,
  showBuyerEmails = true,
}: BuildLeadColumnsOptions): ColumnDef<Lead, any>[] {
  return [
    createSelectColumn<Lead>(),
    {
      accessorKey: 'company',
      header: ({ column }: any) => (
        <SortableHeader column={column} label={t('leadColumns.company')} />
      ),
      cell: ({ row }: any) => {
        const lead = row.original
        return (
          <div className="flex min-w-0 flex-col gap-[2px]">
            <span className="truncate text-[13.5px] font-medium leading-[1.2] text-deep">
              {lead.company}
            </span>
            {lead.location && (
              <span className="truncate text-[12.5px] leading-[1.2] text-mute">
                {lead.location}
              </span>
            )}
          </div>
        )
      },
      meta: {
        fieldConfig: fieldConfig.company,
        headerClassName: 'min-w-[200px] max-w-[320px]',
        cellClassName: `${CELL} max-w-[320px]`,
      },
    },
    {
      id: 'shipmentVolume',
      header: ({ column }: any) => (
        <SortableHeader column={column} label={t('leadColumns.shipmentVolume')} />
      ),
      accessorFn: (row: Lead) => row.importContext?.totalShipments ?? null,
      cell: ({ row }: any) => {
        const total = row.original.importContext?.totalShipments
        if (!total) {
          return <span className="text-[12.5px] text-mute">{t('leadColumns.noData')}</span>
        }
        const containers = Math.round(total / 15)
        return (
          <span className="whitespace-nowrap font-mono text-[12.5px] text-ink tabular-nums">
            {t('leadColumns.containers', { count: containers })}
          </span>
        )
      },
      sortingFn: 'basic',
      meta: {
        fieldConfig: fieldConfig.shipmentVolume,
        headerClassName: 'min-w-[130px] w-[150px]',
        cellClassName: `${CELL} w-[150px]`,
      },
    },
    {
      id: 'supplierCount',
      header: t('leadColumns.supplierCount'),
      accessorFn: (row: Lead) => {
        const suppliers = (row.supplierContext as any)?.suppliers
        if (suppliers?.length) {
          const active = suppliers.filter((s: any) => s.shipments12M > 0).length
          return active > 0 ? active : suppliers.length
        }
        return row.importContext?.totalSuppliers ?? null
      },
      cell: ({ row }: any) => {
        const suppliers = (row.original.supplierContext as any)?.suppliers
        if (suppliers?.length) {
          const activeCount = suppliers.filter((s: any) => s.shipments12M > 0).length
          return (
            <span className="font-mono text-[12.5px] text-ink tabular-nums">
              {activeCount > 0 ? activeCount : suppliers.length}
            </span>
          )
        }
        const total = row.original.importContext?.totalSuppliers
        if (total) {
          return (
            <span className="font-mono text-[12.5px] text-ink tabular-nums">{total}</span>
          )
        }
        return <span className="text-[12.5px] text-mute">{t('leadColumns.noData')}</span>
      },
      sortingFn: 'basic',
      meta: {
        fieldConfig: fieldConfig.supplierCount,
        headerClassName: 'min-w-[110px] w-[120px]',
        cellClassName: `${CELL} w-[120px]`,
      },
    },
    {
      id: 'lastShipment',
      header: ({ column }: any) => (
        <SortableHeader column={column} label={t('leadColumns.lastShipment')} />
      ),
      accessorFn: (row: Lead) => {
        const dateStr = row.importContext?.mostRecentShipment
        if (!dateStr) return null
        const parts = dateStr.split('/')
        if (parts.length === 3) return new Date(+parts[2], +parts[1] - 1, +parts[0]).getTime()
        return null
      },
      cell: ({ row }: any) => {
        const dateStr = row.original.importContext?.mostRecentShipment
        if (!dateStr) {
          return (
            <span className="text-[12px] italic text-mute/60">
              {row.original.importContext ? t('leadColumns.noData') : t('leadColumns.pendingEnrichment')}
            </span>
          )
        }
        const parts = dateStr.split('/')
        if (parts.length !== 3) return <span className="text-[12px] text-mute">{dateStr}</span>
        const shipDate = new Date(+parts[2], +parts[1] - 1, +parts[0])
        const daysAgo = Math.round((Date.now() - shipDate.getTime()) / (1000 * 60 * 60 * 24))
        const isStale = daysAgo > 60
        return (
          <span
            className={`inline-flex items-center gap-1 whitespace-nowrap font-mono text-[12px] tabular-nums ${isStale ? 'text-gold' : 'text-ink'}`}
          >
            {isStale && <AlertCircle className="h-[11px] w-[11px]" />}
            {t('leadColumns.daysAgo', { count: daysAgo })}
          </span>
        )
      },
      sortingFn: 'basic',
      meta: {
        fieldConfig: fieldConfig.lastShipment,
        headerClassName: 'min-w-[110px] w-[120px]',
        cellClassName: `${CELL} w-[120px]`,
      },
    },
    {
      id: 'trend',
      header: t('leadColumns.trend'),
      accessorFn: (row: Lead) => {
        const suppliers = (row.supplierContext as any)?.suppliers
        if (!suppliers?.length) return null
        const active = suppliers.filter((s: any) => s.shipments12M > 0 || s.shipments1224M > 0)
        if (!active.length) return null
        const totalShare = active.reduce((sum: number, s: any) => sum + (s.share || 0), 0)
        if (totalShare === 0) return null
        return active.reduce(
          (sum: number, s: any) => sum + (s.trend || 0) * ((s.share || 0) / totalShare),
          0
        )
      },
      cell: ({ row }: any) => {
        const suppliers = (row.original.supplierContext as any)?.suppliers
        if (!suppliers?.length) {
          return (
            <span className="text-[12px] italic text-mute/60">
              {row.original.supplierContext ? t('leadColumns.noData') : t('leadColumns.pendingEnrichment')}
            </span>
          )
        }
        const active = suppliers.filter((s: any) => s.shipments12M > 0 || s.shipments1224M > 0)
        if (!active.length) {
          return <span className="text-[12px] text-mute">{t('leadColumns.noData')}</span>
        }
        const totalShare = active.reduce((sum: number, s: any) => sum + (s.share || 0), 0)
        if (totalShare === 0) {
          return <span className="text-[12px] text-mute">{t('leadColumns.noData')}</span>
        }
        const weightedTrend = active.reduce(
          (sum: number, s: any) => sum + (s.trend || 0) * ((s.share || 0) / totalShare),
          0
        )
        const rounded = Math.round(weightedTrend)
        if (rounded === 0) {
          return <span className="font-mono text-[12.5px] text-mute tabular-nums">→ 0%</span>
        }
        const isUp = rounded > 0
        // Signal system (DESIGN.md §2): up = accent for growth, down = mute (the minus
        // sign carries the negative — no alarm red).
        return (
          <span
            className={`whitespace-nowrap font-mono text-[12.5px] tabular-nums ${isUp ? 'text-accent' : 'text-mute'}`}
          >
            {isUp ? '↗ +' : '↘ −'}
            {Math.abs(rounded)}%
          </span>
        )
      },
      sortingFn: 'basic',
      meta: {
        fieldConfig: fieldConfig.trend,
        headerClassName: 'min-w-[90px] w-[100px]',
        cellClassName: `${CELL} w-[100px]`,
      },
    },
    {
      accessorKey: 'score',
      header: ({ column }: any) => (
        <SortableHeader column={column} label={t('leadColumns.score')} />
      ),
      cell: ({ row }: any) => {
        const score = row.original.score
        const condensed = row.original.bolDetailContext?.aiInsightCondensed
        if (score == null) {
          return <span className="text-[12.5px] text-mute">{t('leadColumns.noData')}</span>
        }
        const tierClass =
          score >= 80 ? 'text-accent' : score >= 60 ? 'text-gold' : 'text-mute'
        return (
          <div className="flex max-w-[220px] min-w-0 flex-col leading-[1.2]">
            <span
              className={`font-mono text-[15px] font-medium leading-none tabular-nums ${tierClass}`}
            >
              {score}
            </span>
            {condensed && (
              <span className="mt-1 line-clamp-2 text-[11.5px] leading-[1.3] text-mute">
                {condensed}
              </span>
            )}
          </div>
        )
      },
      meta: {
        fieldConfig: fieldConfig.score,
        headerClassName: 'min-w-[160px] w-[220px]',
        cellClassName: `${CELL} w-[220px]`,
      },
    },
    {
      accessorKey: 'status',
      header: t('leadColumns.status'),
      cell: ({ getValue, row, column, table }: any) => (
        <EditableCell getValue={getValue} row={row} column={column} table={table} />
      ),
      meta: {
        fieldConfig: {
          ...fieldConfig.status,
          renderDisplay: (value: any) => {
            const key = String(value).toLowerCase().replace(/[\s]+/g, '_')
            const validKeys = ['new', 'synced_to_crm', 'qualified', 'not_interested']
            const label = validKeys.includes(key)
              ? t(`status.${key}` as any)
              : formatStatusLabel(value)
            const variant = getVariant(leadStatusVariant, value)
            return <Badge variant={variant}>{label}</Badge>
          },
        },
        headerClassName: 'min-w-[100px] w-[120px]',
        cellClassName: `${CELL} w-[120px]`,
      },
    },
  ]
}
