import React, { useState, useEffect } from 'react'
import { Calendar, FileText, PhoneCall, Star, Plus, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import MeetingScheduler from './MeetingScheduler'
import type { Customer } from '@/types/crm'
import { crmApiClient } from '@/lib/api/client'
import { useTranslations } from 'next-intl'
import { toast } from 'sonner'

interface Tab {
  key: string
  label: string
  icon: React.ElementType
}

interface AddActivityModalProps {
  open?: boolean
  isOpen?: boolean
  onOpenChange?: (open: boolean) => void
  onClose?: () => void
  customer: Customer
  onNoteAdded?: () => void
  onInteractionAdded?: () => void
  initialActivityType?: string
}

/**
 * AddActivityModal - Enhanced with shadcn Dialog primitive
 *
 * Now uses shadcn's Dialog for better accessibility and consistency.
 * Supports both old (isOpen/onClose) and new (open/onOpenChange) prop names for backward compatibility.
 */
const AddActivityModal: React.FC<AddActivityModalProps> = ({
  open,
  isOpen,
  onOpenChange,
  onClose,
  customer,
  onNoteAdded,
  onInteractionAdded,
  initialActivityType = 'note',
}) => {
  const t = useTranslations('crm')
  const MAX_TITLE_LENGTH = 200
  const MAX_NOTE_LENGTH = 2000
  const MAX_CALL_SUMMARY_LENGTH = 5000
  const MAX_THEME_LENGTH = 50

  // Support both new (open) and legacy (isOpen) prop names
  const modalOpen = open !== undefined ? open : (isOpen ?? false)

  // Support both new (onOpenChange) and legacy (onClose) callbacks
  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen && !isSubmitting) {
      if (onOpenChange) {
        onOpenChange(newOpen)
      } else if (onClose) {
        onClose()
      }
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

  // Reset form when modal opens/closes or activity type changes
  useEffect(() => {
    if (!modalOpen) {
      setNoteTitle('')
      setNoteBody('')
      setNoteStar(false)
      setCallSummary('')
      setCallTheme('')
    } else {
      // When modal opens, set the activity type to the initial one
      setActivityType(initialActivityType)
    }
  }, [modalOpen, initialActivityType])

  // Validate note input
  const validateNote = (): string | null => {
    const trimmedBody = noteBody.trim()
    const trimmedTitle = noteTitle.trim()

    if (trimmedBody.length === 0) {
      return t('addActivityValidation.noteContentEmpty')
    }
    if (trimmedBody.length > MAX_NOTE_LENGTH) {
      return t('addActivityValidation.noteContentMax', { max: MAX_NOTE_LENGTH })
    }
    if (trimmedTitle.length > MAX_TITLE_LENGTH) {
      return t('addActivityValidation.noteTitleMax', { max: MAX_TITLE_LENGTH })
    }
    return null
  }

  // Validate call summary input
  const validateCallSummary = (): string | null => {
    const trimmedSummary = callSummary.trim()
    const trimmedTheme = callTheme.trim()

    if (trimmedSummary.length === 0) {
      return t('addActivityValidation.callSummaryEmpty')
    }
    if (trimmedSummary.length > MAX_CALL_SUMMARY_LENGTH) {
      return t('addActivityValidation.callSummaryMax', { max: MAX_CALL_SUMMARY_LENGTH })
    }
    if (trimmedTheme.length > MAX_THEME_LENGTH) {
      return t('addActivityValidation.callThemeMax', { max: MAX_THEME_LENGTH })
    }
    return null
  }

  // Handle note submission
  const handleSubmitNote = async () => {
    if (!customer?.id) return

    const validationError = validateNote()
    if (validationError) {
      toast.error(validationError)
      return
    }

    setIsSubmitting(true)

    const payload = {
      title: noteTitle.trim() || '',
      body: noteBody.trim(),
      star: noteStar ? 'important' : null,
      interactionId: null, // General note, not linked to interaction
    }

    try {
      await crmApiClient.post(`/customers/${customer.id}/notes`, payload)

      toast.success(t('addActivityToasts.noteAdded'))

      // Trigger data refresh in background (don't wait)
      if (onNoteAdded) {
        onNoteAdded()
      }

      handleOpenChange(false)
    } catch (err: any) {
      console.error('Error adding note:', err)
      toast.error(t('addActivityToasts.noteAddFailed'))
    } finally {
      setIsSubmitting(false)
    }
  }

  // Handle call summary submission
  const handleSubmitCallSummary = async () => {
    if (!customer?.id) return

    const validationError = validateCallSummary()
    if (validationError) {
      toast.error(validationError)
      return
    }

    setIsSubmitting(true)

    const payload = {
      content: callSummary.trim(),
      theme: callTheme.trim() || null,
      source: 'manual',
      durationMinutes: null,
    }

    try {
      await crmApiClient.post(`/customers/${customer.id}/call-summaries`, payload)

      toast.success(t('addActivityToasts.callAdded'))

      // Trigger interaction refresh in background (call summaries are interactions)
      if (onInteractionAdded) {
        onInteractionAdded()
      }

      handleOpenChange(false)
    } catch (err: any) {
      console.error('Error adding call summary:', err)
      toast.error(t('addActivityToasts.callAddFailed'))
    } finally {
      setIsSubmitting(false)
    }
  }

  // Get tab configuration
  const tabs: Tab[] = [
    { key: 'note', label: t('addActivityModal.tabNote'), icon: FileText },
    { key: 'meeting', label: t('addActivityModal.tabMeeting'), icon: Calendar },
    { key: 'callSummary', label: t('addActivityModal.tabCall'), icon: PhoneCall },
  ]

  return (
    <Dialog open={modalOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="flex h-[90vh] w-[95vw] max-w-full flex-col p-0">
        <DialogHeader className="flex-shrink-0 border-b border-rule px-6 pt-5 pb-3">
          <DialogTitle className="title-page">{t('addActivityModal.title')}</DialogTitle>
        </DialogHeader>

        {/* Activity Type Tabs */}
        <div className="flex-shrink-0 border-b border-rule px-6">
          <div className="flex gap-2">
            {tabs.map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setActivityType(key)}
                className={`flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium transition-colors ${
                  activityType === key
                    ? 'border-deep text-ink'
                    : 'border-transparent text-mute hover:text-mute'
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
                  <Label htmlFor="note-title-activity">
                    {t('addActivityModal.noteTitle')}{' '}
                    <span className="text-mute">{t('addActivityModal.noteTitleOptional')}</span>
                  </Label>
                  <div className="relative">
                    <Input
                      id="note-title-activity"
                      type="text"
                      value={noteTitle}
                      onChange={(e) => setNoteTitle(e.target.value)}
                      placeholder={t('addActivityModal.noteTitlePlaceholder')}
                      className="pr-20"
                      maxLength={MAX_TITLE_LENGTH}
                      disabled={isSubmitting}
                    />
                    <div className="absolute right-3 bottom-3 text-xs text-mute">
                      {noteTitle.length}/{MAX_TITLE_LENGTH}
                    </div>
                  </div>
                </div>

                {/* Note Body */}
                <div className="space-y-2">
                  <Label htmlFor="note-body-activity">
                    {t('addActivityModal.noteContent')} <span className="text-threat">*</span>
                  </Label>
                  <div className="relative">
                    <Textarea
                      id="note-body-activity"
                      value={noteBody}
                      onChange={(e) => setNoteBody(e.target.value)}
                      placeholder={t('addActivityModal.noteContentPlaceholder')}
                      className="h-48 resize-none pr-20"
                      maxLength={MAX_NOTE_LENGTH}
                      disabled={isSubmitting}
                    />
                    <div className="absolute right-3 bottom-3 text-xs text-mute">
                      {noteBody.length}/{MAX_NOTE_LENGTH}
                    </div>
                  </div>
                </div>

                {/* Star Toggle */}
                <div className="flex items-center gap-3">
                  <label className="flex cursor-pointer items-center gap-2">
                    <input
                      type="checkbox"
                      checked={noteStar}
                      onChange={(e) => setNoteStar(e.target.checked)}
                      disabled={isSubmitting}
                      className="sr-only"
                    />
                    <div
                      className={`flex items-center gap-2 rounded-full px-3 py-2 text-sm transition-colors ${
                        noteStar
                          ? 'border border-gold bg-gold-lo text-gold'
                          : 'border border-rule bg-cream text-mute hover:bg-fog'
                      }`}
                    >
                      <Star
                        className={`h-4 w-4 ${noteStar ? 'fill-gold text-gold' : ''}`}
                      />
                      {noteStar
                        ? t('addActivityModal.important')
                        : t('addActivityModal.markImportant')}
                    </div>
                  </label>
                </div>
              </div>
            </div>
          )}

          {/* Meeting Scheduler */}
          {activityType === 'meeting' && (
            <MeetingScheduler
              customer={{ ...customer, name: customer.name || customer.clientEmail || 'Unknown' }}
              onMeetingCreated={async (meeting: any) => {
                toast.success(t('addActivityToasts.meetingCreated'))

                // Trigger interaction refresh in background (meetings are interactions)
                if (onInteractionAdded) {
                  onInteractionAdded()
                }

                handleOpenChange(false)
              }}
            />
          )}

          {/* Call Summary Form */}
          {activityType === 'callSummary' && (
            <div className="rounded-lg border border-rule bg-bone p-6">
              <div className="space-y-4">
                {/* Call Theme Input */}
                <div className="space-y-2">
                  <Label htmlFor="call-theme">
                    {t('addActivityModal.callTheme')}{' '}
                    <span className="text-mute">{t('addActivityModal.callThemeOptional')}</span>
                  </Label>
                  <div className="relative">
                    <Input
                      id="call-theme"
                      type="text"
                      value={callTheme}
                      onChange={(e) => setCallTheme(e.target.value)}
                      placeholder={t('addActivityModal.callThemePlaceholder')}
                      className="pr-20"
                      maxLength={MAX_THEME_LENGTH}
                      disabled={isSubmitting}
                    />
                    <div className="absolute right-3 bottom-3 text-xs text-mute">
                      {callTheme.length}/{MAX_THEME_LENGTH}
                    </div>
                  </div>
                </div>

                {/* Call Summary Content */}
                <div className="space-y-2">
                  <Label htmlFor="call-summary">
                    {t('addActivityModal.callSummary')} <span className="text-threat">*</span>
                  </Label>
                  <div className="relative">
                    <Textarea
                      id="call-summary"
                      value={callSummary}
                      onChange={(e) => setCallSummary(e.target.value)}
                      placeholder={t('addActivityModal.callSummaryPlaceholder')}
                      className="h-48 resize-none pr-20"
                      maxLength={MAX_CALL_SUMMARY_LENGTH}
                      disabled={isSubmitting}
                    />
                    <div className="absolute right-3 bottom-3 text-xs text-mute">
                      {callSummary.length}/{MAX_CALL_SUMMARY_LENGTH}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <DialogFooter className="flex flex-shrink-0 justify-end gap-3 border-t border-rule bg-paper px-6 py-4">
          <Button variant="outline" onClick={() => handleOpenChange(false)} disabled={isSubmitting}>
            {t('addActivityModal.cancel')}
          </Button>
          {activityType === 'note' && (
            <Button
              className="bg-deep text-bone hover:bg-deep disabled:bg-mute"
              onClick={handleSubmitNote}
              disabled={!noteBody.trim() || isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                  {t('addActivityModal.addingNote')}
                </>
              ) : (
                <>
                  <Plus className="mr-2 h-4 w-4" />
                  {t('addActivityModal.addNote')}
                </>
              )}
            </Button>
          )}
          {activityType === 'callSummary' && (
            <Button
              className="bg-deep text-bone hover:bg-deep disabled:bg-mute"
              onClick={handleSubmitCallSummary}
              disabled={!callSummary.trim() || isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                  {t('addActivityModal.addingCall')}
                </>
              ) : (
                <>
                  <Plus className="mr-2 h-4 w-4" />
                  {t('addActivityModal.addCallSummary')}
                </>
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default AddActivityModal
