'use client'

import React from 'react'
import { useTranslations } from 'next-intl'
import {
  DollarSign,
  AlertCircle,
  RefreshCw,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { formatRoomStatus as formatRoomStatusLabel } from '@/lib/utils/deal-status'
import { dealStageVariant, getVariant } from '@/lib/colors/status-mappings'
import { signalChipClass } from '@/lib/design/signal'
import type { Customer, Deal } from '@/types/crm'

export interface CustomerDealsTabProps {
  localCustomer: Customer
  deals: Deal[]
  isLoadingDeals: boolean
  dealsError: string
  fetchDeals: () => Promise<void>
}

const CustomerDealsTab: React.FC<CustomerDealsTabProps> = ({
  localCustomer,
  deals,
  isLoadingDeals,
  dealsError,
  fetchDeals,
}) => {
  const t = useTranslations('crm')
  return (
    <div className="space-y-6">
      <div className="mx-auto w-4/5">
        {/* Deals Header */}
        <div className="mb-4 rounded-lg border border-rule bg-bone p-6">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <DollarSign className="h-6 w-6 text-deep" />
              <h3 className="title-panel">
                {t('customerModal.dealsWith', { company: localCustomer.company })}
              </h3>
            </div>
            <button
              onClick={fetchDeals}
              disabled={isLoadingDeals}
              className="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-mute transition-colors hover:bg-cream hover:text-ink disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${isLoadingDeals ? 'animate-spin' : ''}`} />
              {t('customerModal.refresh')}
            </button>
          </div>

          {!isLoadingDeals && !dealsError && deals.length > 0 && (
            <div className="grid grid-cols-3 gap-4 border-t border-rule pt-4">
              <div>
                <span className="text-xs text-mute">
                  {t('customerModal.totalDeals')}
                </span>
                <p className="text-2xl tabular-nums text-deep">{deals.length}</p>
              </div>
              <div>
                <span className="text-xs text-mute">
                  {t('customerModal.totalValue')}
                </span>
                <p className="text-2xl tabular-nums text-deep">
                  $
                  {deals
                    .reduce((sum, deal) => sum + (deal.valueUsd || 0), 0)
                    .toLocaleString()}
                </p>
              </div>
              <div>
                <span className="text-xs text-mute">
                  {t('customerModal.activeDeals')}
                </span>
                <p className="text-2xl tabular-nums text-deep">
                  {
                    deals.filter(
                      (d) => !['closed-won', 'closed-lost'].includes(d.roomStatus || '')
                    ).length
                  }
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Deals Table */}
        {isLoadingDeals ? (
          <div className="rounded-lg border border-rule bg-bone p-8 text-center">
            <div className="flex items-center justify-center gap-3">
              <RefreshCw className="h-5 w-5 animate-spin text-mute" />
              <span className="text-mute">{t('customerModal.loadingDeals')}</span>
            </div>
          </div>
        ) : dealsError ? (
          <div className={`rounded-lg border p-6 text-center ${signalChipClass('threat')}`}>
            <AlertCircle className="mx-auto mb-2 h-6 w-6 text-threat" />
            <span className="text-threat">{dealsError}</span>
          </div>
        ) : deals.length === 0 ? (
          <div className="rounded-lg border border-rule bg-bone p-12 text-center">
            <DollarSign className="mx-auto mb-4 h-12 w-12 text-mute" />
            <p className="mb-2 text-lg text-mute">{t('customerModal.noDeals')}</p>
            <p className="text-sm text-mute">{t('customerModal.noDealsDescription')}</p>
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-rule">
            <table className="w-full bg-bone">
              <thead className="border-b border-rule bg-paper">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-mute uppercase">
                    {t('customerModal.dealTableName')}
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-mute uppercase">
                    {t('customerModal.dealTableValue')}
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-mute uppercase">
                    {t('customerModal.dealTableStage')}
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-mute uppercase">
                    {t('customerModal.dealTableLastContact')}
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-mute uppercase">
                    {t('customerModal.dealTableExpectedClose')}
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-mute uppercase">
                    {t('customerModal.dealTableCreated')}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {deals.map((deal, index) => (
                  <tr
                    key={deal.dealId}
                    className={`transition-colors hover:bg-cream ${index % 2 === 0 ? 'bg-bone' : 'bg-paper'}`}
                  >
                    <td className="px-4 py-3">
                      <div>
                        <p className="text-sm font-medium text-ink">{deal.dealName}</p>
                        {deal.description && (
                          <p className="mt-1 line-clamp-1 text-xs text-mute">
                            {deal.description}
                          </p>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="tabular-nums text-sm font-semibold text-ink">
                        ${deal.valueUsd ? deal.valueUsd.toLocaleString() : '0'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={getVariant(dealStageVariant, deal.roomStatus ?? '')}>
                        {formatRoomStatusLabel(deal.roomStatus, t)}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <span className="tabular-nums text-sm text-ink">
                        {deal.lastContactDate
                          ? new Date(deal.lastContactDate).toLocaleDateString()
                          : '-'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="tabular-nums text-sm text-ink">
                        {deal.expectedCloseDate
                          ? new Date(deal.expectedCloseDate).toLocaleDateString()
                          : '-'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="tabular-nums text-sm text-mute">
                        {deal.createdAt
                          ? new Date(deal.createdAt).toLocaleDateString()
                          : '-'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

export default CustomerDealsTab
