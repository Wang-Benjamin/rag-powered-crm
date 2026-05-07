import React, { useState, useRef, useEffect } from 'react'
import { Search, X, ChevronDown, AlertCircle } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useTranslations } from 'next-intl'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'

interface Column {
  key: string
  label: string
  icon: string | React.ComponentType<{ className?: string }>
}

interface SearchColumns {
  [key: string]: boolean
}

interface SearchBarWithColumnsProps {
  value: string
  onChange: (value: string) => void
  onClear?: () => void
  searchColumns: SearchColumns
  onColumnChange?: (columns: SearchColumns) => void
  availableColumns?: Column[]
  placeholder?: string
  className?: string
}

const SearchBarWithColumns: React.FC<SearchBarWithColumnsProps> = ({
  value,
  onChange,
  onClear,
  searchColumns,
  onColumnChange,
  availableColumns,
  placeholder,
  className = '',
}) => {
  const t = useTranslations('navigation.search')
  const [showColumnDropdown, setShowColumnDropdown] = useState(false)
  const [isComposing, setIsComposing] = useState(false)
  const [localValue, setLocalValue] = useState(value)
  const searchRef = useRef<HTMLDivElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Sync local value with prop when not composing
  useEffect(() => {
    if (!isComposing) {
      setLocalValue(value)
    }
  }, [value, isComposing])

  // Default available columns for searching (fallback)
  const defaultAvailableColumns: Column[] = [
    { key: 'company', label: 'Company', icon: '🏢' },
    { key: 'status', label: 'Status', icon: '📊' },
    { key: 'notes', label: 'Notes', icon: '📝' },
  ]

  const columns = availableColumns || defaultAvailableColumns

  // Count active columns
  const activeColumnCount = Object.values(searchColumns || {}).filter((v) => v).length

  // Handle click outside to close column dropdown
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(event.target as Node)) {
        setShowColumnDropdown(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleClear = () => {
    onClear?.()
  }

  const handleColumnToggle = (columnKey: string) => {
    const newColumns = { ...searchColumns }
    newColumns[columnKey] = !newColumns[columnKey]
    onColumnChange?.(newColumns)
  }

  const handleSelectAll = () => {
    const newColumns: SearchColumns = {}
    columns.forEach((col) => {
      newColumns[col.key] = true
    })
    onColumnChange?.(newColumns)
  }

  const handleSelectNone = () => {
    const newColumns: SearchColumns = {}
    columns.forEach((col) => {
      newColumns[col.key] = false
    })
    onColumnChange?.(newColumns)
  }

  return (
    <div className={`relative ${className}`} ref={searchRef}>
      {/* Search bar with column selector - always expanded */}
      <div
        className={`flex h-[34px] min-w-80 items-center gap-2 rounded-lg border px-3 ${
          activeColumnCount === 0 && value
            ? 'border-gold bg-gold/10'
            : 'border-rule bg-bone'
        }`}
      >
        {/* Search Icon */}
        <Search
          className={`h-[14px] w-[14px] flex-shrink-0 ${
            activeColumnCount === 0 && value ? 'text-gold' : 'text-mute'
          }`}
        />

        {/* Search Input — uses local state during IME composition to prevent React snapping */}
        <Input
          ref={inputRef}
          type="text"
          value={isComposing ? localValue : value}
          onChange={(e) => {
            const val = e.target.value
            setLocalValue(val)
            if (!isComposing) {
              onChange?.(val)
            }
          }}
          onCompositionStart={() => setIsComposing(true)}
          onCompositionEnd={(e) => {
            setIsComposing(false)
            const val = (e.target as HTMLInputElement).value
            setLocalValue(val)
            onChange?.(val)
          }}
          placeholder={placeholder}
          disabled={activeColumnCount === 0}
          className="h-auto flex-1 border-0 bg-transparent p-0 shadow-none focus-visible:ring-0 focus-visible:ring-offset-0 disabled:cursor-not-allowed disabled:opacity-50"
          title={activeColumnCount === 0 ? t('selectColumnToSearch') : undefined}
        />

        {/* Warning indicator when no columns selected */}
        {activeColumnCount === 0 && value && (
          <div className="flex items-center text-xs whitespace-nowrap text-gold">
            <AlertCircle className="mr-1 h-4 w-4" />
            <span>{t('noColumns')}</span>
          </div>
        )}

        {/* Column Selector Button */}
        <div className="relative">
          <button
            onClick={() => setShowColumnDropdown(!showColumnDropdown)}
            className={`flex items-center gap-1 rounded px-2 py-1 text-xs transition-colors ${
              activeColumnCount === 0
                ? 'bg-gold/20 font-semibold text-ink hover:bg-gold/30'
                : 'bg-cream hover:bg-fog'
            }`}
            title={t('selectColumnToSearch')}
          >
            <span className="font-medium">
              {activeColumnCount}{' '}
              {t('columnsCount', { count: activeColumnCount })
                .replace(String(activeColumnCount), '')
                .trim()}
            </span>
            <ChevronDown
              className={`h-3 w-3 transition-transform ${showColumnDropdown ? 'rotate-180' : ''}`}
            />
          </button>

          {/* Column Dropdown — editorial paper-warm popover matching Buyers.html pop-columns */}
          <AnimatePresence>
            {showColumnDropdown && (
              <motion.div
                ref={dropdownRef}
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.14 }}
                className="absolute right-0 top-[calc(100%+6px)] z-50 w-[264px] overflow-hidden rounded-xl border border-rule bg-bone shadow-[0_24px_80px_-32px_oklch(0.2_0.02_260/0.4)]"
              >
                {/* Head */}
                <div className="flex items-center justify-between gap-3 border-b border-rule bg-paper px-4 py-3">
                  <span className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-mute">
                    {t('searchInColumns')}
                  </span>
                  <div className="inline-flex items-center gap-2.5">
                    <button
                      onClick={handleSelectAll}
                      className="text-[12px] text-mute transition-colors hover:text-ink"
                    >
                      {t('selectAll')}
                    </button>
                    <span className="text-rule text-[12px]">·</span>
                    <button
                      onClick={handleSelectNone}
                      className="text-[12px] text-mute transition-colors hover:text-ink"
                    >
                      {t('clearAll')}
                    </button>
                  </div>
                </div>

                {/* Body — no column icons per product preference */}
                <div className="max-h-[340px] overflow-y-auto py-1.5">
                  {columns.map((column) => {
                    const isOn = searchColumns?.[column.key] || false
                    return (
                      <label
                        key={column.key}
                        className="flex cursor-pointer select-none items-center gap-3 px-4 py-2 text-[13.5px] text-ink transition-colors hover:bg-paper"
                      >
                        <Checkbox
                          checked={isOn}
                          onCheckedChange={() => handleColumnToggle(column.key)}
                        />
                        <span className="flex-1">{column.label}</span>
                      </label>
                    )
                  })}
                </div>

                {/* Foot — single full-width apply button */}
                <div className="border-t border-rule bg-paper px-4 py-2.5">
                  <button
                    onClick={() => setShowColumnDropdown(false)}
                    className="inline-flex h-[34px] w-full items-center justify-center rounded-lg border border-deep bg-deep text-[13px] font-medium text-bone transition-colors hover:border-accent hover:bg-accent"
                  >
                    {t('done')}
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Clear Button */}
        {value && (
          <button
            onClick={handleClear}
            className="rounded p-1 transition-colors hover:bg-cream"
            title={t('clearSearch')}
          >
            <X className="h-4 w-4 text-mute" />
          </button>
        )}
      </div>
    </div>
  )
}

export default SearchBarWithColumns
