'use client'

import React, { useState, useEffect } from 'react'
import { Row, Column, Table } from '@tanstack/react-table'
import { Edit3 } from 'lucide-react'
import { InlineLoader } from '@/components/ui/inline-loader'
import type { DataTableColumnMeta, DataTableMeta } from './types'

interface EditableCellProps<TData> {
  getValue: () => any
  row: Row<TData>
  column: Column<TData>
  table: Table<TData>
}

function EditableCellInner<TData>({ getValue, row, column, table }: EditableCellProps<TData>) {
  const columnMeta = column.columnDef.meta as DataTableColumnMeta | undefined
  const fieldConfig = columnMeta?.fieldConfig
  const tableMeta = table.options.meta as DataTableMeta<TData> | undefined
  const initialValue = getValue()
  const isNumericField = fieldConfig?.type === 'currency' || fieldConfig?.type === 'number'
  const toInputValue = (v: any): any => {
    if (v === null || v === undefined) return ''
    return isNumericField ? v : String(v)
  }
  const normalizedInitialValue = toInputValue(initialValue)
  const matchesOptionValue = (optionValue: string | number, candidate: string) =>
    String(optionValue) === candidate ||
    (typeof optionValue === 'string' && optionValue.toLowerCase() === candidate.toLowerCase())

  const [value, setValue] = useState(normalizedInitialValue)
  const [isEditing, setIsEditing] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const saveTimeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    setValue(normalizedInitialValue)
  }, [normalizedInitialValue])

  const valuesMatch = (left: any, right: any) => {
    if (left === right) return true
    if (left === null || left === undefined || left === '') {
      return right === null || right === undefined || right === ''
    }
    if (right === null || right === undefined || right === '') return false
    return String(left) === String(right)
  }

  const handleSave = async () => {
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current)
      saveTimeoutRef.current = null
    }

    if (isSaving) return

    if (valuesMatch(value, initialValue)) {
      setIsEditing(false)
      return
    }

    if (fieldConfig?.validation) {
      const validationError = fieldConfig.validation(value)
      if (validationError) {
        setError(validationError)
        return
      }
    }

    setIsSaving(true)
    setError(null)

    try {
      await tableMeta?.updateData(row, column.id, value)
      setIsEditing(false)
      tableMeta?.onSaveSuccess?.(column.id)
    } catch (err: any) {
      const errorObj = err instanceof Error ? err : new Error(err?.message || 'Update failed')
      setError(errorObj.message)
      tableMeta?.onSaveError?.(column.id, errorObj)
    } finally {
      setIsSaving(false)
    }
  }

  const handleCancel = () => {
    setValue(normalizedInitialValue)
    setIsEditing(false)
    setError(null)
  }

  const formatDisplayValue = (): React.ReactNode => {
    if (!value && value !== 0) return '-'

    // renderDisplay callback takes priority
    if (fieldConfig?.renderDisplay) {
      return fieldConfig.renderDisplay(value)
    }

    switch (fieldConfig?.type) {
      case 'currency': {
        const num = typeof value === 'number' ? value : parseFloat(String(value))
        return isNaN(num)
          ? value
          : new Intl.NumberFormat(undefined, {
              style: 'currency',
              currency: 'USD',
              minimumFractionDigits: 0,
              maximumFractionDigits: 0,
            }).format(num)
      }
      case 'date':
        return value ? new Date(String(value)).toLocaleDateString() : '-'
      case 'select': {
        const option = fieldConfig.options?.find((opt) =>
          matchesOptionValue(opt.value, String(value))
        )
        return option?.label ?? value
      }
      default:
        return value
    }
  }

  if (fieldConfig?.readonly) {
    return <div className="py-1 text-sm text-ink">{formatDisplayValue()}</div>
  }

  if (isEditing) {
    return (
      <div className="relative">
        <div className="flex items-center gap-1">
          {fieldConfig?.type === 'select' ? (
            <select
              value={value}
              onChange={(e) => {
                setValue(e.target.value)
                if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
                saveTimeoutRef.current = setTimeout(() => handleSave(), 100)
              }}
              onBlur={handleSave}
              className={`flex-1 rounded border px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-accent ${
                error ? 'border-threat' : 'border-rule'
              }`}
              autoFocus
              disabled={isSaving}
            >
              {fieldConfig.options?.map((option) => (
                <option key={option.value} value={String(option.value)}>
                  {option.label}
                </option>
              ))}
            </select>
          ) : fieldConfig?.type === 'textarea' ? (
            <textarea
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onBlur={handleSave}
              className={`flex-1 rounded border px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-accent ${
                error ? 'border-threat' : 'border-rule'
              }`}
              autoFocus
              disabled={isSaving}
              rows={2}
              onKeyDown={(e) => {
                if (e.key === 'Escape') handleCancel()
              }}
            />
          ) : (
            <input
              type={(() => {
                switch (fieldConfig?.type) {
                  case 'date': return 'date'
                  case 'email': return 'email'
                  case 'tel': return 'tel'
                  default: return 'text'
                }
              })()}
              inputMode={fieldConfig?.type === 'currency' || fieldConfig?.type === 'number' ? 'decimal' : undefined}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onBlur={handleSave}
              className={`flex-1 rounded border px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-accent ${
                error ? 'border-threat' : 'border-rule'
              }`}
              autoFocus
              disabled={isSaving}

              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSave()
                if (e.key === 'Escape') handleCancel()
              }}
            />
          )}

          <div className="flex flex-shrink-0 items-center gap-1">
            {isSaving && <InlineLoader label="Saving" className="text-[10px] text-mute" />}
          </div>
        </div>
        {error && (
          <div className="absolute top-full left-0 z-10 mt-1 rounded border border-rule bg-bone px-2 py-1 text-xs text-threat shadow-sm">
            {error}
          </div>
        )}
      </div>
    )
  }

  const displayValue = formatDisplayValue()
  const stringValue = String(displayValue)

  return (
    <div
      className="group flex min-h-[32px] cursor-pointer items-center justify-between rounded py-1 transition-all hover:bg-cream"
      onClick={(e) => {
        e.stopPropagation()
        setIsEditing(true)
      }}
    >
      {typeof displayValue !== 'string' && displayValue !== '-' ? (
        // renderDisplay returned a ReactNode — render it directly
        <div className="flex-1">{displayValue}</div>
      ) : (
        <span
          className={`truncate ${value ? 'text-ink' : 'text-mute italic'}`}
          title={stringValue !== '-' ? stringValue : undefined}
        >
          {displayValue}
        </span>
      )}
      <Edit3 className="ml-1 h-3.5 w-3.5 flex-shrink-0 text-mute opacity-0 transition-opacity group-hover:opacity-100" />
    </div>
  )
}

export const EditableCell = React.memo(EditableCellInner) as typeof EditableCellInner
