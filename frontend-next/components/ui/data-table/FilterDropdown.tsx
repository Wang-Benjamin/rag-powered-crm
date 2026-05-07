import React, { useState, useRef, useEffect, useLayoutEffect } from 'react'
import { useTranslations } from 'next-intl'
import { Filter, X, ChevronDown, Plus } from 'lucide-react'

interface FilterCondition {
  id: string
  column: string
  condition: string
  value: string
}

interface ColumnOption {
  value: string
  label: string
}

interface Column {
  id: string
  label: string
  type: string
  options?: ColumnOption[]
}

interface ActiveFilter {
  condition?: string
  value?: string
}

interface ActiveFilters {
  [key: string]: ActiveFilter | Array<{ condition: string; value: string }>
}

interface FilterDropdownProps {
  columns: Column[]
  onApplyFilters: (filters: { [key: string]: Array<{ condition: string; value: string }> }) => void
  activeFilters?: ActiveFilters
  className?: string
}

function createEmptyFilter(): FilterCondition {
  return { id: `filter-${Date.now()}`, column: '', condition: '', value: '' }
}

function parseActiveFilters(activeFilters: ActiveFilters | undefined): FilterCondition[] {
  if (!activeFilters) return [createEmptyFilter()]
  const conditions: FilterCondition[] = []
  Object.keys(activeFilters).forEach((columnId, index) => {
    const filter = activeFilters[columnId]
    if (filter && !Array.isArray(filter) && filter.condition) {
      // Old format: {column: {condition, value}}
      conditions.push({
        id: `filter-${index}`,
        column: columnId,
        condition: filter.condition,
        value: filter.value || '',
      })
    } else if (Array.isArray(filter)) {
      // New format (from cookies): {column: [{condition, value}]}
      filter.forEach((filterItem, idx) => {
        if (filterItem.condition) {
          conditions.push({
            id: `filter-${columnId}-${idx}`,
            column: columnId,
            condition: filterItem.condition,
            value: filterItem.value || '',
          })
        }
      })
    }
  })
  return conditions.length > 0 ? conditions : [createEmptyFilter()]
}

