'use client'

import { Column } from '@tanstack/react-table'
import { ArrowUp, ArrowDown, ArrowUpDown } from 'lucide-react'

interface SortableHeaderProps<TData> {
  column: Column<TData>
  label: string
  icon?: React.ComponentType<{ className?: string }>
}

export function SortableHeader<TData>({ column, label, icon: Icon }: SortableHeaderProps<TData>) {
  return (
    <div
      className="flex cursor-pointer items-center gap-2 hover:text-ink"
      onClick={() => column.toggleSorting()}
    >
      {Icon && <Icon className="h-3.5 w-3.5 text-mute" />}
      <span>{label}</span>
      {column.getIsSorted() ? (
        column.getIsSorted() === 'asc' ? (
          <ArrowUp className="h-3 w-3 text-mute" />
        ) : (
          <ArrowDown className="h-3 w-3 text-mute" />
        )
      ) : (
        <ArrowUpDown className="h-3 w-3 text-mute" />
      )}
    </div>
  )
}
