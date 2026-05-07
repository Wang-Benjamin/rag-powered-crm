'use client'

import React from 'react'
import { ColumnDef } from '@tanstack/react-table'
import { useRouter } from '@/i18n/navigation'
import {
  Building,
  Building2,
  DollarSign,
  FileText,
  TrendingUp,
  Calendar,
  User,
  Clock,
  Eye,
  Briefcase,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { dealStageVariant, getVariant, formatStatusLabel } from '@/lib/colors/status-mappings'
import { EditableCell, SortableHeader, createSelectColumn } from '@/components/ui/data-table'
import type { FieldConfig } from '@/components/ui/data-table'
import type { Deal, Employee, Customer } from '@/types/crm'

// Columns whose data values are English (deal names, client names, descriptions, etc.)
export const ENGLISH_DATA_COLUMNS = new Set(['dealName', 'clientName', 'valueUsd', 'description'])

export type DealFieldConfig = Record<string, FieldConfig>

export function buildDealFieldConfig(
  t: (key: string, ...args: any[]) => string,
  employees?: Employee[],
  customers?: Customer[]
): DealFieldConfig {
  return {
    dealName: {
      type: 'text',
      label: t('dealColumns.dealName'),
      icon: Building,
      required: true,
      validation: (value: any) => (value?.length >= 2 ? null : t('dealValidation.nameRequired')),
    },
    description: {
      type: 'textarea' as any,
      label: t('dealColumns.description'),
      icon: FileText,
      validation: (value: any) =>
        value?.length >= 5 ? null : t('dealValidation.descriptionMinLength'),
    },
    valueUsd: {
      type: 'currency',
      label: t('dealColumns.value'),
      icon: DollarSign,
      readonly: true,
    },
    fobPrice: {
      type: 'currency',
      label: t('dealColumns.fobPrice'),
      icon: DollarSign,
      validation: (value: any) => {
        if (value === null || value === undefined || value === '') return null
        const num = parseFloat(value)
        return isNaN(num) || num < 0 ? t('dealValidation.mustBePositive') : null
      },
    },
    landedPrice: {
      type: 'currency',
      label: t('dealColumns.landedPrice'),
      icon: DollarSign,
      validation: (value: any) => {
        if (value === null || value === undefined || value === '') return null
        const num = parseFloat(value)
        return isNaN(num) || num < 0 ? t('dealValidation.mustBePositive') : null
      },
    },
    quantity: {
      type: 'number',
      label: t('dealColumns.quantity'),
      icon: Briefcase,
      validation: (value: any) => {
        if (value === null || value === undefined || value === '') return null
        const num = parseInt(value)
        return isNaN(num) || num < 0 ? t('dealValidation.mustBePositive') : null
      },
    },
    moq: {
      type: 'number',
      label: t('dealColumns.moq'),
      icon: Briefcase,
      validation: (value: any) => {
        if (value === null || value === undefined || value === '') return null
        const num = parseInt(value)
        return isNaN(num) || num < 0 ? t('dealValidation.mustBePositive') : null
      },
    },
    viewCount: {
      type: 'number',
      label: t('dealColumns.views'),
      icon: Eye,
      readonly: true,
    },
    roomStatus: {
      type: 'select',
      label: t('dealColumns.roomStatus'),
      icon: TrendingUp,
      options: [
        { value: 'draft', label: t('dealStages.draft') },
        { value: 'sent', label: t('dealStages.sent') },
        { value: 'viewed', label: t('dealStages.viewed') },
        { value: 'quote_requested', label: t('dealStages.quoteRequested') },
        { value: 'closed-won', label: t('dealStages.closedWon') },
        { value: 'closed-lost', label: t('dealStages.closedLost') },
      ],
      renderDisplay: (value: any) => {
        const stageKeyMap: Record<string, string> = {
          draft: 'draft',
          sent: 'sent',
          viewed: 'viewed',
          quote_requested: 'quoteRequested',
          'closed-won': 'closedWon',
          'closed-lost': 'closedLost',
        }
        const key = stageKeyMap[value]
        const label = key ? t(`dealStages.${key}` as any) : formatStatusLabel(value)
        return <Badge variant={getVariant(dealStageVariant, value)}>{label}</Badge>
      },
    },
    expectedCloseDate: {
      type: 'date',
      label: t('dealColumns.expectedCloseDate'),
      icon: Calendar,
    },
    createdAt: {
      type: 'date',
      label: t('dealColumns.startedTime'),
      icon: Clock,
      readonly: true,
    },
    salesmanName: {
      type: 'select',
      label: t('dealColumns.assignedSalesman'),
      icon: User,
      required: false,
      options:
        employees?.map((emp) => ({
          value: emp.employeeId ?? 0,
          label:
            emp.name ||
            `${emp.firstName || ''} ${emp.lastName || ''}`.trim() ||
            `Employee ${emp.employeeId}`,
        })) || [],
    },
    clientName: {
      type: 'select',
      label: t('dealColumns.client'),
      icon: Building2,
      required: true,
      options:
        customers?.map((c) => ({
          value: (c.id || c.clientId) ?? 0,
          label: c.company || c.name || '',
        })) || [],
    },
  }
}

interface BuildDealColumnsOptions {
  t: (key: string, ...args: any[]) => string
  router: ReturnType<typeof useRouter>
  workspaceId: string
  fieldConfig: DealFieldConfig
}

export function buildDealColumns({
  t,
  router,
  workspaceId,
  fieldConfig,
}: BuildDealColumnsOptions): ColumnDef<Deal, any>[] {
  return [
    createSelectColumn<Deal>(),
    {
      accessorKey: 'dealName',
      header: ({ column }: any) => (
        <SortableHeader column={column} label={t('dealColumns.dealName')} />
      ),
      cell: ({ row }: any) => {
        const deal = row.original
        const id = deal.dealId ?? deal.id
        return (
          <button
            onClick={(e) => {
              e.stopPropagation()
              if (id) router.push(`/workspace/${workspaceId}/deals/${id}`)
            }}
            className="truncate text-left text-sm font-medium text-deep underline decoration-rule underline-offset-2 hover:text-ink hover:decoration-mute"
          >
            {deal.dealName || '-'}
          </button>
        )
      },
      meta: {
        fieldConfig: fieldConfig.dealName,
        headerClassName: 'min-w-[180px] max-w-[250px]',
        cellClassName: 'max-w-[250px] h-14 align-middle',
      },
    },
    {
      accessorKey: 'description',
      header: t('dealColumns.description'),
      cell: EditableCell,
      meta: {
        fieldConfig: fieldConfig.description,
        headerClassName: 'min-w-[150px] max-w-[280px]',
        cellClassName: 'max-w-[280px] h-14 align-middle',
      },
    },
    {
      accessorKey: 'valueUsd',
      header: ({ column }: any) => (
        <SortableHeader column={column} label={t('dealColumns.value')} />
      ),
      cell: EditableCell,
      meta: {
        fieldConfig: fieldConfig.valueUsd,
        headerClassName: 'min-w-[120px] max-w-[150px]',
        cellClassName: 'max-w-[150px] h-14 align-middle font-mono tabular-nums',
      },
    },
    {
      accessorKey: 'fobPrice',
      header: ({ column }: any) => (
        <SortableHeader column={column} label={t('dealColumns.fobPrice')} />
      ),
      cell: EditableCell,
      meta: {
        fieldConfig: fieldConfig.fobPrice,
        headerClassName: 'min-w-[120px] max-w-[150px]',
        cellClassName: 'max-w-[150px] h-14 align-middle font-mono tabular-nums',
      },
    },
    {
      accessorKey: 'landedPrice',
      header: ({ column }: any) => (
        <SortableHeader column={column} label={t('dealColumns.landedPrice')} />
      ),
      cell: EditableCell,
      meta: {
        fieldConfig: fieldConfig.landedPrice,
        headerClassName: 'min-w-[120px] max-w-[150px]',
        cellClassName: 'max-w-[150px] h-14 align-middle font-mono tabular-nums',
      },
    },
    {
      accessorKey: 'quantity',
      header: t('dealColumns.quantity'),
      cell: EditableCell,
      meta: {
        fieldConfig: fieldConfig.quantity,
        headerClassName: 'min-w-[100px] max-w-[130px]',
        cellClassName: 'max-w-[130px] h-14 align-middle font-mono tabular-nums',
      },
    },
    {
      accessorKey: 'moq',
      header: t('dealColumns.moq'),
      cell: EditableCell,
      meta: {
        fieldConfig: fieldConfig.moq,
        headerClassName: 'min-w-[100px] max-w-[130px]',
        cellClassName: 'max-w-[130px] h-14 align-middle font-mono tabular-nums',
      },
    },
    {
      accessorKey: 'viewCount',
      header: ({ column }: any) => (
        <SortableHeader column={column} label={t('dealColumns.views')} />
      ),
      cell: ({ getValue, row }: any) => (
        <button
          onClick={(e) => {
            e.stopPropagation()
            const rid = row.original.dealId ?? row.original.id
            if (rid) router.push(`/workspace/${workspaceId}/deals/${rid}?tab=dealroom`)
          }}
          className="flex items-center gap-1.5 text-mute transition-colors hover:text-deep"
        >
          <Eye className="h-3.5 w-3.5" />
          <span className="font-mono tabular-nums">{getValue() ?? 0}</span>
        </button>
      ),
      meta: {
        fieldConfig: fieldConfig.viewCount,
        headerClassName: 'min-w-[80px] w-[100px]',
        cellClassName: 'w-[100px] h-14 align-middle',
      },
    },
    {
      accessorKey: 'roomStatus',
      header: t('dealColumns.roomStatus'),
      cell: ({ getValue, row, column, table }: any) => (
        <EditableCell getValue={getValue} row={row} column={column} table={table} />
      ),
      meta: {
        fieldConfig: fieldConfig.roomStatus,
        headerClassName: 'min-w-[100px] w-[120px]',
        cellClassName: 'w-[120px] h-14 align-middle',
      },
    },
    {
      accessorKey: 'expectedCloseDate',
      header: t('dealColumns.expectedCloseDate'),
      cell: EditableCell,
      meta: {
        fieldConfig: fieldConfig.expectedCloseDate,
        headerClassName: 'min-w-[140px] max-w-[180px]',
        cellClassName: 'max-w-[180px] h-14 align-middle',
      },
    },
    {
      accessorKey: 'salesmanName',
      header: t('dealColumns.assignedSalesman'),
      cell: EditableCell,
      meta: {
        fieldConfig: fieldConfig.salesmanName,
        headerClassName: 'min-w-[150px] max-w-[200px]',
        cellClassName: 'max-w-[200px] h-14 align-middle',
      },
    },
    {
      accessorKey: 'clientName',
      header: t('dealColumns.client'),
      cell: EditableCell,
      meta: {
        fieldConfig: fieldConfig.clientName,
        headerClassName: 'min-w-[150px] max-w-[200px]',
        cellClassName: 'max-w-[200px] h-14 align-middle',
      },
    },
  ]
}
