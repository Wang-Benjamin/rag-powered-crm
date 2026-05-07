'use client'

import { useEffect, useState } from 'react'
import { useTranslations } from 'next-intl'
import { Clock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover'
import { getDefaultScheduleTime } from '@/lib/utils/scheduleTime'

export interface ScheduleSendPopoverProps {
  onScheduleSend: (scheduledAt: string) => Promise<void>
  isScheduling?: boolean
  isSending?: boolean
  /** Optional preset date-time (ISO-local `YYYY-MM-DDTHH:mm`) to seed the picker. */
  defaultTime?: string
  /** When true, trigger renders as the primary CTA (default variant). */
  isPrimary?: boolean
  /** Invoked after a successful schedule confirm (used by the mass composer's delayed-close pattern). */
  onPostSchedule?: () => void
}

/**
 * Shared popover + datetime-picker trigger for scheduling email sends.
 *
 * Owns the popover open state, the internal `scheduledDateTime` state, the
 * "fill default when opening" effect, confirm + cancel buttons, and the
 * scheduling spinner text. Consumers wrap it in thin components that supply
 * the variant-specific behaviour via props.
 */
export default function ScheduleSendPopover({
  onScheduleSend,
  isScheduling = false,
  isSending = false,
  defaultTime,
  isPrimary = false,
  onPostSchedule,
}: ScheduleSendPopoverProps) {
  const t = useTranslations('email')
  const [open, setOpen] = useState(false)
  const [scheduledDateTime, setScheduledDateTime] = useState(defaultTime ?? '')

  useEffect(() => {
    if (open && !scheduledDateTime) {
      setScheduledDateTime(defaultTime ?? getDefaultScheduleTime())
    }
  }, [open, scheduledDateTime, defaultTime])

  const minDateTime = new Date(Date.now() + 60000).toISOString().slice(0, 16)

  const handleConfirm = async () => {
    if (!scheduledDateTime) return
    try {
      await onScheduleSend(new Date(scheduledDateTime).toISOString())
      setOpen(false)
      setScheduledDateTime('')
      if (onPostSchedule) {
        setTimeout(() => onPostSchedule(), 2000)
      }
    } catch {
      // Error handled in caller
    }
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant={isPrimary ? 'default' : 'outline'}
          disabled={isSending}
          loading={isScheduling}
          loadingText={t('composer.scheduling')}
        >
          <Clock className="mr-2 h-4 w-4" />
          {t('composer.scheduleSend')}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72" align="end">
        <div className="space-y-3">
          <Label className="text-sm font-medium">{t('composer.scheduleFor')}</Label>
          <Input
            type="datetime-local"
            min={minDateTime}
            value={scheduledDateTime}
            onChange={(e) => setScheduledDateTime(e.target.value)}
            className="w-full"
          />
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={handleConfirm}
              disabled={!scheduledDateTime || isScheduling}
              className="flex-1"
            >
              {t('composer.confirmSchedule')}
            </Button>
            <Button variant="outline" size="sm" onClick={() => setOpen(false)}>
              {t('composer.cancel')}
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}
