'use client'

import React from 'react'
import { useTranslations } from 'next-intl'
import {
  Mail,
  AlertCircle,
  CheckCircle,
  RefreshCw,
  TrendingUp,
  Ship,
  Brain,
  ChevronDown,
  ChevronUp,
  Users,
  Sparkles,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import ActivityPanel from '../interactions/ActivityPanel'
import { signalTextClass } from '@/lib/design/signal'
import type { Customer, Interaction } from '@/types/crm'

interface Contact {
  id: string
  name: string
  email: string
  phone?: string
  title?: string
  notes?: string
  isPrimary?: boolean
}

interface Note {
  id: string
  title?: string
  body?: string
  content?: string
  date: string
  updatedAt?: string
  isStarred?: boolean
  star?: string
  interactionId?: string
  author?: string
  type?: string
}

interface TimelineEvent {
  type: string
  originalType: string
  title: string
  description?: string
  date: string
  employeeName?: string
  metadata?: {
    noteId?: string
    interactionId?: string
    isStarred?: boolean
    star?: string
    theme?: string
    subject?: string
    direction?: string
    sourceName?: string
    sourceType?: string
    fromEmail?: string
    parsedMeetingData?: any
    [key: string]: any
  }
}

interface CustomerEmployee {
  employeeId: number
  name: string
  email: string
  role: string
  department: string
}

export interface CustomerOverviewTabProps {
  localCustomer: Customer
  contacts: Contact[]
  customerEmployees: CustomerEmployee[]
  renderEditableField: (
    fieldName: string,
    displayValue: string | null | undefined,
    placeholder?: string,
    isSelect?: boolean,
    options?: Array<{ value: string; label: string }>,
    actualValue?: string | number | null
  ) => React.ReactNode
  handleOpenContactsModal: () => void
  setShowEmployeesModal: (open: boolean) => void
  customerInteractions: Interaction[]
  loadingInteractions: boolean
  timelineFilter: string
  setTimelineFilter: (filter: string) => void
  timelineSearch: string
  setTimelineSearch: (search: string) => void
  isTimelineExpanded: boolean
  handleTimelineToggle: () => void
  expandedPanel: string | null
  setExpandedPanel: (panel: string | null) => void
  handleEventClick: (event: TimelineEvent) => void
  getTimelineEvents: () => TimelineEvent[]
  handleNoteAdded: () => Promise<void>
  handleInteractionAdded: () => Promise<void>
  notes: Note[]
  isLoadingNotes: boolean
  isRefreshingNotes: boolean
  handleDeleteNote: (noteId: string) => Promise<void>
  handleToggleNoteStar: (noteId: string, currentStarStatus?: string) => Promise<void>
  isDeletingNote: string | null
  selectedEmployeeId: number | null
  handleEmployeeFilterChange: (empId: number | null) => void
  currentUserEmployeeId: number | undefined
  isGeneratingSummary: boolean
  handleGenerateSummary: () => Promise<void>
  cachedSummary: any
  summaryError: string
}

const CustomerOverviewTab: React.FC<CustomerOverviewTabProps> = ({
  localCustomer,
  contacts,
  customerEmployees,
  renderEditableField,
  handleOpenContactsModal,
  setShowEmployeesModal,
  customerInteractions,
  loadingInteractions,
  timelineFilter,
  setTimelineFilter,
  timelineSearch,
  setTimelineSearch,
  isTimelineExpanded,
  handleTimelineToggle,
  expandedPanel,
  setExpandedPanel,
  handleEventClick,
  getTimelineEvents,
  handleNoteAdded,
  handleInteractionAdded,
  notes,
  isLoadingNotes,
  isRefreshingNotes,
  handleDeleteNote,
  handleToggleNoteStar,
  isDeletingNote,
  selectedEmployeeId,
  handleEmployeeFilterChange,
  currentUserEmployeeId,
  isGeneratingSummary,
  handleGenerateSummary,
  cachedSummary,
  summaryError,
}) => {
  const t = useTranslations('crm')
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-10">
      {/* Right Column - Customer Information */}
      <div className="lg:order-2 lg:col-span-3">
        <div className="divide-y divide-rule rounded-lg border border-rule bg-bone px-5">
          {/* Customer Info section */}
          <section className="flex flex-col gap-3 py-5">
            <h4 className="font-mono text-[11px] uppercase tracking-[0.1em] text-mute">
              {t('customerModal.customerInfo')}
            </h4>
            <div className="space-y-3">
              <div>
                <label className="mb-1 block font-mono text-[11px] uppercase tracking-[0.1em] text-mute">
                  {t('customerForm.company')}
                </label>
                <div lang="en" translate="no">
                  {renderEditableField(
                    'company',
                    localCustomer.company,
                    t('customerForm.companyPlaceholder')
                  )}
                </div>
              </div>
              <div>
                <label className="mb-1 block font-mono text-[11px] uppercase tracking-[0.1em] text-mute">
                  {t('customerForm.location')}
                </label>
                <div lang="en" translate="no">
                  {renderEditableField(
                    'location',
                    localCustomer.location,
                    t('customerForm.location')
                  )}
                </div>
              </div>
            </div>
          </section>

          {/* Contacts section */}
          <section className="flex flex-col gap-3 py-5">
            <div className="flex items-center justify-between">
              <h4 className="font-mono text-[11px] uppercase tracking-[0.1em] text-mute">
                {t('customerModal.contacts')}
              </h4>
              <button
                onClick={handleOpenContactsModal}
                className="flex items-center gap-1 rounded px-2 py-1 text-xs text-ink transition-colors hover:bg-cream hover:text-ink"
              >
                <Users className="h-3.5 w-3.5" />
                <span className="tabular-nums">
                  {contacts.length > 0
                    ? t('customerModal.contactsCount', { count: contacts.length })
                    : t('customerModal.view')}
                </span>
              </button>
            </div>
            {contacts.length > 0 && (() => {
              const primary = contacts.find(c => c.isPrimary) || contacts[0]
              return (
                <div>
                  <p className="text-sm font-medium text-ink">{primary.name}</p>
                  {primary.title && (
                    <p className="mt-0.5 text-[11px] text-mute">{primary.title}</p>
                  )}
                  {primary.email && (
                    <p className="mt-0.5 flex items-center gap-1 text-[11px] text-mute">
                      <Mail className="h-3 w-3" />
                      {primary.email}
                    </p>
                  )}
                </div>
              )
            })()}
          </section>

          {/* Assigned Employee section */}
          <section className="flex flex-col gap-3 py-5">
            <div className="flex items-center justify-between">
              <h4 className="font-mono text-[11px] uppercase tracking-[0.1em] text-mute">
                {t('customerModal.assignedEmployee')}
              </h4>
              <button
                onClick={() => setShowEmployeesModal(true)}
                className="flex items-center gap-1 rounded px-2 py-1 text-xs text-ink transition-colors hover:bg-cream hover:text-ink"
              >
                <Users className="h-3.5 w-3.5" />
                <span className="tabular-nums">
                  {customerEmployees.length > 1
                    ? t('customerModal.employeesCount', {
                        count: customerEmployees.length,
                      })
                    : t('customerModal.manage')}
                </span>
              </button>
            </div>
            {customerEmployees[0] ? (
              <div>
                <p className="text-sm font-medium text-ink">{customerEmployees[0].name}</p>
                {customerEmployees[0].role && (
                  <p className="mt-0.5 text-[11px] text-mute">{customerEmployees[0].role}</p>
                )}
                {customerEmployees[0].email && (
                  <p className="mt-0.5 flex items-center gap-1 text-[11px] text-mute">
                    <Mail className="h-3 w-3" />
                    {customerEmployees[0].email}
                  </p>
                )}
              </div>
            ) : (
              <p className="px-3 py-2 text-sm italic text-mute">
                {t('customerModal.notAssigned')}
              </p>
            )}
          </section>

          {/* Trade Summary section */}
          <section className="flex flex-col gap-3 py-5">
            <h4 className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.1em] text-mute">
              <Ship className="h-3 w-3" />
              {t('customerModal.tradeSummary')}
            </h4>
            <div className="space-y-2.5">
              {/* Deal-derived fields (always available if deals exist) */}
              {(localCustomer.tradeIntel?.dealProducts?.length || localCustomer.tradeIntel?.topProducts?.length) ? (
                <div className="flex justify-between gap-2 text-sm">
                  <span className="flex-shrink-0 text-mute">{t('customerModal.tradeProduct')}</span>
                  <span className="truncate text-right font-medium text-ink" lang="en" translate="no" title={(localCustomer.tradeIntel?.dealProducts?.[0] || localCustomer.tradeIntel?.topProducts?.[0]) ?? ''}>
                    {(localCustomer.tradeIntel?.dealProducts?.[0] || localCustomer.tradeIntel?.topProducts?.[0]) ?? '—'}
                  </span>
                </div>
              ) : null}
              {(localCustomer.tradeIntel?.dealHsCodes?.length || localCustomer.tradeIntel?.hsCodes?.length) ? (
                <div className="flex justify-between text-sm">
                  <span className="text-mute">{t('customerModal.tradeHsCode')}</span>
                  <span className="font-mono tabular-nums font-medium text-ink" lang="en" translate="no">
                    {(localCustomer.tradeIntel?.dealHsCodes?.[0] || localCustomer.tradeIntel?.hsCodes?.[0]) ?? '—'}
                  </span>
                </div>
              ) : null}
              {localCustomer.tradeIntel?.fobMin != null && (
                <div className="flex justify-between text-sm">
                  <span className="text-mute">{t('customerModal.tradeFob')}</span>
                  <span className="font-mono tabular-nums font-medium text-ink" lang="en" translate="no">
                    ${localCustomer.tradeIntel.fobMin.toFixed(2)}
                    {localCustomer.tradeIntel.fobMax != null && localCustomer.tradeIntel.fobMax !== localCustomer.tradeIntel.fobMin
                      ? ` - $${localCustomer.tradeIntel.fobMax.toFixed(2)}`
                      : ''}
                  </span>
                </div>
              )}
              {localCustomer.tradeIntel?.moqMin != null && (
                <div className="flex justify-between text-sm">
                  <span className="text-mute">{t('customerModal.tradeMoq')}</span>
                  <span className="font-mono tabular-nums font-medium text-ink" lang="en" translate="no">
                    {localCustomer.tradeIntel.moqMin.toLocaleString()} {t('customerModal.tradeMoqUnit')}
                  </span>
                </div>
              )}
              {localCustomer.tradeIntel?.activeDeals != null && localCustomer.tradeIntel.activeDeals > 0 && (
                <div className="flex justify-between text-sm">
                  <span className="text-mute">{t('customerModal.tradeActiveDeals')}</span>
                  <span className="tabular-nums font-medium text-ink">
                    {t('customerModal.tradeActiveCount', { count: localCustomer.tradeIntel.activeDeals })}
                  </span>
                </div>
              )}

              {/* BoL-derived fields (only if converted from lead with enrichment) */}
              {localCustomer.tradeIntel?.totalShipments != null && (
                <>
                  <div className="my-2 border-t border-rule" />
                  <div className="flex justify-between text-sm">
                    <span className="text-mute">{t('customerModal.tradeImportVolume')}</span>
                    <span className="tabular-nums font-medium text-ink">
                      {t('customerModal.tradeShipments', { count: localCustomer.tradeIntel.totalShipments })}
                    </span>
                  </div>
                </>
              )}
              {localCustomer.tradeIntel?.totalSuppliers != null && (
                <div className="flex justify-between text-sm">
                  <span className="text-mute">{t('customerModal.tradeSuppliers')}</span>
                  <span className="tabular-nums font-medium text-ink">{localCustomer.tradeIntel.totalSuppliers}</span>
                </div>
              )}
              {typeof localCustomer.tradeIntel?.reorderWindow === 'string' &&
                localCustomer.tradeIntel.reorderWindow && (
                  <div className="flex justify-between text-sm">
                    <span className="text-mute">{t('customerModal.tradeReorderWindow')}</span>
                    <span className="font-medium text-ink">
                      {localCustomer.tradeIntel.reorderWindow}
                    </span>
                  </div>
                )}
              {localCustomer.tradeIntel?.chinaConcentration != null && (
                <div className="flex justify-between text-sm">
                  <span className="text-mute">{t('customerModal.tradeChinaShare')}</span>
                  <span className="tabular-nums font-medium text-ink">{localCustomer.tradeIntel.chinaConcentration}%</span>
                </div>
              )}
              {localCustomer.tradeIntel?.growth12mPct != null && (
                <div className="flex justify-between text-sm">
                  <span className="text-mute">{t('customerModal.tradeGrowth')}</span>
                  <span className={`tabular-nums font-medium ${localCustomer.tradeIntel.growth12mPct >= 0 ? signalTextClass('positive') : 'text-mute'}`}>
                    {localCustomer.tradeIntel.growth12mPct >= 0 ? '+' : ''}{localCustomer.tradeIntel.growth12mPct}%
                  </span>
                </div>
              )}

              {/* Fallback if no trade intel at all */}
              {!localCustomer.tradeIntel && (
                <p className="text-sm italic text-mute">—</p>
              )}
            </div>
          </section>
        </div>
      </div>

      {/* Left Column - Activity & Summary */}
      <div className="space-y-4 lg:order-1 lg:col-span-7">
        {/* Activity Panel */}
        <ActivityPanel
          customer={localCustomer}
          customerInteractions={customerInteractions as any}
          loadingInteractions={loadingInteractions}
          timelineFilter={timelineFilter}
          setTimelineFilter={setTimelineFilter}
          timelineSearch={timelineSearch}
          setTimelineSearch={setTimelineSearch}
          isTimelineExpanded={isTimelineExpanded}
          handleTimelineToggle={handleTimelineToggle}
          expandedPanel={expandedPanel}
          setExpandedPanel={setExpandedPanel}
          handleEventClick={handleEventClick}
          getTimelineEvents={getTimelineEvents}
          onNoteAdded={handleNoteAdded}
          onInteractionAdded={handleInteractionAdded}
          notes={notes}
          isLoadingNotes={isLoadingNotes}
          isRefreshingNotes={isRefreshingNotes}
          handleDeleteNote={handleDeleteNote}
          handleToggleNoteStar={handleToggleNoteStar}
          isDeletingNote={isDeletingNote || undefined}
          customerEmployees={customerEmployees}
          selectedEmployeeId={selectedEmployeeId}
          onEmployeeFilterChange={handleEmployeeFilterChange}
          currentUserEmployeeId={currentUserEmployeeId}
        />

        {/* Interaction Summary */}
        <div
          className={`flex flex-col rounded-lg border border-rule bg-bone transition-all duration-300 ${
            expandedPanel === 'summary'
              ? 'h-[calc(1000px+1rem-60px-1rem)] p-6'
              : expandedPanel === 'activity'
                ? 'h-[60px] overflow-visible px-6 py-3'
                : 'h-[500px] p-6'
          }`}
        >
          <div
            className={`flex flex-shrink-0 items-center justify-between ${expandedPanel === 'activity' ? 'mb-0' : 'mb-6'}`}
          >
            <h3 className="title-panel flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-deep" />
              {t('customerModal.interactionSummary')}
            </h3>
            <div className="flex flex-shrink-0 items-center gap-2">
              <Button
                variant="outline"
                className="gap-x-2 border-rule whitespace-nowrap text-mute hover:bg-cream"
                onClick={handleGenerateSummary}
                disabled={isGeneratingSummary || !localCustomer?.id}
              >
                <Brain className="h-4 w-4 flex-shrink-0" />
                {isGeneratingSummary
                  ? t('customerModal.analyzing')
                  : cachedSummary
                    ? t('customerModal.refreshSummary')
                    : t('customerModal.generateSummary')}
              </Button>
              <button
                onClick={() =>
                  setExpandedPanel(expandedPanel === 'summary' ? null : 'summary')
                }
                className="flex-shrink-0 rounded p-1 text-mute transition-colors hover:bg-cream hover:text-ink"
              >
                {expandedPanel === 'summary' ? (
                  <ChevronDown className="h-5 w-5" />
                ) : (
                  <ChevronUp className="h-5 w-5" />
                )}
              </button>
            </div>
          </div>
          {expandedPanel !== 'activity' && (
            <div className="flex-1 overflow-y-auto">
              {isGeneratingSummary ? (
                <div className="flex h-full items-center justify-center">
                  <div className="text-center">
                    <RefreshCw className="mx-auto mb-3 h-8 w-8 animate-spin text-ink" />
                    <p className="text-mute">
                      {t('customerModal.analyzingInteractions')}
                    </p>
                  </div>
                </div>
              ) : cachedSummary ? (
                <div className="space-y-4">
                  {/* AI Insights */}
                  {(cachedSummary as any)?.summaryData?.recentActivities &&
                    (cachedSummary as any).summaryData.recentActivities.length > 0 && (
                      <div>
                        <div className="mb-4 flex items-center gap-2 border-b border-rule pb-3">
                          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-paper">
                            <Sparkles className="h-4 w-4 text-deep" />
                          </div>
                          <h4 className="title-block">
                            {t('customerModal.aiInsights')}
                          </h4>
                        </div>
                        <div className="space-y-4">
                          {(cachedSummary as any).summaryData.recentActivities.map(
                            (activity: string, index: number) => (
                              <div key={index} className="flex gap-3">
                                <div className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-cream text-xs font-semibold text-deep">
                                  {index + 1}
                                </div>
                                <p className="flex-1 text-sm leading-relaxed text-ink">
                                  {activity}
                                </p>
                              </div>
                            )
                          )}
                        </div>
                      </div>
                    )}

                  {/* Next Steps */}
                  {(cachedSummary as any)?.summaryData?.nextSteps &&
                    (cachedSummary as any).summaryData.nextSteps.length > 0 && (
                      <div>
                        <div className="mb-4 flex items-center gap-2 border-b border-rule pb-3">
                          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-paper">
                            <CheckCircle className="h-4 w-4 text-deep" />
                          </div>
                          <h4 className="title-block">
                            {t('customerModal.nextSteps')}
                          </h4>
                        </div>
                        <div className="space-y-4">
                          {(cachedSummary as any).summaryData.nextSteps.map(
                            (step: string, index: number) => (
                              <div key={index} className="flex gap-3">
                                <div className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-cream text-xs font-semibold text-deep">
                                  {index + 1}
                                </div>
                                <p className="flex-1 text-sm leading-relaxed text-ink">
                                  {step}
                                </p>
                              </div>
                            )
                          )}
                        </div>
                      </div>
                    )}
                </div>
              ) : summaryError ? (
                <div className="flex h-full items-center justify-center">
                  <div className="text-center text-threat">
                    <AlertCircle className="mx-auto mb-2 h-8 w-8" />
                    <p className="text-sm">{t('customerModal.errorGeneratingSummary')}</p>
                    <p className="mt-1 text-xs text-mute">{summaryError}</p>
                  </div>
                </div>
              ) : (
                <div className="flex h-full items-center justify-center">
                  <div className="text-center">
                    <Brain className="mx-auto mb-3 h-12 w-12 text-mute" />
                    <p className="text-sm text-mute">{t('customerModal.noSummary')}</p>
                    <p className="mt-1 text-xs text-mute">
                      {t('customerModal.noSummaryHelper')}
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default CustomerOverviewTab
