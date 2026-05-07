'use client'

import React from 'react'
import { ColumnDef } from '@tanstack/react-table'
import { useRouter } from '@/i18n/navigation'
import {
  Building,
  Mail,
  User,
  Radio,
  Layers,
  Activity,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { customerStageVariant, getVariant } from '@/lib/colors/status-mappings'
import { EditableCell, SortableHeader, createSelectColumn } from '@/components/ui/data-table'
import type { FieldConfig } from '@/components/ui/data-table'
import type { Customer } from '@/types/crm'

// Columns whose data values are English (company names, contacts, emails, etc.)
export const ENGLISH_DATA_COLUMNS = new Set(['company', 'contactName', 'email'])

export type CustomerFieldConfig = Record<string, FieldConfig>

export function buildCustomerFieldConfig(
  t: (key: string, ...args: any[]) => string
): CustomerFieldConfig {
  return {
    company: {
      type: 'text',
      label: t('columns.company'),
      icon: Building,
      required: true,
      validation: (value: any) => (value?.length >= 2 ? null : t('validation.companyRequired')),
    },
    contactName: {
      type: 'text',
      label: t('columns.contactName'),
      icon: User,
    },
    email: {
      type: 'text',
      label: t('columns.email'),
      icon: Mail,
      validation: (value: any) => {
        if (!value) return null
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) ? null : t('validation.emailInvalid')
      },
    },
    signal: {
      type: 'text',
      label: t('columns.signal'),
      icon: Radio,
      readonly: true,
    },
    stage: {
      type: 'select',
      label: t('columns.stage'),
      icon: Layers,
      options: [
        { value: 'new', label: t('stage.new') },
        { value: 'contacted', label: t('stage.contacted') },
        { value: 'replied', label: t('stage.replied') },
        { value: 'engaged', label: t('stage.engaged') },
        { value: 'quoting', label: t('stage.quoting') },
      ],
      renderDisplay: (value: any) => {
        const variant = getVariant(customerStageVariant, value)
        // We need the label — but renderDisplay only has the raw value.
        // Derive the label from the value key directly (the options labels are set at build time).
        return <Badge variant={variant}>{value}</Badge>
      },
    },
    lastActivity: {
      type: 'date',
      label: t('columns.lastActivity'),
      icon: Activity,
      readonly: true,
    },
  }
}

// Signal badge color mapping (used in signal column cell)
const signalColors: Record<string, { bg: string; text: string; border: string }> = {
  red: { bg: 'bg-threat-lo', text: 'text-threat', border: 'border-threat/30' },
  purple: { bg: 'bg-info-lo', text: 'text-info', border: 'border-info/30' },
  green: { bg: 'bg-accent-lo', text: 'text-accent', border: 'border-accent/30' },
  none: { bg: 'bg-paper', text: 'text-mute', border: 'border-rule' },
}

interface BuildCustomerColumnsOptions {
  t: (key: string, ...args: any[]) => string
  tc: (key: string, ...args: any[]) => string
  locale: string
  router: ReturnType<typeof useRouter>
  workspaceId: string
  fieldConfig: CustomerFieldConfig
}

