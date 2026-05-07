'use client'

import React, { useMemo } from 'react'
import { useTranslations } from 'next-intl'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  SortingState,
} from '@tanstack/react-table'
import { Shield } from 'lucide-react'
import { EmptyState } from '@/components/ui/states/EmptyState'
import { DataTable, DataTablePagination } from '@/components/ui/data-table'
import { buildCompetitorColumns } from './competitorColumns'
import type { Competitor } from '@/types/leads/bol'

const COMPETITORS_PER_PAGE = 10

interface CompetitorTableProps {
  competitors: Competitor[]
  loading: boolean
  onSelect?: (competitor: Competitor) => void
}

export function CompetitorTable({ competitors, loading, onSelect }: CompetitorTableProps) {
  const t = useTranslations('leads')
  const columns = useMemo(() => buildCompetitorColumns(t), [t])

  const [sorting, setSorting] = React.useState<SortingState>([
    { id: 'threatScore', desc: true },
  ])

  const table = useReactTable({
    data: competitors,
    columns,
    state: { sorting },
    enableSorting: true,
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: {
      pagination: { pageSize: COMPETITORS_PER_PAGE },
    },
  })

  const emptyState = (
    <EmptyState
      icon={Shield}
      title={t('bol.competitors.emptyTitle')}
      description={t('bol.competitors.emptyDescriptionAlt')}
    />
  )

  return (
    <div className="overflow-hidden rounded-lg border border-rule bg-bone">
      <DataTable
        table={table}
        compactCells
        onRowClick={(competitor, e) => {
          if (!competitor.isBlurred) onSelect?.(competitor)
        }}
        getRowClassName={(competitor) =>
          competitor.isBlurred
            ? 'pointer-events-none select-none cursor-not-allowed bg-paper/50 [&_td]:blur-[4px]'
            : ''
        }
        isLoading={loading}
        loadingRows={8}
        emptyState={emptyState}
      />

      <DataTablePagination
        table={table}
        totalItems={competitors.length}
        pageSize={COMPETITORS_PER_PAGE}
        labels={{
          showing: (start, end, total) => `显示第 ${start}-${end} 条，共 ${total} 条`,
          page: (current, total) => `第 ${current} 页，共 ${total} 页`,
        }}
      />
    </div>
  )
}
