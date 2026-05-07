import { useMemo } from 'react'
import type { FieldConfig } from './types'

export interface UseTableFilteringOptions<TData> {
  searchTerm: string
  searchColumns: Record<string, boolean>
  columnFilters: Record<string, Array<{ condition: string; value: string }>>
  fieldConfig: Record<string, FieldConfig>
  preFilters?: (data: TData[]) => TData[]
  getSearchValue?: (row: TData, columnId: string) => string | null
  getFilterValue?: (row: TData, columnId: string) => any
}

function applyFilterCondition(
  value: any,
  condition: string,
  filterValue: string,
  columnType?: string
): boolean {
  // Handle empty/not empty conditions
  if (condition === 'is_empty') {
    return value === null || value === undefined || value === ''
  }
  if (condition === 'not_empty') {
    return value !== null && value !== undefined && value !== ''
  }

  // If value is empty and we're not checking for empty, fail the filter
  if (value === null || value === undefined || value === '') {
    return false
  }

  // If filterValue is empty, skip this filter condition
  if (filterValue === null || filterValue === undefined || filterValue === '') {
    return true
  }

  const valueStr = String(value).normalize('NFKC').toLowerCase()
  const filterStr = filterValue.normalize('NFKC').toLowerCase()

  // Text conditions
  if (condition === 'contains') return valueStr.includes(filterStr)
  if (condition === 'not_contains') return !valueStr.includes(filterStr)
  if (condition === 'equals') return valueStr === filterStr
  if (condition === 'not_equals') return valueStr !== filterStr
  if (condition === 'starts_with') return valueStr.startsWith(filterStr)
  if (condition === 'ends_with') return valueStr.endsWith(filterStr)

  // Numeric conditions
  if (columnType === 'currency' || columnType === 'number' || columnType === 'percentage') {
    const numValue = parseFloat(String(value))
    const numFilter = parseFloat(filterValue)

    if (isNaN(numValue) || isNaN(numFilter)) return false

    if (condition === 'greater_than') return numValue > numFilter
    if (condition === 'less_than') return numValue < numFilter
    if (condition === 'greater_equal') return numValue >= numFilter
    if (condition === 'less_equal') return numValue <= numFilter

    if (condition === 'between') {
      const [min, max] = filterValue.split(',').map((v) => parseFloat(v.trim()))
      if (isNaN(min) || isNaN(max)) return false
      return numValue >= min && numValue <= max
    }
  }

  // Date conditions
  if (columnType === 'date' || columnType === 'datetime') {
    const dateValue = new Date(value)
    const dateFilter = new Date(filterValue)

    if (isNaN(dateValue.getTime())) return false

    if (condition === 'before') return dateValue < dateFilter
    if (condition === 'after') return dateValue > dateFilter

    if (condition === 'between') {
      const [date1, date2] = filterValue.split(',')
      const startDate = new Date(date1.trim())
      const endDate = new Date(date2.trim())
      if (isNaN(startDate.getTime()) || isNaN(endDate.getTime())) return false
      return dateValue >= startDate && dateValue <= endDate
    }

    if (condition === 'last_days') {
      const days = parseInt(filterValue)
      if (isNaN(days)) return false
      const daysAgo = new Date()
      daysAgo.setDate(daysAgo.getDate() - days)
      return dateValue >= daysAgo
    }

    if (condition === 'next_days') {
      const days = parseInt(filterValue)
      if (isNaN(days)) return false
      const daysFromNow = new Date()
      daysFromNow.setDate(daysFromNow.getDate() + days)
      return dateValue <= daysFromNow
    }
  }

  // Select conditions
  if (columnType === 'select') {
    if (condition === 'in') {
      const values = filterValue.split(',').map((v) => v.trim().toLowerCase())
      return values.includes(valueStr)
    }
    if (condition === 'not_in') {
      const values = filterValue.split(',').map((v) => v.trim().toLowerCase())
      return !values.includes(valueStr)
    }
  }

  // Default: exact match
  return valueStr === filterStr
}

export function useTableFiltering<TData>(
  data: TData[],
  options: UseTableFilteringOptions<TData>
): TData[] {
  const {
    searchTerm,
    searchColumns,
    columnFilters,
    fieldConfig,
    preFilters,
    getSearchValue,
    getFilterValue,
  } = options

  return useMemo(() => {
    if (!data) return []

    // a. Apply preFilters first
    let filtered = preFilters ? preFilters(data) : [...data]

    // b. Apply search filter
    if (searchTerm) {
      const searchLower = searchTerm.normalize('NFKC').toLowerCase()
      const selectedColumns = Object.keys(searchColumns).filter((key) => searchColumns[key])

      if (selectedColumns.length > 0) {
        filtered = filtered.filter((row) => {
          return selectedColumns.some((columnId) => {
            let rawValue: string | null
            if (getSearchValue) {
              rawValue = getSearchValue(row, columnId)
            } else {
              rawValue = String((row as any)[columnId] ?? '')
            }
            if (rawValue === null) return false
            return rawValue.normalize('NFKC').toLowerCase().includes(searchLower)
          })
        })
      }
      // If no columns selected, search is effectively disabled (don't filter)
    }

    // c. Apply column filters
    if (Object.keys(columnFilters).length > 0) {
      filtered = filtered.filter((row) => {
        return Object.entries(columnFilters).every(([columnId, filterArray]) => {
          if (!filterArray || !Array.isArray(filterArray) || filterArray.length === 0) {
            return true
          }

          const rowValue = getFilterValue
            ? getFilterValue(row, columnId)
            : (row as any)[columnId]

          const columnType = fieldConfig[columnId]?.type

          // All conditions for this column must pass (AND logic)
          return filterArray.every((filter) => {
            const { condition, value } = filter
            if (!condition) return true
            return applyFilterCondition(rowValue, condition, value, columnType)
          })
        })
      })
    }

    return filtered
  }, [data, searchTerm, searchColumns, columnFilters, fieldConfig, preFilters, getSearchValue, getFilterValue])
}