export function buildCustomerColumns({
  t,
  tc,
  locale,
  router,
  workspaceId,
  fieldConfig,
}: BuildCustomerColumnsOptions): ColumnDef<Customer, any>[] {
  return [
    createSelectColumn<Customer>(),
    {
      accessorKey: 'company',
      header: ({ column }: any) => (
        <SortableHeader column={column} label={t('columns.company')} />
      ),
      cell: ({ row }: any) => {
        const customer = row.original
        return (
          <button
            onClick={(e) => {
              e.stopPropagation()
              if (customer.id) router.push(`/workspace/${workspaceId}/crm/${customer.id}`)
            }}
            className="truncate text-left text-sm font-medium text-deep underline decoration-rule underline-offset-2 hover:text-ink hover:decoration-mute"
          >
            {customer.company || '-'}
          </button>
        )
      },
      meta: {
        fieldConfig: fieldConfig.company,
        headerClassName: 'min-w-[180px] max-w-[250px]',
        cellClassName: 'max-w-[250px] h-14 align-middle',
      },
    },
    {
      id: 'contactName',
      accessorFn: (row: Customer) =>
        row.personnel?.[0]?.fullName || row.personnel?.[0]?.firstName || '',
      header: t('columns.contactName'),
      cell: EditableCell,
      meta: {
        fieldConfig: fieldConfig.contactName,
        headerClassName: 'min-w-[140px] max-w-[200px]',
        cellClassName: 'max-w-[200px] h-14 align-middle',
      },
    },
    {
      id: 'email',
      accessorFn: (row: Customer) => row.personnel?.[0]?.email || row.clientEmail || '',
      header: t('columns.email'),
      cell: EditableCell,
      meta: {
        fieldConfig: fieldConfig.email,
        headerClassName: 'min-w-[180px] max-w-[250px]',
        cellClassName: 'max-w-[250px] h-14 align-middle',
      },
    },
    {
      accessorKey: 'signal',
      header: t('columns.signal'),
      cell: ({ getValue }: any) => {
        const signal = getValue()
        if (!signal) return <div className="py-1 text-sm text-mute italic">—</div>
        const colors = signalColors[signal.level] || signalColors.green
        const signalKeyMap: Record<string, string> = {
          'respond now': 'respondNow',
          'quote requested': 'quoteRequested',
          'pricing question': 'pricingQuestion',
          'replied today': 'repliedToday',
          'high intent': 'highIntent',
          'deal room viewed': 'dealRoomViewed',
          'viewed multiple times': 'viewedMultiple',
          'shared internally': 'sharedInternally',
          opened: 'opened',
          'clicked email': 'clickedEmail',
          'asking about moq': 'askingMoq',
          'asking about lead time': 'askingLeadTime',
          'asking about samples': 'askingSamples',
          'import spike': 'importSpike',
          'reorder window': 'reorderWindow',
          'early research': 'earlyResearch',
          'buyer interested': 'buyerInterested',
          'buyer objection': 'buyerObjection',
          'buyer question': 'buyerQuestion',
          'not interested': 'notInterested',
        }
        const labelKey = signal.label ? signalKeyMap[signal.label.toLowerCase()] : undefined
        const displayLabel = labelKey ? t(`signal.${labelKey}` as any) : signal.label
        return (
          <div className="py-1">
            <span
              className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${colors.bg} ${colors.text} ${colors.border}`}
            >
              {displayLabel}
            </span>
          </div>
        )
      },
      enableSorting: false,
      meta: {
        fieldConfig: fieldConfig.signal,
        headerClassName: 'min-w-[120px] w-[160px]',
        cellClassName: 'w-[160px] h-14 align-middle',
      },
    },
    {
      accessorKey: 'stage',
      header: ({ column }: any) => (
        <SortableHeader column={column} label={t('columns.stage')} />
      ),
      cell: ({ getValue, row, column, table }: any) => {
        // Use shared EditableCell but wrap display with Badge via renderDisplay in fieldConfig
        return <EditableCell getValue={getValue} row={row} column={column} table={table} />
      },
      meta: {
        fieldConfig: {
          ...fieldConfig.stage,
          renderDisplay: (value: any) => {
            const validStages = ['new', 'contacted', 'replied', 'engaged', 'quoting']
            const key = String(value).toLowerCase().replace(/[\s]+/g, '')
            const label = validStages.includes(key)
              ? t(`stage.${key}` as any)
              : value
            const variant = getVariant(customerStageVariant, value)
            return <Badge variant={variant}>{label}</Badge>
          },
        },
        headerClassName: 'min-w-[100px] w-[130px]',
        cellClassName: 'w-[130px] h-14 align-middle',
      },
    },
    {
      accessorKey: 'lastActivity',
      header: ({ column }: any) => (
        <SortableHeader column={column} label={t('columns.lastActivity')} />
      ),
      cell: ({ getValue }: any) => {
        const value = getValue()
        if (!value) return <div className="py-1 text-sm text-mute italic">—</div>
        const date = new Date(value)
        const now = new Date()
        const diffMs = now.getTime() - date.getTime()
        const diffMins = Math.floor(diffMs / 60000)
        const diffHours = Math.floor(diffMs / 3600000)
        const diffDays = Math.floor(diffMs / 86400000)
        let display: string
        if (diffMins < 60) display = t('dealRoomsList.minsAgo', { count: diffMins })
        else if (diffHours < 24) display = t('dealRoomsList.hoursAgo', { count: diffHours })
        else if (diffDays < 7) display = t('dealRoomsList.daysAgo', { count: diffDays })
        else display = date.toLocaleDateString(locale)
        return (
          <div className="py-1 text-sm text-ink" title={date.toLocaleString(locale)}>
            {display}
          </div>
        )
      },
      meta: {
        fieldConfig: fieldConfig.lastActivity,
        headerClassName: 'min-w-[100px] w-[120px]',
        cellClassName: 'w-[120px] h-14 align-middle',
      },
    },
  ]
}
