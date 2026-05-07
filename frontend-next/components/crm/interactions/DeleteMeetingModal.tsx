import React, { useState } from 'react'
import { X, Trash2, Calendar, Clock, Users, MapPin, FileText, ExternalLink } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { ConfirmationToast } from '@/components/ui/confirmation-toast'
import { useConfirmationToast } from '@/hooks/useConfirmationToast'
import { crmApiClient } from '@/lib/api/client'
import { useLocale, useTranslations } from 'next-intl'
import { toast } from 'sonner'

interface Meeting {
  interactionId: string
  title?: string
  description?: string
  startTime?: string
  endTime?: string
  location?: string
  attendees?: string[]
  googleCalendarEventId?: string
}

interface DeleteMeetingModalProps {
  open?: boolean
  isOpen?: boolean
  onOpenChange?: (open: boolean) => void
  onClose?: () => void
  meeting?: Meeting | null
  onDelete: () => void
  googleAccessToken?: string
}

/**
 * MeetingDetailModal - Enhanced with shadcn Dialog primitive
 *
 * Now uses shadcn's Dialog for better accessibility and consistency.
 * Supports both old (onClose) and new (open/onOpenChange) prop names for backward compatibility.
 */
const DeleteMeetingModal: React.FC<DeleteMeetingModalProps> = ({
  open,
  isOpen,
  onOpenChange,
  onClose,
  meeting,
  onDelete,
  googleAccessToken,
}) => {
  const locale = useLocale()
  const t = useTranslations('crm')

  // Support both new (open) and legacy (isOpen) prop names
  const modalOpen = open !== undefined ? open : meeting ? true : false

  // Support both new (onOpenChange) and legacy (onClose) callbacks
  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen) {
      if (onOpenChange) {
        onOpenChange(newOpen)
      } else if (onClose) {
        onClose()
      }
    }
  }

  const { confirm, toastProps } = useConfirmationToast()

  // Helper function to strip HTML tags and decode HTML entities
  const stripHtml = (html?: string): string => {
    if (!html) return ''

    // Create a temporary div element
    const tmp = document.createElement('div')
    tmp.innerHTML = html

    // Get text content (strips all HTML tags)
    let text = tmp.textContent || tmp.innerText || ''

    // Clean up excessive whitespace and dots
    text = text.replace(/\.{10,}/g, '') // Remove long sequences of dots
    text = text.replace(/\s+/g, ' ') // Replace multiple spaces with single space
    text = text.trim()

    return text
  }

  const handleDeleteClick = () => {
    confirm({
      title: t('deleteMeeting.confirmTitle'),
      description: t('deleteMeeting.confirmDescription'),
      confirmLabel: t('deleteMeeting.confirmLabel'),
      variant: 'destructive',
      itemName: meeting?.title || t('deleteMeeting.untitled'),
      onConfirm: async () => {
        if (!meeting?.interactionId) return

        try {
          // Use auto-refresh method - no need to pass token!
          // Backend will use stored tokens with auto-refresh
          await crmApiClient.delete(`/meetings/${meeting.interactionId}`)

          // Success - close modal and refresh calendar
          onDelete()
          toast.success(t('meetingDetail.meetingDeleted'))
        } catch (error: any) {
          console.error('Error deleting meeting:', error)
          const errorCode = error?.data?.detail?.code

          if (errorCode === 'CALENDAR_RECONNECT_REQUIRED') {
            toast.error(t('deleteMeetingErrors.reconnectCalendar'))
          } else if (errorCode === 'MEETING_PERMISSION_DENIED') {
            toast.error(t('deleteMeetingErrors.noPermission'))
          } else if (errorCode === 'CALENDAR_PROVIDER_NOT_CONNECTED') {
            toast.error(t('deleteMeetingErrors.reconnectCalendar'))
          } else {
            toast.error(t('deleteMeetingErrors.deleteFailed'))
          }
        }
      },
    })
  }

  // Format date and time for display
  const formatDateTime = (): string => {
    if (!meeting?.startTime) return t('deleteMeeting.noDate')

    const startDate = new Date(meeting.startTime)
    const endDate = meeting.endTime ? new Date(meeting.endTime) : null

    const dateStr = startDate.toLocaleDateString(locale, {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })

    const startTimeStr = startDate.toLocaleTimeString(locale, {
      hour: 'numeric',
      minute: '2-digit',
    })

    const endTimeStr = endDate
      ? endDate.toLocaleTimeString(locale, {
          hour: 'numeric',
          minute: '2-digit',
        })
      : ''

    return `${dateStr} • ${startTimeStr}${endTimeStr ? ` - ${endTimeStr}` : ''}`
  }

  // Open Google Calendar event link
  const openInGoogleCalendar = () => {
    if (meeting?.googleCalendarEventId) {
      window.open(
        `https://calendar.google.com/calendar/event?eid=${meeting.googleCalendarEventId}`,
        '_blank'
      )
    }
  }

  if (!meeting) return null

  return (
    <>
      <Dialog open={modalOpen} onOpenChange={handleOpenChange}>
        <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
          <DialogHeader className="-mx-6 -mt-6 border-b border-zinc-200 bg-gradient-to-r from-zinc-50 to-zinc-50 px-6 py-6">
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-zinc-100 p-2">
                <Calendar className="h-6 w-6 text-zinc-800" />
              </div>
              <div>
                <DialogTitle className="title-page">
                  {meeting.title || t('deleteMeeting.untitled')}
                </DialogTitle>
                <p className="mt-0.5 text-sm text-zinc-600">{t('deleteMeeting.subtitle')}</p>
              </div>
            </div>
          </DialogHeader>

          {/* Content */}
          <div className="space-y-6">
            {/* Date & Time Section */}
            <div className="flex items-start gap-3">
              <div className="rounded-lg bg-zinc-50 p-2">
                <Clock className="h-5 w-5 text-zinc-900" />
              </div>
              <div className="flex-1">
                <div className="mb-1 text-sm font-medium text-zinc-700">
                  {t('deleteMeeting.dateTime')}
                </div>
                <div className="text-base text-zinc-900">{formatDateTime()}</div>
              </div>
            </div>

            {/* Attendees Section */}
            {meeting.attendees && meeting.attendees.length > 0 && (
              <div className="flex items-start gap-3">
                <div className="rounded-lg bg-green-50 p-2">
                  <Users className="h-5 w-5 text-green-600" />
                </div>
                <div className="flex-1">
                  <div className="mb-1 text-sm font-medium text-zinc-700">
                    {t('deleteMeeting.attendees')}
                  </div>
                  <div className="text-base text-zinc-900">
                    {Array.isArray(meeting.attendees)
                      ? meeting.attendees.join(', ')
                      : meeting.attendees}
                  </div>
                </div>
              </div>
            )}

            {/* Location Section */}
            {meeting.location && (
              <div className="flex items-start gap-3">
                <div className="rounded-lg bg-zinc-50 p-2">
                  <MapPin className="h-5 w-5 text-zinc-700" />
                </div>
                <div className="flex-1">
                  <div className="mb-1 text-sm font-medium text-zinc-700">
                    {t('deleteMeeting.location')}
                  </div>
                  <div className="text-base text-zinc-900">{meeting.location}</div>
                </div>
              </div>
            )}

            {/* Description Section */}
            {meeting.description && (
              <div className="flex items-start gap-3">
                <div className="rounded-lg bg-orange-50 p-2">
                  <FileText className="h-5 w-5 text-orange-600" />
                </div>
                <div className="flex-1">
                  <div className="mb-1 text-sm font-medium text-zinc-700">
                    {t('deleteMeeting.description')}
                  </div>
                  <div className="text-base whitespace-pre-wrap text-zinc-900">
                    {stripHtml(meeting.description)}
                  </div>
                </div>
              </div>
            )}

            {/* Google Calendar Link */}
            {meeting.googleCalendarEventId && (
              <div className="border-t border-zinc-200 pt-4">
                <button
                  onClick={openInGoogleCalendar}
                  className="flex items-center gap-2 text-zinc-900 transition-colors hover:text-zinc-900"
                >
                  <ExternalLink className="h-4 w-4" />
                  <span className="text-sm font-medium">{t('deleteMeeting.viewInCalendar')}</span>
                </button>
              </div>
            )}
          </div>

          <DialogFooter className="-mx-6 -mb-6 flex items-center justify-between border-t border-zinc-200 bg-zinc-50 px-6 py-4">
            <Button
              variant="outline"
              onClick={handleDeleteClick}
              className="border-red-300 text-red-600 hover:bg-red-50"
            >
              <Trash2 className="mr-2 h-4 w-4" />
              {t('deleteMeeting.deleteButton')}
            </Button>
            <Button onClick={() => handleOpenChange(false)} className="px-6">
              {t('deleteMeeting.closeButton')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <ConfirmationToast {...toastProps} />
    </>
  )
}

export default DeleteMeetingModal