const FilterDropdown: React.FC<FilterDropdownProps> = ({
  columns,
  onApplyFilters,
  activeFilters = {},
  className = '',
}) => {
  const t = useTranslations('common')
  const [isOpen, setIsOpen] = useState(false)
  const [dropdownPosition, setDropdownPosition] = useState({ top: 0, left: 0 })
  const [isComposing, setIsComposing] = useState(false)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const [filterConditions, setFilterConditions] = useState<FilterCondition[]>(() =>
    parseActiveFilters(activeFilters)
  )
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Only sync from parent when filters are explicitly cleared (empty object)
  // Avoid syncing on every prop change to prevent interrupting user input
  const prevActiveFiltersKeys = useRef<string>(JSON.stringify(Object.keys(activeFilters).sort()))

  useEffect(() => {
    const currentKeys = JSON.stringify(Object.keys(activeFilters).sort())

    // Only update if the filter keys changed (not just values)
    // OR if filters were completely cleared
    if (currentKeys === prevActiveFiltersKeys.current) {
      return // No change in filter structure, skip update
    }

    prevActiveFiltersKeys.current = currentKeys

    // If activeFilters is explicitly empty (user cleared all filters)
    if (Object.keys(activeFilters).length === 0) {
      setFilterConditions([createEmptyFilter()])
      return
    }

    // Otherwise, only sync if new filters were added from outside
    const conditions = parseActiveFilters(activeFilters)

    // Only update if we have new conditions (not just the empty placeholder)
    if (conditions.length > 0 && conditions[0].column !== '') {
      setFilterConditions(conditions)
    }
  }, [activeFilters])

  // Calculate dropdown position — recalculates on scroll/resize to prevent glitches.
  // Default behavior: popover's right edge aligns with the trigger's right edge so
  // the panel grows leftward. Falls back to left-align if right-align would push
  // the panel off the left edge of the viewport.
  const recalcPosition = React.useCallback(() => {
    if (!buttonRef.current) return
    const rect = buttonRef.current.getBoundingClientRect()
    const dropdownWidth = 520
    const dropdownHeight = 384
    const viewportWidth = window.innerWidth
    const viewportHeight = window.innerHeight

    let left = rect.right - dropdownWidth
    if (left < 10) left = Math.max(10, rect.left)
    if (left + dropdownWidth > viewportWidth) {
      left = Math.max(10, viewportWidth - dropdownWidth - 10)
    }

    let top = rect.bottom + 8
    if (top + dropdownHeight > viewportHeight) {
      top = rect.top - dropdownHeight - 8
      if (top < 10) top = 10
    }

    setDropdownPosition({ top, left })
  }, [])

  // Position synchronously before paint to prevent flicker
  useLayoutEffect(() => {
    if (isOpen) recalcPosition()
  }, [isOpen, recalcPosition])

  // Re-position on scroll/resize (can be async — no flicker concern)
  useEffect(() => {
    if (isOpen) {
      window.addEventListener('scroll', recalcPosition, true)
      window.addEventListener('resize', recalcPosition)
      return () => {
        window.removeEventListener('scroll', recalcPosition, true)
        window.removeEventListener('resize', recalcPosition)
      }
    }
  }, [isOpen, recalcPosition])

  // Close dropdown when clicking outside or pressing ESC
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    const handleEscapeKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      document.addEventListener('keydown', handleEscapeKey)
      return () => {
        document.removeEventListener('mousedown', handleClickOutside)
        document.removeEventListener('keydown', handleEscapeKey)
      }
    }
  }, [isOpen])

  const addFilterCondition = () => {
    setFilterConditions((prev) => [...prev, createEmptyFilter()])
  }

  const removeFilterCondition = (id: string) => {
    setFilterConditions((prev) => {
      const newConditions = prev.filter((f) => f.id !== id)
      // Always keep at least one filter row
      return newConditions.length > 0 ? newConditions : [createEmptyFilter()]
    })
  }

  const updateFilterCondition = (id: string, field: string, value: string) => {
    setFilterConditions((prev) =>
      prev.map((filter) => {
        if (filter.id === id) {
          const updated = { ...filter, [field]: value }
          // Reset value when condition changes to certain types
          if (field === 'condition' && ['is_empty', 'not_empty'].includes(value)) {
            updated.value = ''
          }
          // Reset condition and value when column changes
          if (field === 'column') {
            updated.condition = ''
            updated.value = ''
          }
          return updated
        }
        return filter
      })
    )
  }

  const handleApply = () => {
    // Convert filter conditions to the format expected by parent
    // Support multiple conditions per field by creating an array
    const filters: { [key: string]: Array<{ condition: string; value: string }> } = {}
    filterConditions.forEach((fc) => {
      if (fc.column && fc.condition) {
        if (!filters[fc.column]) {
          filters[fc.column] = []
        }
        filters[fc.column].push({
          condition: fc.condition,
          value: fc.value,
        })
      }
    })
    onApplyFilters(filters)
    setIsOpen(false)
  }

  const handleClear = () => {
    setFilterConditions([createEmptyFilter()])
    onApplyFilters({})
  }

  const activeFilterCount = filterConditions.filter((fc) => fc.column && fc.condition).length

  const getConditionOptions = (type: string) => {
    switch (type) {
      case 'text':
      case 'email':
        return [
          { value: 'contains', label: t('filters.operators.contains') },
          { value: 'not_contains', label: t('filters.operators.notContains') },
          { value: 'equals', label: t('filters.operators.equals') },
          { value: 'not_equals', label: t('filters.operators.notEquals') },
          { value: 'starts_with', label: t('filters.operators.startsWith') },
          { value: 'ends_with', label: t('filters.operators.endsWith') },
          { value: 'is_empty', label: t('filters.operators.isEmpty') },
          { value: 'not_empty', label: t('filters.operators.isNotEmpty') },
        ]
      case 'tel':
        return [
          { value: 'contains', label: t('filters.operators.contains') },
          { value: 'not_contains', label: t('filters.operators.notContains') },
          { value: 'equals', label: t('filters.operators.equals') },
          { value: 'not_equals', label: t('filters.operators.notEquals') },
          { value: 'starts_with', label: t('filters.operators.startsWith') },
          { value: 'is_empty', label: t('filters.operators.isEmpty') },
          { value: 'not_empty', label: t('filters.operators.isNotEmpty') },
        ]
      case 'number':
      case 'currency':
      case 'percentage':
        return [
          { value: 'equals', label: t('filters.operators.equals') },
          { value: 'not_equals', label: t('filters.operators.notEquals') },
          { value: 'greater_than', label: t('filters.operators.greaterThan') },
          { value: 'less_than', label: t('filters.operators.lessThan') },
          { value: 'greater_equal', label: t('filters.operators.greaterOrEqual') },
          { value: 'less_equal', label: t('filters.operators.lessOrEqual') },
          { value: 'between', label: t('filters.operators.between') },
          { value: 'is_empty', label: t('filters.operators.isEmpty') },
          { value: 'not_empty', label: t('filters.operators.isNotEmpty') },
        ]
      case 'date':
      case 'datetime':
        return [
          { value: 'equals', label: t('filters.operators.on') },
          { value: 'not_equals', label: t('filters.operators.notOn') },
          { value: 'before', label: t('filters.operators.before') },
          { value: 'after', label: t('filters.operators.after') },
          { value: 'between', label: t('filters.operators.between') },
          { value: 'last_days', label: t('filters.operators.lastDays') },
          { value: 'next_days', label: t('filters.operators.nextDays') },
          { value: 'is_empty', label: t('filters.operators.isEmpty') },
          { value: 'not_empty', label: t('filters.operators.isNotEmpty') },
        ]
      case 'select':
      case 'dropdown':
        return [
          { value: 'equals', label: t('filters.operators.is') },
          { value: 'not_equals', label: t('filters.operators.isNot') },
          { value: 'in', label: t('filters.operators.isOneOf') },
          { value: 'not_in', label: t('filters.operators.isNotOneOf') },
          { value: 'is_empty', label: t('filters.operators.isEmpty') },
          { value: 'not_empty', label: t('filters.operators.isNotEmpty') },
        ]
      case 'boolean':
        return [
          { value: 'equals', label: t('filters.operators.is') },
          { value: 'not_equals', label: t('filters.operators.isNot') },
        ]
      default:
        // Default to text-like filters for unknown types
        return [
          { value: 'contains', label: t('filters.operators.contains') },
          { value: 'equals', label: t('filters.operators.equals') },
          { value: 'is_empty', label: t('filters.operators.isEmpty') },
          { value: 'not_empty', label: t('filters.operators.isNotEmpty') },
        ]
    }
  }

  const renderValueInput = (filter: FilterCondition) => {
    const column = columns.find((c) => c.id === filter.column)
    if (!column || !filter.condition) return null

    const needsValue = !['is_empty', 'not_empty'].includes(filter.condition)
    if (!needsValue) return null

    // Handle boolean type fields
    if (column.type === 'boolean') {
      return (
        <select
          value={filter.value || ''}
          onChange={(e) => updateFilterCondition(filter.id, 'value', e.target.value)}
          className="flex-1 rounded-md border border-rule px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
        >
          <option value="">{t('filters.select')}</option>
          <option value="true">{t('filters.boolean.yes')}</option>
          <option value="false">{t('filters.boolean.no')}</option>
        </select>
      )
    }

    if (filter.condition === 'between') {
      const [minValue, maxValue] = (filter.value || '').split(',')

      // Determine input type and constraints for between inputs
      let inputType = 'text'
      let step: string | undefined = undefined
      let min: string | undefined = undefined
      let max: string | undefined = undefined

      if (column.type === 'currency' || column.type === 'number' || column.type === 'percentage') {
        inputType = 'number'
        if (column.type === 'currency') {
          step = '0.01'
        } else if (column.type === 'percentage') {
          step = '1'
          min = '0'
          max = '100'
        }
      } else if (column.type === 'date' || column.type === 'datetime') {
        inputType = column.type === 'datetime' ? 'datetime-local' : 'date'
      }

      return (
        <div className="flex flex-1 gap-2">
          <input
            type={inputType}
            placeholder={
              column.type === 'percentage'
                ? t('filters.placeholders.minPercent')
                : column.type === 'currency'
                  ? t('filters.placeholders.minCurrency')
                  : t('filters.placeholders.min')
            }
            value={minValue || ''}
            onChange={(e) => {
              if (isComposing) return
              const newValue = `${e.target.value},${maxValue || ''}`
              updateFilterCondition(filter.id, 'value', newValue)
            }}
            onCompositionStart={() => setIsComposing(true)}
            onCompositionEnd={(e) => {
              setIsComposing(false)
              const newValue = `${(e.target as HTMLInputElement).value},${maxValue || ''}`
              updateFilterCondition(filter.id, 'value', newValue)
            }}
            className="flex-1 rounded-md border border-rule px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
            step={step}
            min={min}
            max={max}
          />
          <input
            type={inputType}
            placeholder={
              column.type === 'percentage'
                ? t('filters.placeholders.maxPercent')
                : column.type === 'currency'
                  ? t('filters.placeholders.maxCurrency')
                  : t('filters.placeholders.max')
            }
            value={maxValue || ''}
            onChange={(e) => {
              if (isComposing) return
              const newValue = `${minValue || ''},${e.target.value}`
              updateFilterCondition(filter.id, 'value', newValue)
            }}
            onCompositionStart={() => setIsComposing(true)}
            onCompositionEnd={(e) => {
              setIsComposing(false)
              const newValue = `${minValue || ''},${(e.target as HTMLInputElement).value}`
              updateFilterCondition(filter.id, 'value', newValue)
            }}
            className="flex-1 rounded-md border border-rule px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
            step={step}
            min={min}
            max={max}
          />
        </div>
      )
    }

    if (column.type === 'select' && ['in', 'not_in'].includes(filter.condition)) {
      const selectedValues = (filter.value || '').split(',').filter((v) => v)
      return (
        <div className="flex-1">
          <div className="relative">
            <select
              multiple
              value={selectedValues}
              onChange={(e) => {
                const values = Array.from(e.target.selectedOptions, (option) => option.value)
                updateFilterCondition(filter.id, 'value', values.join(','))
              }}
              className="w-full rounded-md border border-rule px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
              size={3}
            >
              {column.options?.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <div className="pointer-events-none absolute inset-x-0 bottom-0 h-4 bg-gradient-to-t from-bone to-transparent"></div>
          </div>
          {selectedValues.length > 0 && (
            <div className="mt-1 text-xs text-mute">
              {t('filters.selectedCount', { count: selectedValues.length })}
            </div>
          )}
        </div>
      )
    }

    if (column.type === 'select' && ['equals', 'not_equals'].includes(filter.condition)) {
      return (
        <select
          value={filter.value || ''}
          onChange={(e) => updateFilterCondition(filter.id, 'value', e.target.value)}
          className="flex-1 rounded-md border border-rule px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
        >
          <option value="">{t('filters.select')}</option>
          {column.options?.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      )
    }

    if (['last_days', 'next_days'].includes(filter.condition)) {
      return (
        <input
          type="number"
          placeholder={t('filters.placeholders.numberOfDays')}
          value={filter.value || ''}
          onChange={(e) => updateFilterCondition(filter.id, 'value', e.target.value)}
          className="flex-1 rounded-md border border-rule px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          min="1"
        />
      )
    }

    // Determine input type based on column type
    let inputType = 'text'
    let step: string | undefined = undefined
    let placeholder = t('filters.enterValue')
    let min: string | undefined = undefined
    let max: string | undefined = undefined

    if (column.type === 'date' || column.type === 'datetime') {
      inputType = column.type === 'datetime' ? 'datetime-local' : 'date'
    } else if (
      column.type === 'currency' ||
      column.type === 'number' ||
      column.type === 'percentage'
    ) {
      inputType = 'number'
      if (column.type === 'currency') {
        step = '0.01'
        placeholder = t('filters.placeholders.enterAmount')
      } else if (column.type === 'percentage') {
        step = '1'
        min = '0'
        max = '100'
        placeholder = t('filters.placeholders.enterPercentage')
      }
    } else if (column.type === 'email') {
      inputType = 'email'
      placeholder = t('filters.placeholders.enterEmail')
    } else if (column.type === 'tel') {
      inputType = 'tel'
      placeholder = t('filters.placeholders.enterPhone')
    }

    return (
      <input
        type={inputType}
        placeholder={placeholder}
        value={filter.value || ''}
        onChange={(e) => {
          if (isComposing) return
          updateFilterCondition(filter.id, 'value', e.target.value)
        }}
        onCompositionStart={() => setIsComposing(true)}
        onCompositionEnd={(e) => {
          setIsComposing(false)
          updateFilterCondition(filter.id, 'value', (e.target as HTMLInputElement).value)
        }}
        className="flex-1 rounded-md border border-rule px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
        step={step}
        min={min}
        max={max}
      />
    )
  }

  return (
    <div className={`relative ${className}`}>
      <button
        ref={buttonRef}
        onClick={() => setIsOpen(!isOpen)}
        className={`inline-flex h-[34px] items-center justify-center gap-1.5 rounded-lg border bg-bone px-3 text-[13px] font-medium text-ink transition-colors duration-150 hover:border-ink hover:bg-cream focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 disabled:pointer-events-none ${
          activeFilterCount > 0 ? 'border-rule' : 'border-dashed border-rule'
        }`}
      >
        <Filter className="h-3.5 w-3.5" />
        <span>{t('filters.button')}</span>
        {activeFilterCount > 0 && (
          <span className="rounded bg-deep px-1.5 py-0.5 text-[10px] text-bone">
            {activeFilterCount}
          </span>
        )}
        <ChevronDown
          className={`h-3 w-3 opacity-70 transition-transform ${isOpen ? 'rotate-180' : ''}`}
        />
      </button>

      {isOpen && (
        <div
          ref={dropdownRef}
          className="fixed z-50 w-[520px] max-w-[90vw] overflow-hidden rounded-xl border border-rule bg-bone shadow-[0_24px_80px_-32px_oklch(0.2_0.02_260/0.4)]"
          style={{
            top: `${dropdownPosition.top}px`,
            left: `${dropdownPosition.left}px`,
          }}
        >
          {/* Popover head — editorial mono title + clear-all linklet */}
          <div className="flex items-center justify-between gap-3 border-b border-rule bg-paper px-4 py-3">
            <span className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-mute">
              {t('filters.title')}
              {activeFilterCount > 0 && (
                <>
                  <span className="mx-1.5 text-rule">·</span>
                  <span className="tabular-nums">{activeFilterCount}</span>
                  <span className="ml-1 normal-case tracking-normal">{t('filters.active')}</span>
                </>
              )}
            </span>
            <button
              onClick={handleClear}
              className="text-[12px] text-mute transition-colors hover:text-ink"
            >
              {t('filters.clearAll')}
            </button>
          </div>

          {/* Body — grid-based filter rows */}
          <div className="max-h-[340px] overflow-y-auto px-4 pt-3.5 pb-1">
            {filterConditions.map((filter, index) => {
              const column = columns.find((c) => c.id === filter.column)
              const isFirstRow = index === 0
              return (
                <div
                  key={filter.id}
                  className="mb-2.5 grid items-center gap-2"
                  style={{ gridTemplateColumns: '48px 1fr 110px 1.4fr 28px' }}
                >
                  {/* Conjunction — 当 for first, 且 for subsequent */}
                  <span
                    className={`select-none text-center ${
                      isFirstRow
                        ? 'font-mono text-[10.5px] uppercase tracking-[0.12em] text-mute'
                        : 'font-display text-[13px] italic text-mute'
                    }`}
                  >
                    {isFirstRow ? t('filters.when') : t('filters.and')}
                  </span>

                  {/* Column select */}
                  <select
                    value={filter.column}
                    onChange={(e) => updateFilterCondition(filter.id, 'column', e.target.value)}
                    className="h-[34px] w-full rounded-lg border border-rule bg-bone px-2.5 pr-7 text-[13px] text-ink transition-colors hover:border-mute focus:border-accent focus:outline-none focus:ring-[3px] focus:ring-accent-lo"
                  >
                    <option value="">{t('filters.selectColumn')}</option>
                    {columns.map((col) => (
                      <option key={col.id} value={col.id}>
                        {col.label}
                      </option>
                    ))}
                  </select>

                  {/* Condition select */}
                  {filter.column ? (
                    <select
                      value={filter.condition}
                      onChange={(e) =>
                        updateFilterCondition(filter.id, 'condition', e.target.value)
                      }
                      className="h-[34px] w-full rounded-lg border border-rule bg-bone px-2.5 pr-7 text-[13px] text-ink transition-colors hover:border-mute focus:border-accent focus:outline-none focus:ring-[3px] focus:ring-accent-lo"
                    >
                      <option value="">{t('filters.selectCondition')}</option>
                      {getConditionOptions(column?.type || '').map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <span aria-hidden />
                  )}

                  {/* Value input */}
                  {filter.column &&
                  filter.condition &&
                  !['is_empty', 'not_empty'].includes(filter.condition) ? (
                    <div className="min-w-0">{renderValueInput(filter)}</div>
                  ) : (
                    <span aria-hidden />
                  )}

                  {/* Remove row */}
                  {filterConditions.length > 1 ? (
                    <button
                      onClick={() => removeFilterCondition(filter.id)}
                      aria-label={t('filters.cancel')}
                      className="inline-flex h-7 w-7 items-center justify-center rounded-md text-mute transition-colors hover:bg-cream hover:text-threat"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  ) : (
                    <span aria-hidden />
                  )}
                </div>
              )
            })}

            <button
              onClick={addFilterCondition}
              className="mb-3 mt-0.5 inline-flex items-center gap-1.5 text-[12.5px] text-mute transition-colors hover:text-accent"
            >
              <Plus className="h-[13px] w-[13px]" />
              {t('filters.addCondition')}
            </button>
          </div>

          {/* Foot — 取消 linklet + 应用筛选 deep button */}
          <div className="flex items-center justify-between gap-2.5 border-t border-rule bg-paper px-3 py-2.5">
            <button
              onClick={() => setIsOpen(false)}
              className="text-[13px] text-mute transition-colors hover:text-ink"
            >
              {t('filters.cancel')}
            </button>
            <button
              onClick={handleApply}
              className="inline-flex items-center rounded-lg border border-deep bg-deep px-3.5 py-[7px] text-[12.5px] font-medium text-bone transition-colors hover:border-accent hover:bg-accent"
            >
              {t('filters.apply')}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default FilterDropdown
