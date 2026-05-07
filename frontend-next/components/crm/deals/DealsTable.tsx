'use client'

import React, { useState, useMemo, useCallback, useEffect, useRef } from 'react'
import { useRouter } from '@/i18n/navigation'
import { useParams } from 'next/navigation'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  SortingState,
  Row,
} from '@tanstack/react-table'
import {
  Plus,
  RefreshCw,
  Building,
  Building2,
  FileText,
  User,
  Briefcase,
  AlertCircle,
  Loader2,
  ChevronDown,
} from 'lucide-react'
import { useCRM } from '@/contexts/CRMContext'
import { useAuth } from '@/hooks/useAuth'
import {
  usePersistedSearch,
  usePersistedFilters,
  usePersistedColumns,
  usePersistedState,
} from '@/hooks/usePersistedState'
import { useTranslations } from 'next-intl'
import { toast } from 'sonner'
import { crmApiClient } from '@/lib/api/client'
import SearchBarWithColumns from '@/components/ui/data-table/SearchBarWithColumns'
import FilterDropdown from '@/components/ui/data-table/FilterDropdown'
import { EmptyState } from '@/components/ui/states/EmptyState'
import {
  DataTable,
  DataTableToolbar,
  DataTablePagination,
  useTableFiltering,
} from '@/components/ui/data-table'
import { buildDealColumns, buildDealFieldConfig, ENGLISH_DATA_COLUMNS } from './dealColumns'
import type { Deal } from '@/types/crm'

const DEALS_PER_PAGE = 10

interface DealsTableProps {
  selectedDealIds?: Set<string>
  onSelectionChange?: (selectedIds: Set<string>) => void
}

