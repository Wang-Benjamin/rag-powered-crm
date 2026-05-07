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
  Building,
  MapPin,
  Plus,
  Download,
  Users,
  RefreshCw,
  User,
  Mail,
  Loader2,
  AlertTriangle,
  ChevronDown,
} from 'lucide-react'
import { useLeadContext } from '@/contexts/LeadContext'
import { useSubscription } from '@/stores/subscriptionStore'
import {
  usePersistedSearch,
  usePersistedFilters,
  usePersistedColumns,
  usePersistedState,
} from '@/hooks/usePersistedState'
import { useTranslations } from 'next-intl'
import { toast } from 'sonner'
import SearchBarWithColumns from '@/components/ui/data-table/SearchBarWithColumns'
import FilterDropdown from '@/components/ui/data-table/FilterDropdown'
import { EmptyState } from '@/components/ui/states/EmptyState'
import {
  DataTable,
  DataTableToolbar,
  DataTablePagination,
  useTableFiltering,
} from '@/components/ui/data-table'
import leadsApiService from '@/lib/api/leads'
import {
  buildLeadColumns,
  buildLeadFieldConfig,
  getLeadFilterValue,
  ENGLISH_DATA_COLUMNS,
} from './leadColumns'
import type { Lead } from '@/types/leads'

const LEADS_PER_PAGE = 10

interface LeadsTableProps {
  onLeadClick?: (lead: Lead) => void
  selectedLeadIds?: Set<string | number>
  onSelectionChange?: (selectedIds: Set<string | number>) => void
  onAddLead?: () => void
  onExportCsv?: () => void
  onRefresh?: () => void
  isRefreshing?: boolean
}

