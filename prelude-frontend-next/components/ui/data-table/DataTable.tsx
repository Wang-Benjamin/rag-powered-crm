'use client'

import { flexRender, Table } from '@tanstack/react-table'
import { Inbox } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import type { DataTableColumnMeta } from './types'

export interface DataTableProps<TData> {
  table: Table<TData>
  onRowClick?: (row: TData, event: React.MouseEvent) => void
  getRowClassName?: (row: TData) => string
  isLoading?: boolean
  loadingRows?: number
  emptyState?: React.ReactNode
  newRow?: React.ReactNode
  englishColumns?: Set<string>
  className?: string
  /**
   * When true, cells get `px-4` only — vertical spacing is controlled by each
   * column's `cellClassName` (typically via `h-16 align-middle` or similar).
   * Matches the Buyers.html + Competitors.html editorial table spec which has
   * zero vertical padding on td and a fixed row height instead.
   */
  compactCells?: boolean
}

export function DataTable<TData>({
  table,
  onRowClick,
  getRowClassName,
  isLoading = false,
  loadingRows = 10,
  emptyState,
  newRow,
  englishColumns,
  className,
  compactCells = false,
}: DataTableProps<TData>) {
  const tdPad = compactCells ? 'px-3.5' : 'px-4 py-2'
  const thPad = compactCells ? 'px-3.5 py-2.5' : 'px-4 py-3'
  const handleRowClick = (row: TData, e: React.MouseEvent) => {
    if (!onRowClick) return
    const target = e.target as HTMLElement
    if (
      target.tagName === 'INPUT' ||
      target.tagName === 'SELECT' ||
      target.tagName === 'TEXTAREA' ||
      target.tagName === 'BUTTON' ||
      target.closest('button') ||
      target.closest('input[type="checkbox"]')
    ) {
      return
    }
    onRowClick(row, e)
  }

  const visibleColumns = table.getVisibleLeafColumns()
  const columnCount = visibleColumns.length

  const renderSkeletonCell = (
    column: (typeof visibleColumns)[number],
    rowIndex: number,
    columnIndex: number
  ) => {
    const meta = column.columnDef.meta as DataTableColumnMeta | undefined
    const type = meta?.fieldConfig?.type
    const id = column.id.toLowerCase()
    const widthSet = [
      ['72%', '42%'],
      ['58%', '36%'],
      ['66%', '48%'],
      ['50%', '32%'],
      ['62%', '40%'],
    ]
    const [primaryWidth, secondaryWidth] = widthSet[(rowIndex + columnIndex) % widthSet.length]

    if (id === 'select') {
      return <Skeleton className="h-4 w-4 rounded" />
    }

    if (type === 'select' || /status|state|stage|chip|badge|priority/.test(id)) {
      const chipWidths = [56, 64, 72, 60]
      return <Skeleton variant="chip" width={chipWidths[(rowIndex + columnIndex) % chipWidths.length]} />
    }

    if (
      type === 'number' ||
      type === 'currency' ||
      type === 'date' ||
      type === 'tel' ||
      /score|count|total|volume|trend|amount|rate|days|date|shipment|value|price|qty|quantity|overlap/.test(
        id
      )
    ) {
      const numWidths = [44, 52, 60, 48, 56]
      return <Skeleton variant="num" width={numWidths[(rowIndex + columnIndex) % numWidths.length]} />
    }

    if (
      columnIndex === 0 ||
      type === 'text' ||
      type === 'email' ||
      type === 'textarea' ||
      /name|company|customer|buyer|supplier|title|subject|email|location|website/.test(id)
    ) {
      return (
        <div className="flex flex-col gap-1.5 py-1">
          <Skeleton variant="tall" width={primaryWidth} />
          <Skeleton variant="mono" width={secondaryWidth} />
        </div>
      )
    }

    return <Skeleton className="h-4" width={primaryWidth} />
  }

  return (
    <table className={`min-w-full table-fixed bg-bone ${className ?? ''}`}>
      <thead className="sticky top-0 z-10 border-b border-rule bg-paper">
        {table.getHeaderGroups().map((headerGroup) => (
          <tr key={headerGroup.id}>
            {headerGroup.headers.map((header) => {
              const meta = header.column.columnDef.meta as DataTableColumnMeta | undefined
              return (
                <th
                  key={header.id}
                  className={`${thPad} text-left font-mono text-xs uppercase tracking-wide text-mute ${meta?.headerClassName ?? ''}`}
                >
                  {header.isPlaceholder
                    ? null
                    : flexRender(header.column.columnDef.header, header.getContext())}
                </th>
              )
            })}
          </tr>
        ))}
      </thead>
      <tbody className="divide-y divide-rule">
        {newRow}
        {isLoading ? (
          Array.from({ length: loadingRows }).map((_, i) => (
            <tr key={`skeleton-${i}`}>
              {visibleColumns.map((column, j) => {
                const meta = column.columnDef.meta as DataTableColumnMeta | undefined
                return (
                  <td key={column.id} className={`${tdPad} text-left ${meta?.cellClassName ?? ''}`}>
                    {renderSkeletonCell(column, i, j)}
                  </td>
                )
              })}
            </tr>
          ))
        ) : table.getRowModel().rows.length > 0 ? (
          table.getRowModel().rows.map((row) => (
            <tr
              key={row.id}
              onClick={(e) => handleRowClick(row.original, e)}
              className={`transition-colors ${onRowClick ? 'cursor-pointer' : ''} hover:bg-cream ${getRowClassName ? getRowClassName(row.original) : ''}`}
            >
              {row.getVisibleCells().map((cell) => {
                const meta = cell.column.columnDef.meta as DataTableColumnMeta | undefined
                return (
                  <td
                    key={cell.id}
                    className={`${tdPad} text-left ${meta?.cellClassName ?? ''}`}
                    lang={englishColumns?.has(cell.column.id) ? 'en' : undefined}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                )
              })}
            </tr>
          ))
        ) : (
          <tr>
            <td colSpan={columnCount} className="px-4 py-12 text-center">
              {emptyState ?? (
                <div className="flex flex-col items-center justify-center gap-2 py-8 text-mute">
                  <Inbox className="h-8 w-8" />
                </div>
              )}
            </td>
          </tr>
        )}
      </tbody>
    </table>
  )
}
