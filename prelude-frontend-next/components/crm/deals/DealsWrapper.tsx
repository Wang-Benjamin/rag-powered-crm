'use client'

import React, { useEffect, useMemo, useState } from 'react'
import { KpiValue } from '@/components/ui/KpiValue'
import { motion } from 'framer-motion'
import { useTranslations } from 'next-intl'
import { toast } from 'sonner'
import DealsTable from '@/components/crm/deals/DealsTable'
import { useCRM } from '@/contexts/CRMContext'
import { Trash2, Loader2 } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogFooter,
} from '@/components/ui/alert-dialog'

interface DealsWrapperProps {
  wsConnection?: {
    isConnected: boolean
    onRetry: () => void
  }
}

const CLOSED_STATUSES = new Set(['closed_won', 'closed_lost', 'won', 'lost', 'closed-won', 'closed-lost'])

// Wrapper component for Deals - CRMProvider is now at App level for shared state with CRM
const DealsWrapper: React.FC<DealsWrapperProps> = ({ wsConnection: _wsConnection }) => {
  const { isLoadedFromCache, deleteDeal, loadDeals, loadCustomers, deals, dealsLoading } = useCRM()
  const t = useTranslations('crm')
  const tc = useTranslations('common')

  useEffect(() => {
    loadDeals()
    loadCustomers()
  }, [loadDeals, loadCustomers])

  // Use faster animation when data is loaded from cache (50ms vs 300ms)
  const animationDuration = isLoadedFromCache ? 0.05 : 0.3

  // Selection state (lifted from table)
  const [selectedDealIds, setSelectedDealIds] = useState(new Set<string>())
  const [showMassDeleteModal, setShowMassDeleteModal] = useState(false)
  const [isDeletingMultiple, setIsDeletingMultiple] = useState(false)

  // KPI metrics derived from loaded deals
  const kpi = useMemo(() => {
    const allDeals = deals ?? []
    const openDeals = allDeals.filter(
      (d) => !CLOSED_STATUSES.has((d.roomStatus ?? '').toLowerCase())
    )
    const pipelineValue = openDeals.reduce((s, d) => s + (d.valueUsd ?? 0), 0)
    const now = new Date()
    const closingThisMonth = allDeals.filter((d) => {
      if (!d.expectedCloseDate) return false
      const dt = new Date(d.expectedCloseDate)
      return dt.getFullYear() === now.getFullYear() && dt.getMonth() === now.getMonth()
    }).length
    const activeRooms = allDeals.filter((d) => (d.viewCount ?? 0) > 0).length
    return { openCount: openDeals.length, pipelineValue, closingThisMonth, activeRooms }
  }, [deals])

  const formatCompact = (value: number) =>
    new Intl.NumberFormat('en-US', {
      notation: 'compact',
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 1,
    }).format(value)

  // Handle mass delete
  const handleMassDelete = async () => {
    setIsDeletingMultiple(true)
    try {
      for (const dealId of selectedDealIds) {
        await deleteDeal(dealId.toString())
      }
      toast(t('toasts.success'), {
        description: t('dealToasts.dealsDeleted', { count: selectedDealIds.size }),
      })
      setSelectedDealIds(new Set())
      setShowMassDeleteModal(false)
    } catch (error: any) {
      toast.error(t('toasts.error'), {
        description: error.message || t('dealToasts.bulkDeleteFailed'),
      })
    } finally {
      setIsDeletingMultiple(false)
    }
  }

  return (
    <div className="flex h-full flex-col">
      {/* Main Content — single overflow-y-auto so the page scrolls as one
          document while the sidebar stays fixed. */}
      <div className="flex-1 overflow-y-auto bg-paper p-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: animationDuration }}
        >
          {/* KPI Strip */}
          <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {/* Open Deals */}
            <div className="flex min-h-[96px] flex-col justify-between rounded-xl border border-rule bg-bone p-5">
              {dealsLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-2.5 w-20" />
                  <Skeleton className="h-9 w-16" />
                  <Skeleton className="h-2.5 w-24" />
                </div>
              ) : (
                <>
                  <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-mute">
                    {t('deals.kpi.open')}
                  </span>
                  <KpiValue>{kpi.openCount}</KpiValue>
                  <span className="text-[12px] leading-[1.35] text-mute">
                    {t('deals.kpi.openSub')}
                  </span>
                </>
              )}
            </div>

            {/* Pipeline Value */}
            <div className="flex min-h-[96px] flex-col justify-between rounded-xl border border-rule bg-bone p-5">
              {dealsLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-2.5 w-20" />
                  <Skeleton className="h-9 w-16" />
                  <Skeleton className="h-2.5 w-24" />
                </div>
              ) : (
                <>
                  <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-mute">
                    {t('deals.kpi.pipeline')}
                  </span>
                  <KpiValue>{formatCompact(kpi.pipelineValue)}</KpiValue>
                  <span className="text-[12px] leading-[1.35] text-mute">
                    {t('deals.kpi.pipelineSub')}
                  </span>
                </>
              )}
            </div>

            {/* Closing This Month */}
            <div className="flex min-h-[96px] flex-col justify-between rounded-xl border border-rule bg-bone p-5">
              {dealsLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-2.5 w-20" />
                  <Skeleton className="h-9 w-16" />
                  <Skeleton className="h-2.5 w-24" />
                </div>
              ) : (
                <>
                  <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-mute">
                    {t('deals.kpi.closingMonth')}
                  </span>
                  <KpiValue accent={kpi.closingThisMonth > 0 ? 'gold' : 'deep'}>
                    {kpi.closingThisMonth}
                  </KpiValue>
                  <span className="text-[12px] leading-[1.35] text-mute">
                    {t('deals.kpi.closingMonthSub')}
                  </span>
                </>
              )}
            </div>

            {/* Active Rooms */}
            <div className="flex min-h-[96px] flex-col justify-between rounded-xl border border-rule bg-bone p-5">
              {dealsLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-2.5 w-20" />
                  <Skeleton className="h-9 w-16" />
                  <Skeleton className="h-2.5 w-24" />
                </div>
              ) : (
                <>
                  <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-mute">
                    {t('deals.kpi.activeRooms')}
                  </span>
                  <KpiValue accent={kpi.activeRooms > 0 ? 'accent' : 'deep'}>
                    {kpi.activeRooms}
                  </KpiValue>
                  <span className="text-[12px] leading-[1.35] text-mute">
                    {t('deals.kpi.activeRoomsSub')}
                  </span>
                </>
              )}
            </div>
          </div>

          <DealsTable
            selectedDealIds={selectedDealIds}
            onSelectionChange={setSelectedDealIds}
          />
        </motion.div>
      </div>

      {/* Mass Delete Confirmation Modal */}
      <AlertDialog open={showMassDeleteModal} onOpenChange={setShowMassDeleteModal}>
        <AlertDialogContent className="border-rule bg-bone">
          <AlertDialogHeader>
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-threat/10">
                <Trash2 className="h-6 w-6 text-threat" />
              </div>
              <div>
                <AlertDialogTitle className="title-page">
                  {t('dealDeleteModal.deleteDealsTitle', { count: selectedDealIds.size })}
                </AlertDialogTitle>
                <AlertDialogDescription className="text-mute">
                  {t('dealDeleteModal.deleteDealsDescription', { count: selectedDealIds.size })}
                </AlertDialogDescription>
              </div>
            </div>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel
              disabled={isDeletingMultiple}
              className="text-mute hover:bg-cream hover:text-deep"
            >
              {tc('cancel')}
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleMassDelete}
              disabled={isDeletingMultiple}
              className="bg-threat text-bone hover:bg-threat/90"
            >
              {isDeletingMultiple ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {t('dealDeleteModal.deleting')}
                </>
              ) : (
                <>
                  <Trash2 className="mr-2 h-4 w-4" />
                  {tc('delete')}
                </>
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Floating Selection Actions Bar */}
      {selectedDealIds.size > 0 && (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 transform">
          <div className="flex items-center gap-4 rounded-lg border border-rule bg-bone px-6 py-3 shadow-xl">
            <span className="text-sm font-medium text-deep">
              {tc('selected', { count: selectedDealIds.size })}
            </span>
            <button
              onClick={() => setShowMassDeleteModal(true)}
              className="inline-flex items-center justify-center rounded-lg bg-threat px-4 py-2 text-sm font-medium text-bone transition-all duration-200 hover:bg-threat/90 active:scale-95"
            >
              <Trash2 className="mr-2 h-4 w-4" />
              {tc('deleteSelected')} ({selectedDealIds.size})
            </button>
            <button
              onClick={() => setSelectedDealIds(new Set())}
              className="rounded-lg px-3 py-2 text-sm font-medium text-mute transition-colors hover:bg-cream hover:text-deep"
            >
              {tc('clear')}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default DealsWrapper
