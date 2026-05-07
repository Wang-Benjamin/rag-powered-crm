'use client'

import React from 'react'
import { useTranslations } from 'next-intl'
import { Building } from 'lucide-react'
import DealActivityPanel from './DealActivityPanel'
import DealStageStepper from './DealStageStepper'
import type { Deal } from '@/types/crm'

interface Note {
  id: string
  star?: string
  date: string
  title?: string
  body?: string
  content?: string
  updatedAt?: string
  author?: string
  [key: string]: any
}

interface Activity {
  activityType: string
  type?: string
  originalType?: string
  title?: string
  theme?: string
  body?: string
  content?: string
  createdAt: string
  date?: string
  employeeName?: string
  interactionId?: string
  noteId?: string
  source?: string
  sourceName?: string
  sourceType?: string
  subject?: string
  direction?: string
  fromEmail?: string
  toEmail?: string
  gmailMessageId?: string
  description?: string
  startTime?: string
  endTime?: string
  location?: string
  metadata?: any
}

export interface DealOverviewTabProps {
  localDeal: Deal
  setLocalDeal: React.Dispatch<React.SetStateAction<Deal | null>>
  updateDeal: ((id: string, deal: any) => Promise<any>) | undefined
  editingField: string | null
  handleFieldClick: (fieldName: string, currentValue?: any) => void
  renderEditableField: (
    fieldName: string,
    value?: any,
    placeholder?: string,
    type?: string
  ) => React.ReactNode
  renderEditableTextarea: (fieldName: string, value?: any, placeholder?: string) => React.ReactNode
  renderEditableEmployeeDropdown: (
    fieldName: string,
    employeeId?: number | null,
    employeeName?: string
  ) => React.ReactNode
  formatCurrency: (value?: number | null) => string
  formatDate: (dateString?: string | null) => string
  activityRefreshTrigger: number
  notes: Note[]
  isDeletingNote: string | null
  handleEventClick: (activity: Activity) => void
  handleDeleteNote: (noteId: string) => Promise<void>
  handleCallEventDelete: (interactionId?: string) => Promise<void>
}

const DealOverviewTab: React.FC<DealOverviewTabProps> = ({
  localDeal,
  setLocalDeal,
  updateDeal,
  editingField,
  handleFieldClick,
  renderEditableField,
  renderEditableTextarea,
  renderEditableEmployeeDropdown,
  formatCurrency,
  formatDate,
  activityRefreshTrigger,
  notes,
  isDeletingNote,
  handleEventClick,
  handleDeleteNote,
  handleCallEventDelete,
}) => {
  const t = useTranslations('crm')
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-10">
      {/* Right Column - Deal Information */}
      <div className="space-y-4 lg:order-2 lg:col-span-3">
        {/* Deal Information Card */}
        <div className="flex flex-col rounded-lg border border-rule bg-bone p-6">
          <div className="mb-6 flex flex-shrink-0 items-center justify-between">
            <h3 className="title-panel flex items-center gap-2">
              <Building className="h-4 w-4 text-deep" />
              {t('dealModal.dealInfo')}
            </h3>
          </div>
          <div className="flex-1 space-y-4 overflow-y-auto">
            <div>
              <label className="mb-1 block text-sm font-medium text-mute">
                {t('dealModal.dealName')}
              </label>
              {renderEditableField(
                'dealName',
                localDeal.dealName,
                t('dealModal.clickToAdd')
              )}
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-mute">
                {t('dealModal.client')}
              </label>
              {/* Client is read-only - it's determined by the clientId relationship */}
              <p className="text-ink">{localDeal.clientName || '-'}</p>
            </div>

            {localDeal.clientEmail && (
              <div>
                <label className="mb-1 block text-sm font-medium text-mute">
                  {t('dealModal.clientEmail')}
                </label>
                <p className="text-ink">
                  <a
                    href={`mailto:${localDeal.clientEmail}`}
                    className="text-accent hover:underline"
                  >
                    {localDeal.clientEmail}
                  </a>
                </p>
              </div>
            )}

            <div>
              <label className="mb-1 block text-sm font-medium text-mute">
                {t('dealModal.valueUsd')}
              </label>
              <div className="rounded py-1">
                <p className="text-lg tabular-nums text-deep">
                  {formatCurrency(localDeal.valueUsd)}
                </p>
              </div>
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-mute">
                {t('dealModal.fobPrice')}
              </label>
              {editingField === 'fobPrice' ? (
                renderEditableField('fobPrice', localDeal.fobPrice, '0.00', 'number')
              ) : (
                <div
                  onClick={() => handleFieldClick('fobPrice', localDeal.fobPrice)}
                  className="cursor-pointer rounded border border-transparent px-2 py-1 transition-colors hover:border-rule hover:bg-cream"
                  title={t('dealModal.clickToEdit')}
                >
                  <p className="tabular-nums text-ink">
                    {localDeal.fobPrice != null ? (
                      formatCurrency(localDeal.fobPrice)
                    ) : (
                      <span className="text-mute italic">
                        {t('dealModal.clickToAdd')}
                      </span>
                    )}
                  </p>
                </div>
              )}
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-mute">
                {t('dealModal.salesman')}
              </label>
              {renderEditableEmployeeDropdown(
                'employeeId',
                localDeal.employeeId,
                localDeal.salesmanName
              )}
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-mute">
                {t('dealModal.closingDate')}
              </label>
              {renderEditableField(
                'expectedCloseDate',
                localDeal.expectedCloseDate,
                t('dealModal.clickToAddDate'),
                'date'
              )}
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-mute">
                {t('dealModal.lastContactDate')}
              </label>
              <p className="tabular-nums text-ink">{formatDate(localDeal.lastContactDate)}</p>
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-mute">
                {t('dealModal.createdDate')}
              </label>
              <p className="tabular-nums text-ink">{formatDate(localDeal.createdAt)}</p>
            </div>

            <div className="border-t border-rule pt-4">
              <label className="mb-1 block text-sm font-medium text-mute">
                {t('dealModal.description')}
              </label>
              {renderEditableTextarea(
                'description',
                localDeal.description,
                t('dealModal.descriptionPlaceholder')
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Left Column - Stage Stepper & Activities */}
      <div className="flex flex-col gap-4 lg:order-1 lg:col-span-7">
        {/* Deal Stage Stepper */}
        <div className="flex-shrink-0">
          <DealStageStepper
            currentRoomStatus={localDeal.roomStatus || ''}
            dealId={String(localDeal.dealId)}
            onRoomStatusUpdate={async (newRoomStatus: string) => {
              const updatedDeal = {
                ...localDeal,
                roomStatus: newRoomStatus,
                updatedAt: new Date().toISOString(),
              }
              setLocalDeal(updatedDeal)
              if (updateDeal) {
                await updateDeal(String(updatedDeal.dealId), updatedDeal)
              }
            }}
          />
        </div>

        {/* Activity & Notes Panel */}
        <div className="min-h-0 flex-1">
          <DealActivityPanel
            key={activityRefreshTrigger} // Force re-mount when trigger changes
            deal={localDeal as any}
            onActivityAdded={() => {
              // Optionally refresh deal data
            }}
            handleEventClick={handleEventClick}
            notes={notes as any}
            isDeletingNote={isDeletingNote || undefined}
            handleDeleteNote={handleDeleteNote}
            onCallDeleted={handleCallEventDelete}
          />
        </div>
      </div>
    </div>
  )
}

export default DealOverviewTab
