'use client'

import { Table } from '@tanstack/react-table'
import { ChevronLeft, ChevronRight } from 'lucide-react'

export interface DataTablePaginationProps {
  table: Table<any>
  totalItems: number
  pageSize: number
  labels?: {
    showing?: (start: number, end: number, total: number) => string
    page?: (current: number, total: number) => string
  }
}

export function DataTablePagination({
  table,
  totalItems,
  pageSize,
  labels,
}: DataTablePaginationProps) {
  if (table.getPageCount() <= 1) return null

  const pageIndex = table.getState().pagination.pageIndex
  const start = pageIndex * pageSize + 1
  const end = Math.min((pageIndex + 1) * pageSize, totalItems)
  const current = pageIndex + 1
  const total = table.getPageCount()

  const showingText = labels?.showing
    ? labels.showing(start, end, totalItems)
    : `Showing ${start}-${end} of ${totalItems}`

  const pageText = labels?.page
    ? labels.page(current, total)
    : `Page ${current} of ${total}`

  return (
    <div className="flex flex-shrink-0 items-center justify-between border-t border-rule bg-paper px-4 py-2.5">
      <span className="font-mono text-[11px] tracking-[0.06em] text-mute">{showingText}</span>
      <div className="flex items-center gap-2">
        <button
          onClick={() => table.previousPage()}
          disabled={!table.getCanPreviousPage()}
          className="inline-flex h-[26px] w-[26px] items-center justify-center rounded-md border border-rule bg-bone text-mute transition-colors hover:border-ink hover:bg-cream hover:text-ink disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-rule disabled:hover:bg-bone disabled:hover:text-mute"
        >
          <ChevronLeft className="h-3 w-3" />
        </button>
        <span className="font-mono text-[11px] tracking-[0.06em] text-mute">{pageText}</span>
        <button
          onClick={() => table.nextPage()}
          disabled={!table.getCanNextPage()}
          className="inline-flex h-[26px] w-[26px] items-center justify-center rounded-md border border-rule bg-bone text-mute transition-colors hover:border-ink hover:bg-cream hover:text-ink disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-rule disabled:hover:bg-bone disabled:hover:text-mute"
        >
          <ChevronRight className="h-3 w-3" />
        </button>
      </div>
    </div>
  )
}
