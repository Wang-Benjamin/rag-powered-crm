'use client'

import { useEffect, useRef, useState } from 'react'
import { Table } from '@tanstack/react-table'
import { Check, MoreVertical } from 'lucide-react'
import { Checkbox } from '@/components/ui/checkbox'
import type { DataTableColumnMeta, FieldConfig } from './types'

export interface DataTableToolbarProps {
  table: Table<any>
  fieldConfig?: Record<string, FieldConfig>
  actions?: React.ReactNode
  search?: React.ReactNode
  filters?: React.ReactNode
  toggles?: Array<{
    key: string
    label: string
    checked: boolean
    onChange: (checked: boolean) => void
  }>
  extraMenuItems?: React.ReactNode
  labels?: {
    moreOptions?: string
    columns?: string
  }
}

export function DataTableToolbar({
  table,
  fieldConfig,
  actions,
  search,
  filters,
  toggles,
  extraMenuItems,
  labels,
}: DataTableToolbarProps) {
  const [showMoreOptions, setShowMoreOptions] = useState(false)
  const moreOptionsRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (moreOptionsRef.current && !moreOptionsRef.current.contains(event.target as Node)) {
        setShowMoreOptions(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const allLeafColumns = table.getAllLeafColumns()
  const visibleCount = allLeafColumns.filter(
    (col) => col.getIsVisible() && col.id !== 'select'
  ).length
  const totalCount = allLeafColumns.filter((col) => col.id !== 'select').length

  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Left group */}
      {actions}
      {search}
      {filters}

      {/* More Options */}
      <div className="relative" ref={moreOptionsRef}>
        <button
          onClick={() => setShowMoreOptions((prev) => !prev)}
          className="inline-flex h-[34px] w-[34px] items-center justify-center rounded-lg border border-rule bg-bone p-0 text-mute transition-colors duration-150 hover:border-ink hover:bg-cream hover:text-ink"
          title={labels?.moreOptions ?? 'More options'}
        >
          <MoreVertical className="h-4 w-4" />
        </button>

        {showMoreOptions && (
          <div className="absolute top-[calc(100%+6px)] right-0 z-50 w-[260px] overflow-hidden rounded-xl border border-rule bg-bone shadow-[0_24px_80px_-32px_oklch(0.2_0.02_260/0.4)]">
            {/* Toggles */}
            {toggles && toggles.length > 0 && (
              <>
                {toggles.map((toggle) => (
                  <button
                    key={toggle.key}
                    onClick={() => {
                      toggle.onChange(!toggle.checked)
                      setShowMoreOptions(false)
                    }}
                    className="flex w-full items-center gap-3 px-4 py-2 text-left text-[13.5px] text-ink transition-colors hover:bg-paper"
                  >
                    <Check
                      className={`h-4 w-4 shrink-0 text-deep ${toggle.checked ? '' : 'opacity-0'}`}
                    />
                    <span>{toggle.label}</span>
                  </button>
                ))}
              </>
            )}

            {/* Extra menu items — close dropdown on click */}
            {extraMenuItems && (
              <div onClick={() => setShowMoreOptions(false)}>
                {extraMenuItems}
              </div>
            )}

            {/* Divider before columns */}
            {(toggles?.length || extraMenuItems) && (
              <div className="mx-0 my-1.5 h-px bg-rule" />
            )}

            {/* Column visibility section */}
            <div>
              {/* Section header — mono uppercase with visible/total count */}
              <div className="flex items-baseline justify-between px-4 pb-1.5 pt-3.5">
                <span className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-mute">
                  {labels?.columns ?? 'Columns'}
                </span>
                <span className="font-mono text-[11px] tabular-nums text-mute">
                  {visibleCount}/{totalCount}
                </span>
              </div>
              {/* Column items — no per-row icons per product preference */}
              <div className="pb-1.5">
                {allLeafColumns
                  .filter((column) => column.id !== 'select')
                  .map((column) => {
                    const meta = column.columnDef.meta as DataTableColumnMeta | undefined
                    const fc = meta?.fieldConfig ?? fieldConfig?.[column.id]
                    const label =
                      fc?.label ??
                      (typeof column.columnDef.header === 'string'
                        ? column.columnDef.header
                        : column.id)
                    return (
                      <label
                        key={column.id}
                        className="flex cursor-pointer items-center gap-3 px-4 py-2 text-[13.5px] text-ink transition-colors hover:bg-paper"
                      >
                        <Checkbox
                          checked={column.getIsVisible()}
                          onCheckedChange={(checked) => column.toggleVisibility(checked)}
                        />
                        <span className="flex-1">{label}</span>
                      </label>
                    )
                  })}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
