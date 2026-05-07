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
  Mail,
  Upload,
  AlertCircle,
  Loader2,
  ChevronDown,
  Users,
  User,
} from 'lucide-react'
import { useCRM } from '@/contexts/CRMContext'
import { useAuth } from '@/hooks/useAuth'
import {
  usePersistedSearch,
  usePersistedFilters,
  usePersistedColumns,
  usePersistedState,
} from '@/hooks/usePersistedState'
import { useTranslations, useLocale } from 'next-intl'
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
import { buildCustomerColumns, buildCustomerFieldConfig, ENGLISH_DATA_COLUMNS } from './customerColumns'
import type { Customer } from '@/types/crm'

const CUSTOMERS_PER_PAGE = 10

interface CustomersTableProps {
  onSyncEmails?: () => void
  isSyncingEmails?: boolean
  onCsvUpload?: () => void
  selectedCustomerIds?: Set<string>
  onSelectionChange?: (selectedIds: Set<string>) => void
}

export default function CustomersTable({
  onSyncEmails,
  isSyncingEmails,
  onCsvUpload,
  selectedCustomerIds = new Set(),
  onSelectionChange,
}: CustomersTableProps) {
  const {
    customers,
    customersLoading,
    customersError,
    loadCustomers,
    setCustomers,
    addCustomer,
    hasInitialLoad,
  } = useCRM()
  const { isAuthenticated } = useAuth()
  const t = useTranslations('crm')
  const tc = useTranslations('common')
  const locale = useLocale()
  const router = useRouter()
  const params = useParams()
  const workspaceId = params?.workspaceId as string

  // New customer state
  const [isAddingNewCustomer, setIsAddingNewCustomer] = useState(false)
  const [isSavingNewCustomer, setIsSavingNewCustomer] = useState(false)
  const [newCustomerData, setNewCustomerData] = useState<Partial<Customer>>({})

  // Toolbar dropdown state
  const [showAddCustomersDropdown, setShowAddCustomersDropdown] = useState(false)
  const addCustomersDropdownRef = useRef<HTMLDivElement>(null)

  // Persisted state — same cookie keys as original
  const { searchTerm, setSearchTerm, searchColumns, setSearchColumns } = usePersistedSearch(
    'customers',
    {
      term: '',
      columns: { company: true, contactName: true, email: true },
    }
  )

  const [filters, setFilters] = usePersistedFilters('customers', {
    showInactive: 'true',
  })

  const [columnFilters, setColumnFilters] = usePersistedState<Record<string, any>>(
    'prelude_advfilter_customers',
    {},
    { expires: 365 }
  )

  const [sorting, setSorting] = usePersistedState<SortingState>('prelude_sort_customers', [])
  const [columnVisibility, setColumnVisibility] = usePersistedColumns('customers', {})

  // Field configuration
  const fieldConfig = useMemo(() => buildCustomerFieldConfig(t as any), [t])

  // Stable callback refs for useTableFiltering (TanStack requires stable data references)
  const preFilters = useCallback(
    (data: Customer[]) => {
      if (filters.showInactive !== 'true') {
        return data.filter(
          (c) => c.status !== 'inactive' && c.status !== 'lost'
        )
      }
      return data
    },
    [filters.showInactive]
  )

  const getSearchValue = useCallback(
    (row: Customer, columnId: string): string | null => {
      switch (columnId) {
        case 'contactName':
          return row.personnel?.[0]?.fullName || row.personnel?.[0]?.firstName || null
        case 'email':
          return row.personnel?.[0]?.email || row.clientEmail || null
        default:
          return (row as any)[columnId] ?? null
      }
    },
    []
  )

  // Filtered data via shared hook
  const filteredCustomers = useTableFiltering(customers ?? [], {
    searchTerm,
    searchColumns,
    columnFilters,
    fieldConfig,
    preFilters,
    getSearchValue,
  })

  // Column definitions
  const columns = useMemo(
    () =>
      buildCustomerColumns({
        t: t as any,
        tc: tc as any,
        locale,
        router,
        workspaceId,
        fieldConfig,
      }),
    [t, tc, locale, router, workspaceId, fieldConfig]
  )

  // updateData — full consumer-specific logic preserved from original
  const updateData = async (row: Row<Customer>, columnId: string, value: any) => {
    const customer = row.original
    if (!customer) return

    const personnelFields: Record<string, string> = {
      contactName: 'fullName',
      email: 'email',
    }

    if (columnId in personnelFields) {
      const primaryContact = customer.personnel?.[0]
      if (primaryContact?.personnelId) {
        const contactPayload = {
          name:
            columnId === 'contactName'
              ? value
              : primaryContact.fullName || primaryContact.firstName || '',
          email: columnId === 'email' ? value : primaryContact.email || '',
          phone: primaryContact.phone || '',
          isPrimary: primaryContact.isPrimary ?? true,
        }
        await crmApiClient.put(
          `/customers/${customer.id}/contacts/${primaryContact.personnelId}`,
          contactPayload
        )
        setCustomers((prev) =>
          prev.map((c) => {
            if (c.id !== customer.id) return c
            const updatedPersonnel = [...(c.personnel || [])]
            if (updatedPersonnel[0]) {
              updatedPersonnel[0] = {
                ...updatedPersonnel[0],
                [personnelFields[columnId]]: value,
              }
            }
            return { ...c, personnel: updatedPersonnel }
          })
        )
      } else {
        // No personnel yet — create one
        const newName = columnId === 'contactName' ? value : customer.company || 'Contact'
        const newEmail =
          columnId === 'email'
            ? value
            : `contact@${(customer.company || 'company').toLowerCase().replace(/[^a-z0-9]/g, '')}.com`
        const contactPayload = {
          name: newName,
          email: newEmail,
          phone: '',
          isPrimary: true,
        }
        await crmApiClient.post(`/customers/${customer.id}/contacts`, contactPayload)
        await loadCustomers(true)
      }
    } else {
      const updatedCustomer = await crmApiClient.put(`/customers/${customer.id}`, {
        [columnId]: value,
      })
      setCustomers((prev) => prev.map((c) => (c.id === customer.id ? updatedCustomer : c)))
    }
  }

  // TanStack Table instance
  const table = useReactTable({
    data: filteredCustomers,
    columns: columns as any,
    state: {
      sorting,
      columnVisibility,
      rowSelection: Array.from(selectedCustomerIds).reduce(
        (acc, id) => {
          const rowIndex = filteredCustomers.findIndex((c) => String(c.id) === id)
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
            const customer = filteredCustomers[parseInt(index)]
            return customer ? String(customer.id) : ''
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
        pageSize: CUSTOMERS_PER_PAGE,
      },
    },
    meta: {
      updateData,
      onSaveSuccess: (_columnId: string) => {
        toast(t('toasts.success'), { description: t('toasts.customerUpdated') })
      },
      onSaveError: (_columnId: string, error: Error) => {
        toast.error(t('toasts.error'), {
          description: error.message || t('toasts.updateFailed'),
        })
      },
    },
  })

  // Close add-customers dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        addCustomersDropdownRef.current &&
        !addCustomersDropdownRef.current.contains(event.target as Node)
      ) {
        setShowAddCustomersDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Row click handler
  const handleRowClick = (customer: Customer) => {
    router.push(`/workspace/${workspaceId}/crm/${customer.id}`)
  }

  // New customer handlers
  const handleAddCustomer = () => {
    setIsAddingNewCustomer(true)
    setNewCustomerData({ company: '', stage: 'new' })
  }

  const handleSaveNewCustomer = async () => {
    if (isSavingNewCustomer) return
    try {
      setIsSavingNewCustomer(true)
      if (!newCustomerData.company || newCustomerData.company.trim().length < 2) {
        toast.error(t('toasts.validationError'), { description: t('validation.companyRequired') })
        setIsSavingNewCustomer(false)
        return
      }
      const customerPayload = {
        name: newCustomerData.company,
        stage: newCustomerData.stage || 'new',
        status: 'active',
      }
      const result = await addCustomer(customerPayload)
      if (result.success) {
        setIsAddingNewCustomer(false)
        setNewCustomerData({})
        toast(t('toasts.success'), { description: t('toasts.customerCreated') })
      } else {
        toast.error(t('toasts.error'), {
          description: result.error || t('toasts.createFailed'),
        })
      }
    } catch (error: any) {
      toast.error(t('toasts.error'), {
        description: error.message || t('toasts.createFailed'),
      })
    } finally {
      setIsSavingNewCustomer(false)
    }
  }

  const handleCancelNewCustomer = () => {
    setIsAddingNewCustomer(false)
    setNewCustomerData({})
  }

  // Loading / error / empty states
  if (customersLoading && !hasInitialLoad) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-mute" />
        <span className="ml-2 text-mute">{t('customerList.loading')}</span>
      </div>
    )
  }

  if (customersError) {
    return (
      <div className="p-3">
        <div className="rounded-lg border-rule bg-bone p-6">
          <div className="flex items-center gap-3 text-threat">
            <AlertCircle className="h-6 w-6" />
            <div>
              <h3 className="font-semibold">{t('errors.loadCustomersFailed')}</h3>
              <p className="mt-1 text-sm">{customersError}</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (customers.length === 0 && !customersLoading) {
    return (
      <EmptyState
        icon={Users}
        title={t('customerList.emptyState')}
        description={t('customerList.emptyStateDescription')}
        action={
          onCsvUpload ? (
            <button
              onClick={onCsvUpload}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              <Upload className="h-4 w-4" />
              {t('customerList.importButton')}
            </button>
          ) : undefined
        }
      />
    )
  }

  // New-row JSX passed to DataTable
  const newRow = isAddingNewCustomer ? (
    <tr className="animate-slide-down border border-rule bg-paper">
      {table.getHeaderGroups()[0]?.headers.map((header) => {
        const columnId = header.column.id

        if (columnId === 'select') {
          return <td key={columnId} className="px-4 py-2"></td>
        }

        const config = fieldConfig[columnId]
        if (!config) {
          return (
            <td key={columnId} className="px-4 py-2">
              -
            </td>
          )
        }

        if (config.readonly) {
          const value = (newCustomerData as any)[columnId]
          let displayValue = value || '-'
          if (config.type === 'select' && value) {
            const option = config.options?.find((opt: any) => opt.value === value)
            displayValue = option?.label || value
          }
          return (
            <td key={columnId} className="px-4 py-2">
              <div className="px-2 py-1 text-sm text-mute italic">{displayValue}</div>
            </td>
          )
        }

        if (config.type === 'select') {
          return (
            <td key={columnId} className="px-4 py-2">
              <select
                value={(newCustomerData as any)[columnId] || config.options?.[0]?.value || ''}
                onChange={(e) => {
                  setNewCustomerData({ ...newCustomerData, [columnId]: e.target.value })
                  setTimeout(() => handleSaveNewCustomer(), 100)
                }}
                onBlur={handleSaveNewCustomer}
                className="w-full rounded border border-rule px-2 py-1"
                disabled={isSavingNewCustomer}
              >
                {config.options?.map((option: any) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </td>
          )
        }

        return (
          <td key={columnId} className="px-4 py-2">
            <input
              type={config.type === 'currency' ? 'number' : config.type || 'text'}
              value={(newCustomerData as any)[columnId] || ''}
              onChange={(e) => {
                const val =
                  config.type === 'currency' ? parseFloat(e.target.value) || 0 : e.target.value
                setNewCustomerData({ ...newCustomerData, [columnId]: val })
              }}
              onBlur={handleSaveNewCustomer}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSaveNewCustomer()
                if (e.key === 'Escape') handleCancelNewCustomer()
              }}
              placeholder={config.label}
              className="w-full rounded border border-rule px-2 py-1"
              autoFocus={columnId === 'company'}
              disabled={isSavingNewCustomer}
            />
          </td>
        )
      })}
      <td className="px-4 py-2">
        {isSavingNewCustomer && (
          <div className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin text-mute" />
            <span className="text-sm text-mute">{t('customerList.saving')}</span>
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
            <div className="relative" ref={addCustomersDropdownRef}>
              <button
                onClick={() => setShowAddCustomersDropdown(!showAddCustomersDropdown)}
                disabled={!isAuthenticated}
                className="inline-flex h-[34px] items-center justify-center gap-1.5 rounded-lg border border-deep bg-deep px-3.5 text-[13px] font-medium leading-none text-bone transition-colors duration-150 hover:border-accent hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Plus className="h-3.5 w-3.5" />
                {t('customerList.addButton')}
                <ChevronDown
                  className={`h-3 w-3 opacity-70 transition-transform ${showAddCustomersDropdown ? 'rotate-180' : ''}`}
                />
              </button>

              {showAddCustomersDropdown && (
                <div className="absolute top-full left-0 z-50 mt-2 w-56 rounded-lg border border-rule bg-bone shadow-lg">
                  <div className="py-1">
                    <button
                      onClick={() => {
                        handleAddCustomer()
                        setShowAddCustomersDropdown(false)
                      }}
                      className="flex w-full items-center gap-3 px-4 py-2.5 text-sm text-ink transition-colors hover:bg-cream"
                    >
                      <Plus className="h-4 w-4" />
                      <span className="font-medium">{t('customerList.addButton')}</span>
                    </button>
                    {onCsvUpload && (
                      <button
                        onClick={() => {
                          onCsvUpload()
                          setShowAddCustomersDropdown(false)
                        }}
                        className="flex w-full items-center gap-3 px-4 py-2.5 text-sm text-ink transition-colors hover:bg-cream"
                      >
                        <Upload className="h-4 w-4" />
                        <span className="font-medium">{tc('uploadCsv')}</span>
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
                { key: 'company', label: t('columns.company'), icon: Building },
                { key: 'contactName', label: t('columns.contactName'), icon: User },
                { key: 'email', label: t('columns.email'), icon: Mail },
              ]}
              placeholder={t('customerList.searchPlaceholder')}
            />
          }
          filters={
            <FilterDropdown
              columns={[
                { id: 'company', label: t('columns.company'), type: 'text' },
                { id: 'contactName', label: t('columns.contactName'), type: 'text' },
                { id: 'email', label: t('columns.email'), type: 'text' },
                {
                  id: 'stage',
                  label: t('columns.stage'),
                  type: 'select',
                  options: fieldConfig.stage.options?.map((o) => ({
                    value: String(o.value),
                    label: o.label,
                  })),
                },
                { id: 'lastActivity', label: t('columns.lastActivity'), type: 'date' },
              ]}
              onApplyFilters={setColumnFilters}
              activeFilters={columnFilters}
            />
          }
          toggles={[
            {
              key: 'showInactive',
              label: t('customerList.displayInactive'),
              checked: filters.showInactive === 'true',
              onChange: (checked) => setFilters({ ...filters, showInactive: checked ? 'true' : 'false' }),
            },
          ]}
          extraMenuItems={
            <>
              {onSyncEmails && (
                <button
                  onClick={onSyncEmails}
                  disabled={isSyncingEmails}
                  className="flex w-full items-center gap-3 px-4 py-2.5 text-sm text-ink transition-colors hover:bg-cream disabled:opacity-50"
                >
                  <Mail className="h-4 w-4" />
                  <span className="font-medium">
                    {isSyncingEmails
                      ? t('customerList.syncingEmails')
                      : t('customerList.syncEmails')}
                  </span>
                </button>
              )}
              <button
                onClick={() => loadCustomers(true)}
                disabled={customersLoading}
                className="flex w-full items-center gap-3 px-4 py-2.5 text-sm text-ink transition-colors hover:bg-cream disabled:opacity-50"
              >
                <RefreshCw className={`h-4 w-4 ${customersLoading ? 'animate-spin' : ''}`} />
                <span className="font-medium">
                  {customersLoading
                    ? t('customerList.refreshing')
                    : t('customerList.refreshData')}
                </span>
              </button>
            </>
          }
        />
      </div>

      {/* Table + pagination share one bordered card; scroll at the page level */}
      <div className="overflow-hidden rounded-lg border border-rule">
        <DataTable
          table={table}
          onRowClick={handleRowClick}
          compactCells={true}
          isLoading={customersLoading && !hasInitialLoad}
          emptyState={
            <div className="flex flex-col items-center gap-2 text-mute">
              <Users className="h-8 w-8 text-mute" />
              <p className="text-sm font-medium">{t('customerList.emptyState')}</p>
              <p className="text-xs text-mute">
                {searchTerm
                  ? t('customerList.adjustSearch')
                  : t('customerList.addToGetStarted')}
              </p>
            </div>
          }
          newRow={newRow}
          englishColumns={ENGLISH_DATA_COLUMNS}
        />

        <DataTablePagination
          table={table}
          totalItems={filteredCustomers.length}
          pageSize={CUSTOMERS_PER_PAGE}
          labels={{
            showing: (start, end, total) => tc('showing', { start, end, total }),
            page: (current, total) => tc('page', { current, total }),
          }}
        />
      </div>
    </div>
  )
}