export default function DealsTable({
  selectedDealIds = new Set(),
  onSelectionChange,
}: DealsTableProps) {
  const {
    deals,
    dealsLoading,
    dealsError,
    setDeals,
    loadDeals,
    customers,
    employees,
    loadEmployees,
  } = useCRM()
  const { isAuthenticated } = useAuth()
  const t = useTranslations('crm')
  const tc = useTranslations('common')
  const router = useRouter()
  const params = useParams()
  const workspaceId = params?.workspaceId as string

  // New deal state
  const [isAddingNewDeal, setIsAddingNewDeal] = useState(false)
  const [isSavingNewDeal, setIsSavingNewDeal] = useState(false)
  const [newDealData, setNewDealData] = useState<Partial<Deal>>({})

  // Toolbar dropdown state
  const [showAddDealsDropdown, setShowAddDealsDropdown] = useState(false)
  const addDealsDropdownRef = useRef<HTMLDivElement>(null)

  // Persisted state — same cookie keys as original
  const { searchTerm, setSearchTerm, searchColumns, setSearchColumns } = usePersistedSearch(
    'deals',
    {
      term: '',
      columns: { dealName: true, description: true, clientName: true, salesmanName: true },
    }
  )

  const [filters, setFilters] = usePersistedFilters('deals', {
    showClosedDeals: 'false',
  })

  const [columnFilters, setColumnFilters] = usePersistedState<Record<string, any>>(
    'prelude_advfilter_deals',
    {},
    { expires: 365 }
  )

  const [sorting, setSorting] = usePersistedState<SortingState>('prelude_sort_deals', [])
  const [columnVisibility, setColumnVisibility] = usePersistedColumns('deals', {
    description: false,
    fobPrice: false,
    moq: false,
    viewCount: false,
    expectedCloseDate: false,
    salesmanName: false,
  })

  // Field configuration
  const fieldConfig = useMemo(
    () => buildDealFieldConfig(t as any, employees ?? [], customers ?? []),
    [t, employees, customers]
  )

  // Stable callback refs for useTableFiltering (TanStack requires stable data references)
  const preFilters = useCallback(
    (data: Deal[]) => {
      let filtered = data.filter((d: any) => d.dealId != null)
      if (filters.showClosedDeals !== 'true') {
        filtered = filtered.filter((deal: any) => {
          const roomStatus = deal.roomStatus
          return roomStatus !== 'closed-won' && roomStatus !== 'closed-lost'
        })
      }
      return filtered
    },
    [filters.showClosedDeals]
  )

  // Filtered data via shared hook
  const filteredDeals = useTableFiltering(deals ?? [], {
    searchTerm,
    searchColumns,
    columnFilters,
    fieldConfig,
    preFilters,
  })

  // Column definitions
  const columns = useMemo(
    () =>
      buildDealColumns({
        t: t as any,
        router,
        workspaceId,
        fieldConfig,
      }),
    [t, router, workspaceId, fieldConfig]
  )

  // updateData — deals-specific logic with field remapping
  const updateData = async (row: Row<Deal>, columnId: string, value: any) => {
    const deal = row.original
    if (!deal) return

    const dealId = deal.dealId || deal.id
    if (!dealId) {
      throw new Error('Deal ID not found')
    }

    let processedValue = value
    let fieldName = columnId

    // Special handling for clientName — map to clientId for backend
    if (columnId === 'clientName') {
      fieldName = 'clientId'
      processedValue = parseInt(value) || null
    }
    // Special handling for salesmanName — map to employeeId for backend
    else if (columnId === 'salesmanName') {
      fieldName = 'employeeId'
      processedValue = parseInt(value) || null
    }
    // Process different field types
    else if (fieldConfig[columnId]?.type === 'currency') {
      processedValue = parseFloat(value) || 0
    } else if (fieldConfig[columnId]?.type === 'number') {
      processedValue = value !== '' && value !== null ? parseInt(value) : null
    } else if (fieldConfig[columnId]?.type === 'date') {
      processedValue = value || null
    }

    const updatedDeal = await crmApiClient.put(`/deals/${dealId}`, {
      [fieldName]: processedValue,
    })

    // Backend returns the full deal with clientName and salesmanName populated via JOIN
    setDeals(
      (prev: Deal[]) =>
        prev.map((d: Deal) => (d.dealId === dealId || d.id === dealId ? updatedDeal : d)) as Deal[]
    )
  }

  // TanStack Table instance
  const table = useReactTable({
    data: filteredDeals,
    columns: columns as any,
    state: {
      sorting,
      columnVisibility,
      rowSelection: Array.from(selectedDealIds).reduce(
        (acc, id) => {
          const rowIndex = filteredDeals.findIndex((d) => String(d.dealId || d.id) === id)
          if (rowIndex !== -1) acc[rowIndex] = true
          return acc
        },
        {} as Record<string, boolean>
      ),
    },
    onSortingChange: setSorting,
    onColumnVisibilityChange: setColumnVisibility,
    onRowSelectionChange: (updater) => {
      const newSelection =
        typeof updater === 'function' ? updater(table.getState().rowSelection) : updater
      const newSelectedIds = new Set(
        Object.keys(newSelection)
          .map((index) => {
            const deal = filteredDeals[parseInt(index)]
            return deal ? String(deal.dealId || deal.id) : ''
          })
          .filter(Boolean)
      )
      if (onSelectionChange) {
        onSelectionChange(newSelectedIds)
      }
    },
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: {
      pagination: {
        pageSize: DEALS_PER_PAGE,
      },
    },
    meta: {
      updateData,
      onSaveSuccess: (_columnId: string) => {
        toast(t('toasts.success'), { description: t('dealToasts.dealUpdated') })
      },
      onSaveError: (_columnId: string, error: Error) => {
        toast.error(t('toasts.error'), {
          description: error.message || t('dealToasts.updateFailed'),
        })
      },
    },
  })

  // Load employees on mount
  useEffect(() => {
    loadEmployees()
  }, [loadEmployees])

  // Force-refresh deals on mount so newly-arrived storefront quote-requests
  // show up the moment the seller navigates to /crm. CRMContext otherwise
  // serves a 1-hour cache and won't refetch on its own.
  useEffect(() => {
    loadDeals(true)
  }, [loadDeals])

  // Close add-deals dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        addDealsDropdownRef.current &&
        !addDealsDropdownRef.current.contains(event.target as Node)
      ) {
        setShowAddDealsDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Row click handler
  const handleRowClick = (deal: Deal) => {
    const id = deal.dealId ?? deal.id
    if (!id) return
    router.push(`/workspace/${workspaceId}/deals/${id}`)
  }

  // New deal handlers
  const handleAddDeal = () => {
    setIsAddingNewDeal(true)
    setNewDealData({
      dealName: '',
      description: '',
      valueUsd: 0,
      fobPrice: undefined,
      roomStatus: 'draft',
      expectedCloseDate: '',
      clientId: undefined,
      employeeId: undefined,
    })
  }

  const handleSaveNewDeal = async () => {
    if (isSavingNewDeal) return

    try {
      setIsSavingNewDeal(true)

      if (!newDealData.dealName || newDealData.dealName.trim().length < 2) {
        toast.error(t('toasts.validationError'), { description: t('dealValidation.nameRequired') })
        setIsSavingNewDeal(false)
        return
      }

      if (!newDealData.clientId) {
        toast.error(t('toasts.validationError'), {
          description: t('dealValidation.clientRequired'),
        })
        setIsSavingNewDeal(false)
        return
      }

      const payload = {
        dealName: newDealData.dealName,
        description: newDealData.description || '',
        fobPrice: newDealData.fobPrice || null,
        fobCurrency: (newDealData as any).fobCurrency || 'USD',
        roomStatus: newDealData.roomStatus || 'draft',
        expectedCloseDate: newDealData.expectedCloseDate || null,
        clientId: newDealData.clientId,
        employeeId: newDealData.employeeId || (newDealData as any).salesmanId,
      }

      const savedDeal = await crmApiClient.post('/deals', payload)
      setDeals((prev: Deal[]) => [savedDeal, ...prev] as Deal[])
      setIsAddingNewDeal(false)
      setNewDealData({})
      toast(t('toasts.success'), { description: t('dealToasts.dealCreated') })
    } catch (error) {
      toast.error(t('toasts.error'), { description: t('dealToasts.createFailed') })
    } finally {
      setIsSavingNewDeal(false)
    }
  }

  const handleCancelNewDeal = () => {
    setIsAddingNewDeal(false)
    setNewDealData({})
  }

  // Loading / error states — spinner removed; DataTable handles skeleton rows via isLoading prop

  if (dealsError) {
    return (
      <div className="p-3">
        <div className="rounded-lg border border-rule bg-bone p-6">
          <div className="flex items-center gap-3 text-threat">
            <AlertCircle className="h-6 w-6" />
            <div>
              <h3 className="font-semibold">{t('dealList.cannotLoadDeals')}</h3>
              <p className="mt-1 text-sm">{dealsError}</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (deals.length === 0 && !dealsLoading && !isAddingNewDeal) {
    return (
      <EmptyState
        icon={Briefcase}
        title={t('dealList.noDealsYet')}
        description={t('dealList.noDealsYetDescription')}
        action={
          <button
            onClick={handleAddDeal}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" />
            {t('dealList.createDeal')}
          </button>
        }
      />
    )
  }

  // New-row JSX passed to DataTable
  const newRow = isAddingNewDeal ? (
    <tr className="animate-slide-down border-2 border-rule bg-paper">
      {table.getAllLeafColumns().map((column) => {
        if (!column.getIsVisible()) return null

        if (column.id === 'select') {
          return <td key={column.id} className="px-4 py-2"></td>
        }

        if (column.id === 'dealName') {
          return (
            <td key={column.id} className="px-4 py-2">
              <input
                type="text"
                value={newDealData.dealName || ''}
                onChange={(e) => setNewDealData({ ...newDealData, dealName: e.target.value })}
                onBlur={handleSaveNewDeal}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSaveNewDeal()
                  if (e.key === 'Escape') handleCancelNewDeal()
                }}
                placeholder={t('dealColumns.dealName')}
                className="w-full rounded-md border border-rule bg-bone px-2 py-1 text-deep placeholder:italic placeholder:text-mute focus:border-deep focus:outline-none focus:ring-2 focus:ring-accent/20"
                autoFocus
              />
            </td>
          )
        }

        if (column.id === 'description') {
          return (
            <td key={column.id} className="px-4 py-2">
              <input
                type="text"
                value={newDealData.description || ''}
                onChange={(e) => setNewDealData({ ...newDealData, description: e.target.value })}
                placeholder={t('dealColumns.description')}
                className="w-full rounded-md border border-rule bg-bone px-2 py-1 text-deep placeholder:italic placeholder:text-mute focus:border-deep focus:outline-none focus:ring-2 focus:ring-accent/20"
              />
            </td>
          )
        }

        if (column.id === 'valueUsd') {
          const computed = (newDealData.fobPrice ?? 0) * ((newDealData as any).quantity ?? 0)
          return (
            <td key={column.id} className="px-4 py-2">
              <span className="text-sm text-mute">
                {computed ? `US$${computed.toLocaleString()}` : '-'}
              </span>
            </td>
          )
        }

        if (column.id === 'fobPrice') {
          return (
            <td key={column.id} className="px-4 py-2">
              <input
                type="number"
                step="0.01"
                value={newDealData.fobPrice ?? ''}
                onChange={(e) =>
                  setNewDealData({
                    ...newDealData,
                    fobPrice: e.target.value ? parseFloat(e.target.value) : undefined,
                  })
                }
                placeholder={t('dealColumns.fobPrice')}
                className="w-full rounded-md border border-rule bg-bone px-2 py-1 text-deep placeholder:italic placeholder:text-mute focus:border-deep focus:outline-none focus:ring-2 focus:ring-accent/20"
              />
            </td>
          )
        }

        if (column.id === 'roomStatus') {
          return (
            <td key={column.id} className="px-4 py-2">
              <select
                value={newDealData.roomStatus || 'draft'}
                onChange={(e) => setNewDealData({ ...newDealData, roomStatus: e.target.value })}
                className="w-full rounded-md border border-rule bg-bone px-2 py-1 text-deep placeholder:italic placeholder:text-mute focus:border-deep focus:outline-none focus:ring-2 focus:ring-accent/20"
              >
                <option value="draft">{t('dealStages.draft')}</option>
                <option value="sent">{t('dealStages.sent')}</option>
                <option value="viewed">{t('dealStages.viewed')}</option>
                <option value="quote_requested">{t('dealStages.quoteRequested')}</option>
                <option value="closed-won">{t('dealStages.closedWon')}</option>
                <option value="closed-lost">{t('dealStages.closedLost')}</option>
              </select>
            </td>
          )
        }

        if (column.id === 'expectedCloseDate') {
          return (
            <td key={column.id} className="px-4 py-2">
              <input
                type="date"
                value={newDealData.expectedCloseDate || ''}
                onChange={(e) =>
                  setNewDealData({ ...newDealData, expectedCloseDate: e.target.value })
                }
                className="w-full rounded-md border border-rule bg-bone px-2 py-1 text-deep placeholder:italic placeholder:text-mute focus:border-deep focus:outline-none focus:ring-2 focus:ring-accent/20"
              />
            </td>
          )
        }

        if (column.id === 'salesmanName') {
          return (
            <td key={column.id} className="px-4 py-2">
              <select
                value={(newDealData as any).salesmanId || newDealData.employeeId || ''}
                onChange={(e) =>
                  setNewDealData({
                    ...newDealData,
                    employeeId: parseInt(e.target.value),
                    salesmanId: parseInt(e.target.value),
                  } as any)
                }
                className="w-full rounded-md border border-rule bg-bone px-2 py-1 text-deep placeholder:italic placeholder:text-mute focus:border-deep focus:outline-none focus:ring-2 focus:ring-accent/20"
              >
                <option value="">{t('dealList.selectSalesman')}</option>
                {employees?.map((emp) => (
                  <option key={emp.employeeId} value={emp.employeeId}>
                    {emp.name ||
                      `${emp.firstName || ''} ${emp.lastName || ''}`.trim() ||
                      `Employee ${emp.employeeId}`}
                  </option>
                ))}
              </select>
            </td>
          )
        }

        if (column.id === 'clientName') {
          return (
            <td key={column.id} className="px-4 py-2">
              <select
                value={newDealData.clientId || ''}
                onChange={(e) => {
                  setNewDealData({ ...newDealData, clientId: parseInt(e.target.value) })
                  setTimeout(() => handleSaveNewDeal(), 100)
                }}
                onBlur={handleSaveNewDeal}
                className="w-full rounded-md border border-rule bg-bone px-2 py-1 text-deep placeholder:italic placeholder:text-mute focus:border-deep focus:outline-none focus:ring-2 focus:ring-accent/20"
              >
                <option value="">{t('dealList.selectClient')}</option>
                {customers?.map((c) => (
                  <option key={c.id || c.clientId} value={c.id || c.clientId}>
                    {c.company || c.name}
                  </option>
                ))}
              </select>
            </td>
          )
        }

        return <td key={column.id} className="px-4 py-2"></td>
      })}
      <td className="px-4 py-2">
        {isSavingNewDeal && (
          <div className="flex items-center justify-end gap-2">
            <Loader2 className="h-4 w-4 animate-spin text-mute" />
            <span className="text-sm text-mute">{t('dealList.saving')}</span>
          </div>
        )}
      </td>
    </tr>
  ) : undefined

  return (
    <div className="flex flex-col gap-3">
      {/* Toolbar */}
      <div>
        <DataTableToolbar
          table={table}
          fieldConfig={fieldConfig}
          actions={
            <div className="relative" ref={addDealsDropdownRef}>
              <button
                onClick={() => setShowAddDealsDropdown(!showAddDealsDropdown)}
                disabled={!isAuthenticated}
                className="inline-flex h-[34px] items-center justify-center gap-1.5 rounded-lg border border-deep bg-deep px-3.5 text-[13px] font-medium leading-none text-bone transition-colors duration-150 hover:border-accent hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Plus className="h-3.5 w-3.5" />
                {t('dealList.addDeals')}
                <ChevronDown
                  className={`h-3 w-3 opacity-70 transition-transform ${showAddDealsDropdown ? 'rotate-180' : ''}`}
                />
              </button>

              {showAddDealsDropdown && (
                <div className="absolute top-full left-0 z-50 mt-2 w-56 rounded-lg border border-rule bg-bone shadow-lg">
                  <div className="py-1">
                    <button
                      onClick={() => {
                        handleAddDeal()
                        setShowAddDealsDropdown(false)
                      }}
                      className="flex w-full items-center gap-3 px-4 py-2.5 text-sm text-ink transition-colors hover:bg-cream"
                    >
                      <Plus className="h-4 w-4" />
                      <span className="font-medium">{t('dealList.addButton')}</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          }
          search={
            <SearchBarWithColumns
              value={searchTerm}
              onChange={setSearchTerm}
              onClear={() => setSearchTerm('')}
              searchColumns={searchColumns}
              onColumnChange={(cols) => setSearchColumns(cols as any)}
              availableColumns={[
                { key: 'dealName', label: t('dealColumns.dealName'), icon: Building },
                { key: 'description', label: t('dealColumns.description'), icon: FileText },
                { key: 'clientName', label: t('dealColumns.client'), icon: Building2 },
                { key: 'salesmanName', label: t('dealColumns.salesman'), icon: User },
              ]}
              placeholder={t('dealList.searchPlaceholder')}
            />
          }
          filters={
            <FilterDropdown
              columns={[
                { id: 'dealName', label: t('dealColumns.dealName'), type: 'text' },
                { id: 'description', label: t('dealColumns.description'), type: 'text' },
                { id: 'valueUsd', label: t('dealColumns.value'), type: 'currency' },
                {
                  id: 'roomStatus',
                  label: t('dealColumns.roomStatus'),
                  type: 'select',
                  options: fieldConfig.roomStatus.options?.map((o) => ({
                    value: String(o.value),
                    label: o.label,
                  })),
                },
                {
                  id: 'expectedCloseDate',
                  label: t('dealColumns.expectedCloseDate'),
                  type: 'date',
                },
                { id: 'createdAt', label: t('dealColumns.startedTime'), type: 'datetime' },
                { id: 'salesmanName', label: t('dealColumns.assignedSalesman'), type: 'text' },
                { id: 'clientName', label: t('dealColumns.client'), type: 'text' },
              ]}
              onApplyFilters={setColumnFilters}
              activeFilters={columnFilters}
            />
          }
          toggles={[
            {
              key: 'showClosedDeals',
              label: t('dealList.displayClosedDeals'),
              checked: filters.showClosedDeals === 'true',
              onChange: (checked) =>
                setFilters({ ...filters, showClosedDeals: checked ? 'true' : 'false' }),
            },
          ]}
          extraMenuItems={
            <button
              onClick={() => loadDeals(true)}
              disabled={dealsLoading}
              className="flex w-full items-center gap-3 px-4 py-2.5 text-sm text-ink transition-colors hover:bg-cream hover:text-ink disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${dealsLoading ? 'animate-spin' : ''}`} />
              <span className="font-medium">
                {dealsLoading ? t('dealList.refreshing') : t('dealList.refreshData')}
              </span>
            </button>
          }
        />
      </div>

      {/* Table + pagination share one bordered card; scroll at the page level */}
      <div className="overflow-hidden rounded-lg border border-rule">
        <DataTable
          table={table}
          onRowClick={handleRowClick}
          isLoading={dealsLoading}
          compactCells={true}
          emptyState={
            <div className="flex flex-col items-center gap-2 text-mute">
              <Briefcase className="h-8 w-8 text-rule" />
              <p className="text-sm font-medium">{t('dealList.emptyState')}</p>
              <p className="text-xs text-mute">
                {searchTerm
                  ? t('dealList.adjustSearchOrFilters')
                  : t('dealList.addDealsToGetStarted')}
              </p>
            </div>
          }
          newRow={newRow}
          englishColumns={ENGLISH_DATA_COLUMNS}
        />

        <DataTablePagination
          table={table}
          totalItems={filteredDeals.length}
          pageSize={DEALS_PER_PAGE}
          labels={{
            showing: (start, end, total) =>
              t('dealList.pagination.showing', { start, end, total }),
            page: (current, total) => t('dealList.pagination.page', { current, total }),
          }}
        />
      </div>
    </div>
  )
}
