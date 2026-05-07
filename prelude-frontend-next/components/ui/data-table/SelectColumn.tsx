'use client'

import { ColumnDef } from '@tanstack/react-table'
import type { DataTableColumnMeta } from './types'

export function createSelectColumn<TData>(): ColumnDef<TData> {
  return {
    id: 'select',
    header: ({ table }: any) => (
      <input
        type="checkbox"
        checked={table.getIsAllPageRowsSelected()}
        onChange={table.getToggleAllPageRowsSelectedHandler()}
        className="h-4 w-4 rounded border-rule text-accent focus:ring-accent"
      />
    ),
    cell: ({ row }: any) => (
      <input
        type="checkbox"
        checked={row.getIsSelected()}
        onChange={row.getToggleSelectedHandler()}
        className="h-4 w-4 rounded border-rule text-accent focus:ring-accent"
      />
    ),
    enableSorting: false,
    enableHiding: false,
    meta: {
      headerClassName: 'w-[50px]',
      cellClassName: 'w-[50px]',
    } as DataTableColumnMeta,
  }
}
