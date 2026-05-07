import React, { useState, useEffect } from 'react'
import { useTranslations } from 'next-intl'
import { Calendar, FileText, PhoneCall, Star, Check, RefreshCw, Clock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import GoogleCalendarView from '@/components/crm/calendar/GoogleCalendarView'
import type { Deal } from '@/types/crm'
import { crmApiClient } from '@/lib/api/client'
import { toast } from 'sonner'

interface AddDealActivityModalProps {
  open?: boolean
  isOpen?: boolean
  onOpenChange?: (open: boolean) => void
  onClose?: () => void
  deal: Deal
  onActivityAdded?: () => void
  initialActivityType?: string
}

interface Tab {
  key: string
  label: string
  icon: React.ElementType
}

const AddDealActivityModal: React.FC<AddDealActivityModalProps> = ({
  open,
  isOpen,
  onOpenChange,
  onClose,
  deal,
  onActivityAdded,
  initialActivityType = 'note',
}) => {
  const t = useTranslations('crm')
  const MAX_TITLE_LENGTH = 200
  const MAX_NOTE_LENGTH = 2000
  const MAX_CALL_SUMMARY_LENGTH = 5000
  const MAX_THEME_LENGTH = 50

  // Backward compatibility: support both old and new prop names
  const modalOpen = open !== undefined ? open : isOpen

  // Backward compatibility: support both callback names
  const handleOpenChange = (newOpen: boolean) => {
    if (onOpenChange) {
      onOpenChange(newOpen)
    } else if (onClose) {
      if (!newOpen) onClose()
    }
  }

  // State
  const [activityType, setActivityType] = useState(initialActivityType)
  const [noteTitle, setNoteTitle] = useState('')
  const [noteBody, setNoteBody] = useState('')
  const [noteStar, setNoteStar] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Call Summary State
  const [callSummary, setCallSummary] = useState('')
  const [callTheme, setCallTheme] = useState('')

  // Meeting State - Separate date and time fields (matching CRM implementation)
  const [meetingTitle, setMeetingTitle] = useState('')
  const [meetingDescription, setMeetingDescription] = useState('')
  const [meetingDate, setMeetingDate] = useState('')
  const [meetingStartTime, setMeetingStartTime] = useState('')
  const [meetingEndTime, setMeetingEndTime] = useState('')
  const [meetingLocation, setMeetingLocation] = useState('')

  // Calendar state for GoogleCalendarView
  const [allCalendarEvents, setAllCalendarEvents] = useState<any[]>([])
  const [filteredCalendarEvents, setFilteredCalendarEvents] = useState<any[]>([])
  const [googleAccessToken, setGoogleAccessToken] = useState<string | null>(null)
  const [calendarRefreshTrigger, setCalendarRefreshTrigger] = useState(0)

  // Get Google access token on mount
  useEffect(() => {
    const token =
      localStorage.getItem('google_calendar_access_token') ||
      localStorage.getItem('google_access_token')
    setGoogleAccessToken(token)
  }, [])

  // Filter calendar events by client_id when allCalendarEvents or deal changes
  useEffect(() => {
    if (deal && allCalendarEvents.length > 0) {
      const filtered = allCalendarEvents.filter((event) => event.customerId === deal.clientId)
      console.log(
        `[Add Activity Calendar] Filtered ${filtered.length} meetings for client ${deal.clientId}`
      )
      setFilteredCalendarEvents(filtered)
    } else {
      setFilteredCalendarEvents([])
    }
  }, [allCalendarEvents, deal])

  // Reset form when modal opens/closes or activity type changes
  useEffect(() => {
    if (!modalOpen) {
      setNoteTitle('')
      setNoteBody('')
      setNoteStar(false)
      setCallSummary('')
      setCallTheme('')
      setMeetingTitle('')
      setMeetingDescription('')
      setMeetingDate('')
      setMeetingStartTime('')
      setMeetingEndTime('')
      setMeetingLocation('')
    } else {
      setActivityType(initialActivityType)
    }
  }, [modalOpen, initialActivityType])

  const handleSubmitNote = async () => {
    if (!noteBody.trim()) {
      toast.error(t('addActivityValidation.noteContentEmpty'))
      return
    }

    setIsSubmitting(true)

    try {
      await crmApiClient.post(`/deals/${deal.dealId}/notes`, {
        title: noteTitle.trim(),
        body: noteBody.trim(),
        star: noteStar ? 'important' : null,
      })

      toast.success(t('addActivityToasts.noteAdded'))
      handleOpenChange(false)
      if (onActivityAdded) onActivityAdded()
    } catch (err: any) {
      toast.error(t('addActivityToasts.noteAddFailed'))
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleSubmitCallSummary = async () => {
    if (!callSummary.trim()) {
      toast.error(t('addActivityValidation.callSummaryEmpty'))
      return
    }

    setIsSubmitting(true)

    try {
      await crmApiClient.post(`/deals/${deal.dealId}/call-summaries`, {
        content: callSummary.trim(),
        theme: callTheme.trim() || null,
      })

      toast.success(t('addActivityToasts.callAdded'))
      handleOpenChange(false)
      if (onActivityAdded) onActivityAdded()
    } catch (err: any) {
      toast.error(t('addActivityToasts.callAddFailed'))
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleSubmitMeeting = async () => {
    if (!meetingTitle.trim() || !meetingDate || !meetingStartTime || !meetingEndTime) {
      toast.error(t('addDealActivityModal.meetingFieldsRequired'))
      return
    }

    setIsSubmitting(true)

    try {
      // Combine date and time and convert to ISO format
      const startDateTime = `${meetingDate}T${meetingStartTime}:00`
      const endDateTime = `${meetingDate}T${meetingEndTime}:00`

      // Convert datetime-local format to ISO string
      const convertToIso = (dateTimeLocal: string): string => {
        const date = new Date(dateTimeLocal)
        return date.toISOString()
      }

      await crmApiClient.post(`/deals/${deal.dealId}/meetings`, {
        title: meetingTitle.trim(),
        description: meetingDescription.trim() || null,
        startTime: convertToIso(startDateTime),
        endTime: convertToIso(endDateTime),
        location: meetingLocation.trim() || null,
        attendees: [],
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      })

      toast.success(t('addDealActivityModal.meetingAdded'))
      handleOpenChange(false)
      if (onActivityAdded) onActivityAdded()
    } catch (err: any) {
      toast.error(t('addDealActivityModal.meetingAddFailed'))
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleSubmit = () => {
    if (activityType === 'note') {
      handleSubmitNote()
    } else if (activityType === 'callSummary') {
      handleSubmitCallSummary()
    } else if (activityType === 'meeting') {
      handleSubmitMeeting()
    }
  }

  // Get tab configuration
  const tabs: Tab[] = [
    { key: 'note', label: t('addActivityModal.tabNote'), icon: FileText },
    { key: 'meeting', label: t('addActivityModal.tabMeeting'), icon: Calendar },
    { key: 'callSummary', label: t('addActivityModal.tabCall'), icon: PhoneCall },
  ]

  return (
    <Dialog open={modalOpen ?? false} onOpenChange={handleOpenChange}>
      <DialogContent className="flex h-[90vh] w-full max-w-full flex-col p-0">
        {/* Header */}
        <DialogHeader className="flex-shrink-0 border-b border-rule px-6 pt-5 pb-3">
          <DialogTitle className="title-page">
            {t('addActivityModal.title')}
          </DialogTitle>
        </DialogHeader>

        {/* Activity Type Tabs */}
        <div className="flex-shrink-0 border-b border-rule px-6">
          <div className="flex gap-4">
            {tabs.map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setActivityType(key)}
                className={`flex items-center gap-2 border-b-2 pb-3 text-sm font-medium transition-colors ${
                  activityType === key
                    ? 'border-deep text-deep'
                    : 'border-transparent text-mute hover:text-ink'
                }`}
                disabled={isSubmitting}
              >
                <Icon className="h-4 w-4" />
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto bg-paper px-6 py-6">
          {/* Note Form */}
          {activityType === 'note' && (
            <div className="rounded-lg border border-rule bg-bone p-6">
              <div className="space-y-4">
                {/* Title Input */}
                <div className="space-y-2">
                  <label className="block text-sm font-medium text-ink">
                    {t('addActivityModal.noteTitle')}{' '}
                    <span className="text-mute">{t('addActivityModal.noteTitleOptional')}</span>
                  </label>
                  <div className="relative">
                    <input
                      type="text"
                      value={noteTitle}
                      onChange={(e) => setNoteTitle(e.target.value)}
                      placeholder={t('addActivityModal.noteTitlePlaceholder')}
                      className="w-full rounded border border-rule bg-bone px-4 py-3 pr-20 text-sm focus:ring-2 focus:border-accent focus:outline-none"
                      maxLength={MAX_TITLE_LENGTH}
                      disabled={isSubmitting}
                    />
                    <div className="absolute right-3 bottom-3 tabular-nums text-xs text-mute">
                      {noteTitle.length}/{MAX_TITLE_LENGTH}
                    </div>
                  </div>
                </div>

                {/* Note Body */}
                <div className="space-y-2">
                  <label className="block text-sm font-medium text-ink">
                    {t('addActivityModal.noteContent')} <span className="text-threat">*</span>
                  </label>
                  <div className="relative">
                    <textarea
                      value={noteBody}
                      onChange={(e) => setNoteBody(e.target.value)}
                      placeholder={t('addActivityModal.noteContentPlaceholder')}
                      className="h-48 w-full resize-none rounded border border-rule bg-bone px-4 py-3 pr-20 text-sm focus:ring-2 focus:border-accent focus:outline-none"
                      maxLength={MAX_NOTE_LENGTH}
                      disabled={isSubmitting}
                    />
                    <div className="absolute right-3 bottom-3 tabular-nums text-xs text-mute">
                      {noteBody.length}/{MAX_NOTE_LENGTH}
                    </div>
                  </div>
                </div>

                {/* Star Toggle */}
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setNoteStar(!noteStar)}
                    className={`flex items-center gap-2 rounded-lg border px-3 py-2 transition-colors ${
                      noteStar
                        ? 'border-gold/30 bg-gold-lo text-gold'
                        : 'border-rule bg-cream text-mute hover:bg-paper'
                    }`}
                    disabled={isSubmitting}
                  >
                    <Star
                      className={`h-4 w-4 ${noteStar ? 'fill-gold text-gold' : ''}`}
                    />
                    {noteStar
                      ? t('addActivityModal.important')
                      : t('addActivityModal.markImportant')}
                  </button>
                </div>

                {/* Submit Button */}
                <div className="flex justify-end gap-3 pt-4">
                  <Button
                    onClick={() => handleOpenChange(false)}
                    variant="outline"
                    disabled={isSubmitting}
                  >
                    {t('addActivityModal.cancel')}
                  </Button>
                  <Button
                    onClick={handleSubmitNote}
                    disabled={isSubmitting || !noteBody.trim()}
                    className="bg-deep text-bone hover:bg-deep/90"
                  >
                    {isSubmitting ? (
                      <>
                        <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      <>
                        <Check className="mr-2 h-4 w-4" />
                        {t('addDealActivityModal.saveNote')}
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Call Summary Form */}
          {activityType === 'callSummary' && (
            <div className="rounded-lg border border-rule bg-bone p-6">
              <div className="space-y-4">
                {/* Theme Input */}
                <div className="space-y-2">
                  <label className="block text-sm font-medium text-ink">
                    {t('addActivityModal.callTheme')}{' '}
                    <span className="text-mute">{t('addActivityModal.callThemeOptional')}</span>
                  </label>
                  <div className="relative">
                    <input
                      type="text"
                      value={callTheme}
                      onChange={(e) => setCallTheme(e.target.value)}
                      placeholder={t('addActivityModal.callThemePlaceholder')}
                      className="w-full rounded border border-rule bg-bone px-4 py-3 pr-20 text-sm focus:ring-2 focus:border-accent focus:outline-none"
                      maxLength={MAX_THEME_LENGTH}
                      disabled={isSubmitting}
                    />
                    <div className="absolute right-3 bottom-3 tabular-nums text-xs text-mute">
                      {callTheme.length}/{MAX_THEME_LENGTH}
                    </div>
                  </div>
                </div>

                {/* Call Summary */}
                <div className="space-y-2">
                  <label className="block text-sm font-medium text-ink">
                    {t('addActivityModal.callSummary')} <span className="text-threat">*</span>
                  </label>
                  <div className="relative">
                    <textarea
                      value={callSummary}
                      onChange={(e) => setCallSummary(e.target.value)}
                      placeholder={t('addActivityModal.callSummaryPlaceholder')}
                      className="h-64 w-full resize-none rounded border border-rule bg-bone px-4 py-3 pr-20 text-sm focus:ring-2 focus:border-accent focus:outline-none"
                      maxLength={MAX_CALL_SUMMARY_LENGTH}
                      disabled={isSubmitting}
                    />
                    <div className="absolute right-3 bottom-3 tabular-nums text-xs text-mute">
                      {callSummary.length}/{MAX_CALL_SUMMARY_LENGTH}
                    </div>
                  </div>
                </div>

                {/* Submit Button */}
                <div className="flex justify-end gap-3 pt-4">
                  <Button
                    onClick={() => handleOpenChange(false)}
                    variant="outline"
                    disabled={isSubmitting}
                  >
                    {t('addActivityModal.cancel')}
                  </Button>
                  <Button
                    onClick={handleSubmitCallSummary}
                    disabled={isSubmitting || !callSummary.trim()}
                    className="bg-deep text-bone hover:bg-deep/90"
                  >
                    {isSubmitting ? (
                      <>
                        <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      <>
                        <Check className="mr-2 h-4 w-4" />
                        {t('addDealActivityModal.saveCallSummary')}
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Meeting Form */}
          {activityType === 'meeting' && (
            <div className="flex h-full gap-4 bg-paper">
              {/* Left Side: Meeting Form (30%) */}
              <div className="w-[30%] overflow-y-auto rounded-lg border border-rule bg-bone p-6">
                <div className="space-y-4">
                  {/* Meeting Title */}
                  <div className="space-y-2">
                    <label className="block text-sm font-medium text-ink">
                      {t('addDealActivityModal.meetingTitle')}{' '}
                      <span className="text-threat">*</span>
                    </label>
                    <input
                      type="text"
                      value={meetingTitle}
                      onChange={(e) => setMeetingTitle(e.target.value)}
                      placeholder={t('addDealActivityModal.meetingTitlePlaceholder')}
                      className="w-full rounded border border-rule bg-bone px-4 py-3 text-sm focus:ring-2 focus:border-accent focus:outline-none"
                      disabled={isSubmitting}
                    />
                  </div>

                  {/* Meeting Description */}
                  <div className="space-y-2">
                    <label className="block text-sm font-medium text-ink">
                      {t('addDealActivityModal.meetingDescription')}{' '}
                      <span className="text-mute">
                        {t('addDealActivityModal.meetingDescriptionOptional')}
                      </span>
                    </label>
                    <textarea
                      value={meetingDescription}
                      onChange={(e) => setMeetingDescription(e.target.value)}
                      placeholder={t('addDealActivityModal.meetingDescriptionPlaceholder')}
                      className="h-24 w-full resize-none rounded border border-rule bg-bone px-4 py-3 text-sm focus:ring-2 focus:border-accent focus:outline-none"
                      disabled={isSubmitting}
                    />
                  </div>

                  {/* Date */}
                  <div className="space-y-2">
                    <label className="block text-sm font-medium text-ink">
                      {t('addDealActivityModal.meetingDate')}{' '}
                      <span className="text-threat">*</span>
                    </label>
                    <div className="relative">
                      <Calendar className="absolute top-2.5 left-3 h-4 w-4 text-mute" />
                      <input
                        type="date"
                        value={meetingDate}
                        onChange={(e) => setMeetingDate(e.target.value)}
                        className="w-full rounded border border-rule bg-bone py-2 pr-3 pl-10 text-sm focus:ring-2 focus:border-accent focus:outline-none"
                        disabled={isSubmitting}
                      />
                    </div>
                  </div>

                  {/* Time Range */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <label className="block text-sm font-medium text-ink">
                        {t('addDealActivityModal.meetingStartTime')}{' '}
                        <span className="text-threat">*</span>
                      </label>
                      <div className="relative">
                        <Clock className="absolute top-2.5 left-3 h-4 w-4 text-mute" />
                        <input
                          type="time"
                          value={meetingStartTime}
                          onChange={(e) => setMeetingStartTime(e.target.value)}
                          placeholder={t('addDealActivityModal.meetingTimePlaceholder')}
                          className="w-full rounded border border-rule bg-bone py-2 pr-3 pl-10 text-sm focus:ring-2 focus:border-accent focus:outline-none"
                          disabled={isSubmitting}
                          title={t('addDealActivityModal.meetingTimeTooltip')}
                        />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <label className="block text-sm font-medium text-ink">
                        {t('addDealActivityModal.meetingEndTime')}{' '}
                        <span className="text-threat">*</span>
                      </label>
                      <div className="relative">
                        <Clock className="absolute top-2.5 left-3 h-4 w-4 text-mute" />
                        <input
                          type="time"
                          value={meetingEndTime}
                          onChange={(e) => setMeetingEndTime(e.target.value)}
                          placeholder={t('addDealActivityModal.meetingTimePlaceholder')}
                          className="w-full rounded border border-rule bg-bone py-2 pr-3 pl-10 text-sm focus:ring-2 focus:border-accent focus:outline-none"
                          disabled={isSubmitting}
                          title={t('addDealActivityModal.meetingTimeTooltip')}
                        />
                      </div>
                    </div>
                  </div>

                  {/* Location */}
                  <div className="space-y-2">
                    <label className="block text-sm font-medium text-ink">
                      {t('addDealActivityModal.meetingLocation')}{' '}
                      <span className="text-mute">
                        {t('addDealActivityModal.meetingLocationOptional')}
                      </span>
                    </label>
                    <input
                      type="text"
                      value={meetingLocation}
                      onChange={(e) => setMeetingLocation(e.target.value)}
                      placeholder={t('addDealActivityModal.meetingLocationPlaceholder')}
                      className="w-full rounded border border-rule bg-bone px-4 py-3 text-sm focus:ring-2 focus:border-accent focus:outline-none"
                      disabled={isSubmitting}
                    />
                  </div>

                  {/* Submit Button */}
                  <div className="flex justify-end gap-3 pt-4">
                    <Button
                      onClick={() => handleOpenChange(false)}
                      variant="outline"
                      disabled={isSubmitting}
                    >
                      {t('addActivityModal.cancel')}
                    </Button>
                    <Button
                      onClick={handleSubmitMeeting}
                      disabled={
                        isSubmitting ||
                        !meetingTitle.trim() ||
                        !meetingDate ||
                        !meetingStartTime ||
                        !meetingEndTime
                      }
                      className="bg-deep text-bone hover:bg-deep/90"
                    >
                      {isSubmitting ? (
                        <>
                          <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                          Saving...
                        </>
                      ) : (
                        <>
                          <Check className="mr-2 h-4 w-4" />
                          {t('addDealActivityModal.scheduleMeeting')}
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              </div>

              {/* Right Side: Google Calendar View (70%) */}
              <div className="w-[70%] overflow-y-auto rounded-lg border border-rule bg-bone p-6">
                <h3 className="mb-4 flex items-center gap-2 title-panel">
                  <Calendar className="h-4 w-4 text-ink" />
                  {t('addDealActivityModal.meetingCalendar')}
                  {deal && (
                    <span className="text-xs font-normal text-mute">
                      (
                      {t('addDealActivityModal.meetingCount', {
                        count: filteredCalendarEvents.length,
                      })}
                      )
                    </span>
                  )}
                </h3>
                <div className="flex-1 overflow-hidden">
                  <GoogleCalendarView
                    customer={
                      deal
                        ? {
                            id: String(deal.clientId || ''),
                            name: deal.clientName || '',
                            company: deal.clientName || '',
                          }
                        : undefined
                    }
                    googleAccessToken={googleAccessToken || undefined}
                    onDateSelect={(date: string) => {
                      // Auto-fill date when calendar date is selected
                      if (date) {
                        setMeetingDate(date) // date is already in YYYY-MM-DD format
                      }
                    }}
                    onTimeSlotSelect={(timeSlot: { start: string; end: string }) => {
                      // Auto-fill start and end time when time slot is selected
                      if (timeSlot?.start && timeSlot?.end) {
                        setMeetingStartTime(timeSlot.start) // Already in HH:MM format
                        setMeetingEndTime(timeSlot.end) // Already in HH:MM format
                      }
                    }}
                    refreshTrigger={calendarRefreshTrigger}
                    events={filteredCalendarEvents}
                    setEvents={setAllCalendarEvents}
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default AddDealActivityModal
