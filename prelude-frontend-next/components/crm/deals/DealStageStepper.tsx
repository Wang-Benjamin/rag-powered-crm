import React, { useState } from 'react'
import { Check, Circle, GitBranch } from 'lucide-react'
import { crmApiClient } from '@/lib/api/client'
import { useTranslations } from 'next-intl'
import { toast } from 'sonner'

interface DealStageStepperProps {
  currentRoomStatus: string
  dealId: string
  onRoomStatusUpdate?: (roomStatus: string) => void
}

interface Stage {
  id: string
  label: string
  order: number
  type: 'normal' | 'success' | 'failure'
}

const DealStageStepper: React.FC<DealStageStepperProps> = ({
  currentRoomStatus,
  dealId,
  onRoomStatusUpdate,
}) => {
  const t = useTranslations('crm')
  const [isUpdating, setIsUpdating] = useState(false)

  // Define linear room status progression
  const stages: Stage[] = [
    { id: 'draft', label: t('dealStages.draft'), order: 1, type: 'normal' },
    { id: 'sent', label: t('dealStages.sent'), order: 2, type: 'normal' },
    { id: 'viewed', label: t('dealStages.viewed'), order: 3, type: 'normal' },
    { id: 'quote_requested', label: t('dealStages.quoteRequested'), order: 4, type: 'normal' },
    { id: 'closed-won', label: t('dealStages.closedWon'), order: 5, type: 'success' },
    { id: 'closed-lost', label: t('dealStages.closedLost'), order: 6, type: 'failure' },
  ]

  // Get current room status info
  const getCurrentStatusOrder = (): number => {
    const stage = stages.find((s) => s.id === currentRoomStatus)
    return stage ? stage.order : 0
  }

  const currentOrder = getCurrentStatusOrder()

  // Handle status click
  const handleStatusClick = async (statusId: string) => {
    if (statusId === currentRoomStatus || isUpdating) return

    setIsUpdating(true)
    try {
      console.log(`Updating deal ${dealId} room_status to ${statusId}...`)

      const data = await crmApiClient.put(`/deals/${dealId}`, { roomStatus: statusId })
      console.log('Room status updated successfully:', data)

      // Call parent callback to refresh deal data
      if (onRoomStatusUpdate) {
        onRoomStatusUpdate(statusId)
      }
      toast.success(t('dealStageStepper.stageUpdated'))
    } catch (error: any) {
      console.error('Room status update error:', error)

      const errorMessage = error.message?.includes('Failed to fetch')
        ? t('dealStageStepper.connectionError')
        : t('dealStageStepper.updateFailed')

      toast.error(errorMessage)
    } finally {
      setIsUpdating(false)
    }
  }

  // Determine stage status
  const getStageStatus = (stage: Stage): string => {
    if (stage.id === currentRoomStatus) return 'current'
    if (stage.order < currentOrder) return 'completed'
    return 'upcoming'
  }

  // Get stage styles
  const getStageStyles = (status: string, type: string = 'normal') => {
    // Terminal stage colors
    if (type === 'success' && status === 'current') {
      return {
        circle: 'bg-accent border-accent text-bone ring-4 ring-accent/10',
        label: 'text-accent font-semibold',
        connector: 'bg-accent',
      }
    }

    if (type === 'failure' && status === 'current') {
      return {
        circle: 'bg-threat border-threat text-bone ring-4 ring-threat/10',
        label: 'text-threat font-semibold',
        connector: 'bg-threat',
      }
    }

    // Standard progression colors
    switch (status) {
      case 'completed':
        return {
          circle: 'bg-deep border-deep text-bone',
          label: 'text-deep',
          connector: 'bg-deep',
        }
      case 'current':
        return {
          circle: 'bg-deep border-deep text-bone ring-4 ring-deep/10',
          label: 'text-deep font-semibold',
          connector: 'bg-rule',
        }
      case 'upcoming':
        return {
          circle: 'bg-bone border-rule text-mute hover:border-rule hover:bg-paper',
          label: 'text-mute',
          connector: 'bg-rule',
        }
      default:
        return {
          circle: 'bg-cream border-rule text-mute',
          label: 'text-mute',
          connector: 'bg-rule',
        }
    }
  }

  return (
    <div className="rounded-lg border border-rule bg-bone px-6 py-4 shadow-sm">
      {/* Header - matching Activity & Notes style */}
      <h3 className="mb-3 flex items-center gap-2 title-panel">
        <GitBranch className="h-5 w-5 text-ink" />
        {t('dealStageStepper.dealStage')}
      </h3>

      <div className="relative">
        {/* Linear progression stages */}
        <div className="flex items-center justify-between">
          {stages.map((stage, index) => {
            const status = getStageStatus(stage)
            const styles = getStageStyles(status, stage.type)
            const isClickable = !isUpdating && status !== 'current'

            return (
              <React.Fragment key={stage.id}>
                {/* Stage */}
                <div className="flex flex-1 flex-col items-center">
                  <button
                    onClick={() => isClickable && handleStatusClick(stage.id)}
                    disabled={isUpdating || status === 'current'}
                    className={`flex h-7 w-7 items-center justify-center rounded-full border-2 transition-all duration-200 ${styles.circle} ${
                      isClickable ? 'transform cursor-pointer hover:scale-110' : 'cursor-default'
                    } ${isUpdating ? 'opacity-50' : ''}`}
                  >
                    {status === 'completed' ? (
                      <Check className="h-3.5 w-3.5" />
                    ) : status === 'current' ? (
                      <Circle className="h-3.5 w-3.5 fill-current" />
                    ) : (
                      <span className="tabular-nums text-xs font-medium">{stage.order}</span>
                    )}
                  </button>
                  <span className={`mt-1 text-center text-xs ${styles.label} transition-colors`}>
                    {stage.label}
                  </span>
                </div>

                {/* Connector */}
                {index < stages.length - 1 && (
                  <div className="mx-1 mb-4 flex-1">
                    <div className={`h-0.5 ${styles.connector} transition-colors`}></div>
                  </div>
                )}
              </React.Fragment>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default DealStageStepper