export default function LeadsTable({
  onLeadClick,
  selectedLeadIds = new Set(),
  onSelectionChange,
  onAddLead,
  onExportCsv,
  onRefresh,
  isRefreshing = false,
}: LeadsTableProps) {
  const { leads, workflowLeads, isLoading, leadsError, updateLead, loadLeads, hasInitialLoad } =
    useLeadContext()
  const { entitlements, fetchSubscription, hasFetched } = useSubscription()
  const t = useTranslations('leads')

  useEffect(() => {
    fetchSubscription()
  }, [fetchSubscription])

  const showBuyerEmails = entitlements.showBuyerEmails
  const tc = useTranslations('common')
  const router = useRouter()
  const params = useParams()
  const workspaceId = params?.workspaceId as string

  // Toolbar dropdown state
  const [showAddLeadsDropdown, setShowAddLeadsDropdown] = useState(false)
  const addLeadsDropdownRef = useRef<HTMLDivElement>(null)

  // New lead state
  const [isAddingNewLead, setIsAddingNewLead] = useState(false)
  const [isSavingNewLead, setIsSavingNewLead] = useState(false)
  const [newLeadData, setNewLeadData] = useState<Partial<Lead>>({})

  // Persisted state — same cookie keys as original
  const { searchTerm, setSearchTerm, searchColumns, setSearchColumns } = usePersistedSearch(
    'lead',
    {
      term: '',
      columns: { company: true, name: true, email: true, location: true },
    }
  )

  const [filters] = usePersistedFilters('lead', {
    status: 'all',
  })

  const [columnFilters, setColumnFilters] = usePersistedState<Record<string, any>>(
    'prelude_advfilter_leads',
    {},
    { expires: 365 }
  )

  const [sorting, setSorting] = usePersistedState<SortingState>(
    'prelude_sort_leads',
    [{ id: 'score', desc: true }],
  )
  const [columnVisibility, setColumnVisibility] = usePersistedColumns('leads', {
    location: false,
  })

  // Field configuration
  const fieldConfig = useMemo(() => buildLeadFieldConfig(t as any), [t])

  // All leads combined
  const allLeads = useMemo(() => [...leads, ...workflowLeads], [leads, workflowLeads])

  // Stable callback refs for useTableFiltering (TanStack requires stable data references)
  const preFilters = useCallback(
    (data: Lead[]) => {
      if (filters.status && filters.status !== 'all') {
        return data.filter((lead) => lead.status === filters.status)
      }
      return data
    },
    [filters.status]
  )

  const getSearchValue = useCallback(
    (row: Lead, columnId: string): string | null => {
      if (columnId === 'email') {
        return row.personnel?.[0]?.email || null
      }
      return (row as any)[columnId] ?? null
    },
    []
  )

  // Filtered data via shared hook
  const filteredData = useTableFiltering(allLeads, {
    searchTerm,
    searchColumns,
    columnFilters,
    fieldConfig,
    preFilters,
    getSearchValue,
    getFilterValue: getLeadFilterValue,
  })

  // Column definitions
  const columns = useMemo(
    () =>
      buildLeadColumns({
        t: t as any,
        router,
        workspaceId,
        fieldConfig,
        showBuyerEmails,
      }),
    [t, router, workspaceId, fieldConfig, showBuyerEmails]
  )

  // updateData — uses row.original.id (not row.index) to identify the lead
  const updateData = async (row: Row<Lead>, columnId: string, value: any) => {
    const lead = row.original
    if (!lead) return
    // Find the full lead object (may be workflow lead)
    const fullLead = allLeads.find(
      (l) => String(l.id) === String(lead.id) || String((l as any).leadId) === String(lead.id)
    )
    if (!fullLead) {
      throw new Error('Lead not found')
    }
    await updateLead({ ...fullLead, [columnId]: value })
  }

  const displayData = filteredData
  const blurredIds = useMemo(
    () => new Set(displayData.filter((l) => l.isBlurred).map((l) => l.id)),
    [displayData]
  )

  // TanStack Table instance
  const table = useReactTable({
    data: displayData,
    columns: columns as any,
    state: {
      sorting,
      columnVisibility,
      rowSelection: Array.from(selectedLeadIds).reduce(
        (acc, id) => {
          const rowIndex = displayData.findIndex((lead) => lead.id === id)
          if (rowIndex !== -1) acc[rowIndex] = true
          return acc
        },
        {} as Record<string, boolean>
      ),
    },
    enableSorting: true,
    onSortingChange: setSorting,
    onColumnVisibilityChange: setColumnVisibility,
    onRowSelectionChange: (updater) => {
      const newSelection =
        typeof updater === 'function' ? updater(table.getState().rowSelection) : updater
      const newSelectedIds = new Set(
        Object.keys(newSelection)
          .map((index) => displayData[parseInt(index)]?.id)
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
    enableRowSelection: true,
    initialState: {
      pagination: {
        pageSize: LEADS_PER_PAGE,
      },
    },
    meta: {
      updateData,
      onSaveSuccess: (_columnId: string) => {
        toast(t('toasts.success'), { description: t('toasts.fieldSaved') })
      },
      onSaveError: (_columnId: string, error: Error) => {
        toast.error(t('toasts.error'), {
          description: error.message || t('toasts.fieldSaveFailed'),
        })
      },
    },
  })


  // Close add-leads dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        addLeadsDropdownRef.current &&
        !addLeadsDropdownRef.current.contains(event.target as Node)
      ) {
        setShowAddLeadsDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Row click handler
  const handleRowClick = (lead: Lead) => {
    const leadId = (lead as any).leadId || lead.id
    router.push(`/workspace/${workspaceId}/leads/${leadId}`)
    if (onLeadClick) onLeadClick(lead)
  }

  // New lead handlers
  const handleAddLead = () => {
    setIsAddingNewLead(true)
    setNewLeadData({
      company: '',
      location: '',
      industry: '',
      website: '',
      status: 'new',
    })
  }

  const handleSaveNewLead = async () => {
    if (isSavingNewLead) return
    try {
      setIsSavingNewLead(true)
      if (!newLeadData.company || newLeadData.company.trim().length < 2) {
        toast.error(t('toasts.validationError'), { description: t('validation.companyRequired') })
        setIsSavingNewLead(false)
        return
      }
      const leadPayload = {
        company: newLeadData.company,
        location: newLeadData.location || undefined,
        industry: (newLeadData as any).industry || undefined,
        website: (newLeadData as any).website || undefined,
        status: newLeadData.status || 'new',
        source: 'manual_entry',
      }
      await leadsApiService.createLead(leadPayload as any)
      toast(t('toasts.success'), { description: t('toasts.leadCreated') })
      setIsAddingNewLead(false)
      setNewLeadData({})
      await loadLeads(true)
    } catch (error: any) {
      toast.error(t('toasts.error'), { description: error.message || t('toasts.createFailed') })
    } finally {
      setIsSavingNewLead(false)
    }
  }

  const handleCancelNewLead = () => {
    setIsAddingNewLead(false)
    setNewLeadData({})
  }

  // Loading / error / empty states
  if ((isLoading && !hasInitialLoad) || !hasFetched) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-mute" />
      </div>
    )
  }

  if (leadsError) {
    return (
      <div className="rounded-lg border border-rule bg-bone p-6">
        <div className="flex items-center gap-3 text-threat">
          <AlertTriangle className="h-6 w-6" />
          <div>
            <h3 className="font-semibold">{t('leadList.cannotLoadLeads')}</h3>
            <p className="mt-1 text-sm">{leadsError}</p>
          </div>
        </div>
      </div>
    )
  }

  if (leads.length === 0 && workflowLeads.length === 0 && !isLoading) {
    return (
      <EmptyState
        icon={Users}
        title={t('leadList.emptyState')}
        description={t('leadList.emptyStateDescription')}
        action={
          onAddLead ? (
            <button
              onClick={onAddLead}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              <Plus className="h-4 w-4" />
              {t('leadList.addButton')}
            </button>
          ) : undefined
        }
      />
    )
  }

  // New-row JSX passed to DataTable
  const newRow = isAddingNewLead ? (
    <tr className="animate-slide-down border-2 border-rule bg-paper">
      {table.getAllLeafColumns().map((column) => {
        if (!column.getIsVisible()) return null

        if (column.id === 'select') {
          return <td key={column.id} className="px-4 py-2"></td>
        }

        if (column.id === 'company') {
          return (
            <td key={column.id} className="px-4 py-2">
              <input
                type="text"
                value={newLeadData.company || ''}
                onChange={(e) => setNewLeadData({ ...newLeadData, company: e.target.value })}
                onBlur={handleSaveNewLead}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSaveNewLead()
                  if (e.key === 'Escape') handleCancelNewLead()
                }}
                placeholder={t('leadForm.companyPlaceholder')}
                className="w-full rounded border border-rule px-2 py-1"
                autoFocus
                disabled={isSavingNewLead}
              />
            </td>
          )
        }

        if (column.id === 'location') {
          return (
            <td key={column.id} className="px-4 py-2">
              <input
                type="text"
                value={(newLeadData as any).location || ''}
                onChange={(e) => setNewLeadData({ ...newLeadData, location: e.target.value })}
                onBlur={handleSaveNewLead}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSaveNewLead()
                  if (e.key === 'Escape') handleCancelNewLead()
                }}
                placeholder={t('leadForm.locationPlaceholder')}
                className="w-full rounded border border-rule px-2 py-1"
                disabled={isSavingNewLead}
              />
            </td>
          )
        }

        if (column.id === 'industry') {
          return (
            <td key={column.id} className="px-4 py-2">
              <input
                type="text"
                value={(newLeadData as any).industry || ''}
                onChange={(e) => setNewLeadData({ ...newLeadData, industry: e.target.value })}
                onBlur={handleSaveNewLead}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSaveNewLead()
                  if (e.key === 'Escape') handleCancelNewLead()
                }}
                placeholder={t('leadForm.industryPlaceholder')}
                className="w-full rounded border border-rule px-2 py-1"
                disabled={isSavingNewLead}
              />
            </td>
          )
        }

        if (column.id === 'website') {
          return (
            <td key={column.id} className="px-4 py-2">
              <input
                type="text"
                value={(newLeadData as any).website || ''}
                onChange={(e) => setNewLeadData({ ...newLeadData, website: e.target.value })}
                onBlur={handleSaveNewLead}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSaveNewLead()
                  if (e.key === 'Escape') handleCancelNewLead()
                }}
                placeholder={t('leadForm.websitePlaceholder')}
                className="w-full rounded border border-rule px-2 py-1"
                disabled={isSavingNewLead}
              />
            </td>
          )
        }

        if (column.id === 'status') {
          return (
            <td key={column.id} className="px-4 py-2">
              <select
                value={(newLeadData as any).status || 'new'}
                onChange={(e) => {
                  setNewLeadData({ ...newLeadData, status: e.target.value })
                  setTimeout(() => handleSaveNewLead(), 100)
                }}
                onBlur={handleSaveNewLead}
                className="w-full rounded border border-rule px-2 py-1"
                disabled={isSavingNewLead}
              >
                <option value="new">{t('status.new')}</option>
                <option value="synced_to_crm">{t('status.synced_to_crm')}</option>
                <option value="qualified">{t('status.qualified')}</option>
                <option value="not_interested">{t('status.not_interested')}</option>
              </select>
            </td>
          )
        }

        return (
          <td key={column.id} className="px-4 py-2">
            -
          </td>
        )
      })}
      <td className="px-4 py-2">
        {isSavingNewLead && (
          <div className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin text-mute" />
            <span className="text-sm text-mute">{tc('save')}...</span>
          </div>
        )}
      </td>
    </tr>
  ) : undefined

  const STATUS_OPTIONS = [
    { value: 'new', label: t('status.new') },
    { value: 'synced_to_crm', label: t('status.synced_to_crm') },
    { value: 'qualified', label: t('status.qualified') },
    { value: 'not_interested', label: t('status.not_interested') },
  ]

  return (
    <div className="flex flex-col gap-3">
      {/* Toolbar */}
      <div>
        <DataTableToolbar
          table={table}
          fieldConfig={fieldConfig}
          actions={
            <div className="relative" ref={addLeadsDropdownRef}>
              <button
                onClick={() => setShowAddLeadsDropdown(!showAddLeadsDropdown)}
                disabled={isLoading}
                className="inline-flex h-[34px] items-center justify-center gap-1.5 rounded-lg border border-deep bg-deep px-3.5 text-[13px] font-medium leading-none text-bone transition-colors duration-150 hover:border-accent hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Plus className="h-3.5 w-3.5" />
                {t('leadList.manageButton')}
                <ChevronDown
                  className={`h-3 w-3 opacity-70 transition-transform ${showAddLeadsDropdown ? 'rotate-180' : ''}`}
                />
              </button>

              {showAddLeadsDropdown && (
                <div className="absolute top-full left-0 z-50 mt-2 w-56 rounded-lg border border-rule bg-bone shadow-lg">
                  <div className="py-1">
                    <button
                      onClick={() => {
                        handleAddLead()
                        setShowAddLeadsDropdown(false)
                      }}
                      className="flex w-full items-center gap-3 px-4 py-2.5 text-sm text-ink transition-colors hover:bg-cream"
                    >
                      <Plus className="h-4 w-4" />
                      <span className="font-medium">{t('leadList.addButton')}</span>
                    </button>
                    {onExportCsv && (
                      <button
                        onClick={() => {
                          onExportCsv()
                          setShowAddLeadsDropdown(false)
                        }}
                        disabled={isLoading}
                        className="flex w-full items-center gap-3 px-4 py-2.5 text-sm text-ink transition-colors hover:bg-cream disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <Download className="h-4 w-4" />
                        <span className="font-medium">{t('leadList.exportButton')}</span>
                      </button>
                    )}
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
                { key: 'company', label: t('leadColumns.company'), icon: Building },
                { key: 'name', label: t('leadColumns.name'), icon: User },
                { key: 'email', label: t('leadColumns.email'), icon: Mail },
                { key: 'location', label: t('leadColumns.location'), icon: MapPin },
              ]}
              placeholder={t('leadList.searchPlaceholder')}
            />
          }
          filters={
            <FilterDropdown
              columns={[
                { id: 'company', label: t('leadColumns.company'), type: 'text' },
                { id: 'shipmentVolume', label: t('leadColumns.shipmentVolume'), type: 'number' },
                { id: 'supplierCount', label: t('leadColumns.supplierCount'), type: 'number' },
                { id: 'lastShipment', label: t('leadColumns.lastShipment'), type: 'number' },
                { id: 'trend', label: t('leadColumns.trend'), type: 'number' },
                { id: 'score', label: t('leadColumns.score'), type: 'number' },
                {
                  id: 'status',
                  label: t('leadColumns.status'),
                  type: 'select',
                  options: STATUS_OPTIONS.map((opt) => ({ value: opt.value, label: opt.label })),
                },
              ]}
              onApplyFilters={setColumnFilters}
              activeFilters={columnFilters}
            />
          }
          extraMenuItems={
            onRefresh ? (
              <button
                onClick={onRefresh}
                disabled={isRefreshing}
                className="flex w-full items-center gap-3 px-4 py-2.5 text-sm text-ink transition-colors hover:bg-cream disabled:opacity-50"
              >
                <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
                <span className="font-medium">
                  {isRefreshing
                    ? `${t('leadList.refreshButton')}...`
                    : t('leadList.refreshButton')}
                </span>
              </button>
            ) : undefined
          }
        />
      </div>

      {/* Table + pagination share one bordered card; scroll lives at the page
          level so sidebar + toolbar chrome stay anchored and the whole document
          scrolls as one editorial surface (matches Buyers.html tbl-wrap). */}
      <div className="overflow-hidden rounded-lg border border-rule">
        <DataTable
          table={table}
          compactCells
          onRowClick={(lead: Lead) => {
            if (blurredIds.has(lead.id)) return
            handleRowClick(lead)
          }}
          getRowClassName={(lead: Lead) =>
            blurredIds.has(lead.id)
              ? 'pointer-events-none select-none cursor-not-allowed bg-paper/50 [&_td]:blur-[4px]'
              : ''
          }
          isLoading={isLoading && !hasInitialLoad}
          emptyState={
            <div className="flex flex-col items-center gap-2 text-mute">
              <Users className="h-8 w-8 text-mute" />
              <p className="text-sm font-medium">{t('leadList.emptyState')}</p>
              <p className="text-xs text-mute">
                {searchTerm
                  ? t('emailTimeline.adjustSearch')
                  : t('leadList.emptyStateDescription')}
              </p>
            </div>
          }
          newRow={newRow}
          englishColumns={ENGLISH_DATA_COLUMNS}
        />

        <DataTablePagination
          table={table}
          totalItems={displayData.length}
          pageSize={LEADS_PER_PAGE}
          labels={{
            showing: (start, end, total) =>
              t('leadList.pagination.showing', { start, end, total }),
            page: (current, total) =>
              t('leadList.pagination.page', { current, total }),
          }}
        />
      </div>
    </div>
  )
}
