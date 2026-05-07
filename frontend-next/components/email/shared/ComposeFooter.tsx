'use client'

import React from 'react'
import { Eye, Repeat, Send } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import ScheduleSendPopover from './ScheduleSendPopover'

export interface ComposeFooterProps {
  mode: 'single' | 'mass'
  /** Local-time hint for the recipient (e.g. "Denver 9:14 AM · best send window"). */
  localTimeHint?: string
  onCancel: () => void
  onSend: () => void
  onSchedule?: (scheduledAt: string) => Promise<void>
  sending: boolean
  scheduling?: boolean
  disabled?: boolean

  /** Mass-mode only. */
  approvedCount?: number
  totalCount?: number
  onApproveAll?: () => void

  /** Optional preset for the schedule popover's datetime picker (ISO-local `YYYY-MM-DDTHH:mm`). */
  defaultScheduleTime?: string
}

/**
 * Sticky bottom bar inside `.compose-right`. All footer actions use the
 * kit's <Button> so sizing matches the rest of the app (especially the
 * ScheduleSendPopover trigger, which also uses <Button>).
 *
 * Tracking pills are rendered disabled with a "Coming soon" tooltip in
 * Phase 1 — the underlying flag (`track_opens`) has no propagation path
 * through the orchestrator yet (see docs/leadgen/email-attachments-plan.md
 * task T7).
 */
const ComposeFooter: React.FC<ComposeFooterProps> = ({
  mode,
  localTimeHint,
  onCancel,
  onSend,
  onSchedule,
  sending,
  scheduling = false,
  disabled = false,
  approvedCount,
  totalCount,
  onApproveAll,
  defaultScheduleTime,
}) => {
  const t = useTranslations('email')
  const inFlight = sending || scheduling
  const sendDisabled = disabled || inFlight || (mode === 'mass' && (approvedCount ?? 0) === 0)

  return (
    <div className="sticky-foot">
      <div className="foot-left">
        {localTimeHint && <span className="caption-muted">{localTimeHint}</span>}
        {localTimeHint && <span className="foot-sep">·</span>}

        <button
          type="button"
          className="toggle-pill"
          aria-disabled="true"
          title={t('composer.footer.trackingComingSoon')}
        >
          <Eye />
          {t('composer.footer.tracking')}
        </button>
        <button
          type="button"
          className="toggle-pill"
          aria-disabled="true"
          title={t('composer.footer.trackingComingSoon')}
        >
          <Repeat />
          {t('composer.footer.readReceipt')}
        </button>

        {mode === 'mass' && totalCount !== undefined && (
          <span className="caption-muted">
            {t('composer.footer.approvedCount', {
              approved: approvedCount ?? 0,
              total: totalCount,
            })}
          </span>
        )}
      </div>

      <div className="foot-right">
        <Button variant="outline" onClick={onCancel} disabled={inFlight}>
          {t('composer.cancel')}
        </Button>

        {mode === 'mass' && onApproveAll && (
          <Button variant="outline" onClick={onApproveAll} disabled={inFlight}>
            {t('composer.footer.approveAll')}
          </Button>
        )}

        {onSchedule && (
          <ScheduleSendPopover
            onScheduleSend={onSchedule}
            isScheduling={scheduling}
            isSending={sending}
            defaultTime={defaultScheduleTime}
          />
        )}

        <Button onClick={onSend} disabled={sendDisabled} loading={sending}>
          <Send className="mr-2 h-4 w-4" />
          {mode === 'mass' ? t('composer.footer.sendApproved') : t('composer.sendEmail')}
        </Button>
      </div>
    </div>
  )
}

export default ComposeFooter
