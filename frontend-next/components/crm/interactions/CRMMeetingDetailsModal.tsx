import React, { useState, useEffect, useCallback } from 'react'
import {
  Calendar,
  Clock,
  User,
  Users,
  MapPin,
  Link as LinkIcon,
  FileText,
  Loader2,
  Edit3,
  Check,
  Trash2,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { getMeetingById } from '@/lib/api/meetings'
import { ConfirmationToast } from '@/components/ui/confirmation-toast'
import { useConfirmationToast } from '@/hooks/useConfirmationToast'
import { crmApiClient } from '@/lib/api/client'
import { useLocale, useTranslations } from 'next-intl'
import { toast } from 'sonner'

interface Meeting {
  title: string
  description?: string
  startTime: string
  endTime: string
  location?: string
  attendees?: string[]
  timezone?: string
  meetingLink?: string
  googleCalendarEventId?: string
}

interface FormData {
  title: string
  description: string
  startTime: string
  endTime: string
  location: string
  attendees: string[]
  timezone: string
}

interface CRMMeetingDetailsModalProps {
  open?: boolean
  isOpen?: boolean
  onOpenChange?: (open: boolean) => void
  onClose?: () => void
  meetingId?: string
  meeting?: Meeting
  onUpdate?: (meeting: Meeting) => void
  onDelete?: () => void
  googleAccessToken?: string
}

/**
 * CRMMeetingDetailsModal - Enhanced with shadcn Dialog primitive
 *
 * Now uses shadcn's Dialog for better accessibility and consistency.
 * Supports both old (isOpen/onClose) and new (open/onOpenChange) prop names for backward compatibility.
 */

const CRMMeetingDetailsModal: React.FC<CRMMeetingDetailsModalProps> = ({
  open,
  isOpen,
  onOpenChange,
  onClose,
  meetingId,
  meeting,
  onUpdate,
  onDelete,
  googleAccessToken: _googleAccessToken,
}) => {
  const locale = useLocale()
  const t = useTranslations('crm')

  // Support both new (open) and legacy (isOpen) prop names
  const modalOpen = open !== undefined ? open : (isOpen ?? false)

  // Backward compatibility: support both callback names
  const handleOpenChange = (newOpen: boolean) => {
    if (onOpenChange) {
      onOpenChange(newOpen)
    } else if (onClose) {
      if (!newOpen) onClose()
    }
  }
  const [meetingDetails, setMeetingDetails] = useState<Meeting | null>(null)
  const [loading, setLoading] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const { confirm, toastProps } = useConfirmationToast()

  // Form state for editing
  const [formData, setFormData] = useState<FormData>({
    title: '',
    description: '',
    startTime: '',
    endTime: '',
    location: '',
    attendees: [],
    timezone: '',
  })

  const fetchMeetingDetails = useCallback(async () => {
    if (!meetingId) {
      toast.error(t('meetingDetailErrors.missingId'))
      return
    }

    setLoading(true)

    try {
      console.log('🔄 Fetching CRM meeting details for interaction ID:', meetingId)
      const data = await getMeetingById(meetingId)

      console.log('✅ Meeting data received:', data)
      setMeetingDetails(data)
    } catch (err: any) {
      console.error('❌ Error fetching meeting details:', err)
      toast.error(t('meetingDetailErrors.loadFailed'))
    } finally {
      setLoading(false)
    }
  }, [meetingId, t])

  useEffect(() => {
    if (modalOpen) {
      // If meeting data is already provided, use it immediately
      if (meeting) {
        console.log('✅ Using pre-loaded meeting data:', meeting)
        setMeetingDetails(meeting)
        setLoading(false)
        initializeFormData(meeting)
      } else if (meetingId) {
        // Otherwise, fetch from API
        fetchMeetingDetails()
      }
    } else {
      // Reset state when modal closes
      setIsEditing(false)
    }
  }, [modalOpen, meetingId, meeting, fetchMeetingDetails])

  // Initialize form data when meeting details are loaded
  const initializeFormData = (details: Meeting) => {
    if (!details) return

    // Convert ISO datetime to datetime-local format (YYYY-MM-DDTHH:MM) in user's local timezone
    const formatForInput = (isoString: string): string => {
      if (!isoString) return ''
      try {
        const date = new Date(isoString)
        // Use en-US specifically for parsing — this produces the datetime-local input value, not display text
        const localString = date.toLocaleString('en-US', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          hour12: false,
        })
        // Parse the en-US string (format: "MM/DD/YYYY, HH:MM")
        const [datePart, timePart] = localString.split(', ')
        const [month, day, year] = datePart.split('/')
        const [hours, minutes] = timePart.split(':')
        return `${year}-${month}-${day}T${hours}:${minutes}`
      } catch {
        return ''
      }
    }

    setFormData({
      title: details.title || '',
      description: details.description || '',
      startTime: formatForInput(details.startTime),
      endTime: formatForInput(details.endTime),
      location: details.location || '',
      attendees: Array.isArray(details.attendees) ? details.attendees : [],
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    })
  }

  // Update form data initialization when meeting details change
  useEffect(() => {
    if (meetingDetails) {
      initializeFormData(meetingDetails)
    }
  }, [meetingDetails])

  const formatDate = (dateTimeString: string): string => {
    if (!dateTimeString) return t('meetingDetail.notSpecified')
    try {
      const date = new Date(dateTimeString)
      return date.toLocaleDateString(locale, {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    } catch {
      return dateTimeString
    }
  }

  const formatTime = (dateTimeString: string): string => {
    if (!dateTimeString) return t('meetingDetail.notSpecified')
    try {
      const date = new Date(dateTimeString)
      return date.toLocaleTimeString(locale, {
        hour: '2-digit',
        minute: '2-digit',
        timeZoneName: 'short',
      })
    } catch {
      return dateTimeString
    }
  }

  const calculateDuration = (startTime: string, endTime: string): string => {
    if (!startTime || !endTime) return t('meetingDetail.unknown')
    try {
      const start = new Date(startTime)
      const end = new Date(endTime)
      const durationMs = end.getTime() - start.getTime()
      const durationMinutes = Math.floor(durationMs / 60000)

      if (durationMinutes < 60) {
        return t('meetingDetail.durationMinutes', { minutes: durationMinutes })
      } else {
        const hours = Math.floor(durationMinutes / 60)
        const minutes = durationMinutes % 60
        return minutes > 0
          ? t('meetingDetail.durationHoursMinutes', { hours, minutes })
          : t('meetingDetail.durationHours', { hours })
      }
    } catch {
      return t('meetingDetail.unknown')
    }
  }

  // Handle edit mode toggle
  const handleEditClick = () => {
    setIsEditing(true)
  }

  const handleCancelEdit = () => {
    setIsEditing(false)
    // Reset form data to original values
    if (meetingDetails) {
      initializeFormData(meetingDetails)
    }
  }

  // Handle form field changes
  const handleFormChange = (field: keyof FormData, value: string | string[]) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }))
  }

  const handleAttendeesChange = (value: string) => {
    // Split by comma and trim whitespace
    const attendeesList = value
      .split(',')
      .map((email) => email.trim())
      .filter((email) => email)
    setFormData((prev) => ({
      ...prev,
      attendees: attendeesList,
    }))
  }

  // Handle save meeting
  const handleSaveMeeting = async () => {
    if (!formData.title.trim()) {
      toast.error(t('meetingDetailErrors.titleRequired'))
      return
    }

    if (!formData.startTime || !formData.endTime) {
      toast.error(t('meetingDetailErrors.timesRequired'))
      return
    }

    setIsSaving(true)

    try {
      // Convert datetime-local format to ISO string
      const convertToIso = (dateTimeLocal: string): string => {
        const date = new Date(dateTimeLocal)
        return date.toISOString()
      }

      const meetingData = {
        title: formData.title.trim(),
        description: formData.description.trim(),
        startTime: convertToIso(formData.startTime),
        endTime: convertToIso(formData.endTime),
        location: formData.location.trim(),
        attendees: formData.attendees,
        timezone: formData.timezone,
      }

      const updatedMeeting = await crmApiClient.put(`/meetings/${meetingId}`, meetingData)

      setMeetingDetails(updatedMeeting)
      setIsEditing(false)

      // Notify parent component
      if (onUpdate) {
        onUpdate(updatedMeeting)
      }
      toast.success(t('meetingDetail.meetingSaved'))
    } catch (err: any) {
      console.error('Error updating meeting:', err)
      toast.error(t('meetingDetail.meetingSaveFailed'))
    } finally {
      setIsSaving(false)
    }
  }

  // Handle delete meeting
  const handleDeleteClick = () => {
    confirm({
      title: t('deleteMeeting.confirmTitle'),
      description: t('deleteMeeting.confirmDescription'),
      confirmLabel: t('deleteMeeting.confirmLabel'),
      variant: 'destructive',
      itemName: meetingDetails?.title || t('deleteMeeting.untitled'),
      onConfirm: async () => {
        try {
          await crmApiClient.delete(`/meetings/${meetingId}`)

          // Notify parent component
          if (onDelete) {
            onDelete()
          }
          handleOpenChange(false)
          toast.success(t('meetingDetail.meetingDeleted'))
        } catch (err: any) {
          console.error('Error deleting meeting:', err)
          toast.error(t('meetingDetail.meetingDeleteFailed'))
        }
      },
    })
  }

  return (
    <>
      <Dialog open={modalOpen} onOpenChange={handleOpenChange}>
        <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto p-0">
          {/* Header */}
          <DialogHeader className="sticky top-0 z-10 border-b border-zinc-200 bg-zinc-50 p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-zinc-100 p-2">
                  <Calendar className="h-6 w-6 text-zinc-900" />
                </div>
                <div>
                  <DialogTitle className="title-page">
                    {loading
                      ? t('meetingDetail.loadingShort')
                      : meetingDetails?.title || t('meetingDetail.title')}
                  </DialogTitle>
                  <p className="mt-0.5 text-sm text-zinc-600">
                    {isEditing ? t('meetingDetail.editTitle') : t('meetingDetail.title')}
                  </p>
                </div>
              </div>
              {!isEditing && !loading && meetingDetails && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleEditClick}
                  className="border-zinc-300 text-zinc-900 hover:bg-zinc-100"
                >
                  <Edit3 className="mr-2 h-4 w-4" />
                  {t('meetingDetail.editButton')}
                </Button>
              )}
            </div>
          </DialogHeader>

          {/* Content */}
          <div className="p-6">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-zinc-900" />
                <span className="ml-3 text-zinc-600">{t('meetingDetail.loading')}</span>
              </div>
            ) : null}

            {!loading && !meetingDetails ? (
              <div className="py-12 text-center text-muted-foreground">
                {t('meetingDetailErrors.loadFailed')}
              </div>
            ) : !loading && meetingDetails && isEditing ? (
              /* Edit Mode */
              <div className="space-y-6">
                {/* Title */}
                <div>
                  <label className="mb-2 block text-sm font-medium text-zinc-700">
                    {t('meetingDetail.meetingTitleLabel')} *
                  </label>
                  <input
                    type="text"
                    value={formData.title}
                    onChange={(e) => handleFormChange('title', e.target.value)}
                    className="w-full rounded-md border border-zinc-300 px-3 py-2 focus:ring-2 focus:ring-ring focus:outline-none"
                    placeholder={t('meetingDetail.titlePlaceholder')}
                    disabled={isSaving}
                  />
                </div>

                {/* Start and End Time */}
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-zinc-700">
                      {t('meetingDetail.startTime')} *
                    </label>
                    <input
                      type="datetime-local"
                      value={formData.startTime}
                      onChange={(e) => handleFormChange('startTime', e.target.value)}
                      className="w-full rounded-md border border-zinc-300 px-3 py-2 focus:ring-2 focus:ring-ring focus:outline-none"
                      disabled={isSaving}
                    />
                  </div>
                  <div>
                    <label className="mb-2 block text-sm font-medium text-zinc-700">
                      {t('meetingDetail.endTime')} *
                    </label>
                    <input
                      type="datetime-local"
                      value={formData.endTime}
                      onChange={(e) => handleFormChange('endTime', e.target.value)}
                      className="w-full rounded-md border border-zinc-300 px-3 py-2 focus:ring-2 focus:ring-ring focus:outline-none"
                      disabled={isSaving}
                    />
                  </div>
                </div>

                {/* Location */}
                <div>
                  <label className="mb-2 block text-sm font-medium text-zinc-700">
                    {t('meetingDetail.locationLabel')}
                  </label>
                  <input
                    type="text"
                    value={formData.location}
                    onChange={(e) => handleFormChange('location', e.target.value)}
                    className="w-full rounded-md border border-zinc-300 px-3 py-2 focus:ring-2 focus:ring-ring focus:outline-none"
                    placeholder={t('meetingDetail.locationPlaceholder')}
                    disabled={isSaving}
                  />
                </div>

                {/* Attendees */}
                <div>
                  <label className="mb-2 block text-sm font-medium text-zinc-700">
                    {t('meetingDetail.attendeesLabel')}
                  </label>
                  <input
                    type="text"
                    value={formData.attendees.join(', ')}
                    onChange={(e) => handleAttendeesChange(e.target.value)}
                    className="w-full rounded-md border border-zinc-300 px-3 py-2 focus:ring-2 focus:ring-ring focus:outline-none"
                    placeholder={t('meetingDetail.attendeesPlaceholder')}
                    disabled={isSaving}
                  />
                </div>

                {/* Description */}
                <div>
                  <label className="mb-2 block text-sm font-medium text-zinc-700">
                    {t('meetingDetail.descriptionLabel')}
                  </label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => handleFormChange('description', e.target.value)}
                    rows={4}
                    className="w-full rounded-md border border-zinc-300 px-3 py-2 focus:ring-2 focus:ring-ring focus:outline-none"
                    placeholder={t('meetingDetail.descriptionPlaceholder')}
                    disabled={isSaving}
                  />
                </div>

                {/* Action Buttons */}
                <div className="flex items-center justify-end gap-3 border-t border-zinc-200 pt-4">
                  <Button variant="outline" onClick={handleCancelEdit} disabled={isSaving}>
                    {t('meetingDetail.cancelButton')}
                  </Button>
                  <Button
                    onClick={handleSaveMeeting}
                    disabled={
                      isSaving || !formData.title.trim() || !formData.startTime || !formData.endTime
                    }
                    className="bg-primary text-primary-foreground hover:bg-primary/90"
                  >
                    {isSaving ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        {t('meetingDetail.saving')}
                      </>
                    ) : (
                      <>
                        <Check className="mr-2 h-4 w-4" />
                        {t('meetingDetail.saveButton')}
                      </>
                    )}
                  </Button>
                </div>
              </div>
            ) : !loading && meetingDetails ? (
              /* View Mode */
              <div className="space-y-6">
                {/* Meeting Title */}
                <div>
                  <h3 className="title-panel">{meetingDetails.title}</h3>
                </div>

                {/* Meeting Information Grid */}
                <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-6">
                  <h4 className="mb-4 flex items-center gap-2 title-block">
                    <FileText className="h-5 w-5 text-zinc-900" />
                    {t('meetingDetail.meetingInfo')}
                  </h4>
                  <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                    {/* Date */}
                    <div className="flex items-start gap-3">
                      <Calendar className="mt-1 h-5 w-5 text-zinc-600" />
                      <div>
                        <p className="text-sm font-medium text-zinc-500">
                          {t('meetingDetail.date')}
                        </p>
                        <p className="mt-1 text-base text-zinc-900">
                          {formatDate(meetingDetails.startTime)}
                        </p>
                      </div>
                    </div>

                    {/* Time */}
                    <div className="flex items-start gap-3">
                      <Clock className="mt-1 h-5 w-5 text-green-500" />
                      <div>
                        <p className="text-sm font-medium text-zinc-500">
                          {t('meetingDetail.time')}
                        </p>
                        <p className="mt-1 text-base text-zinc-900">
                          {formatTime(meetingDetails.startTime)} -{' '}
                          {formatTime(meetingDetails.endTime)}
                        </p>
                      </div>
                    </div>

                    {/* Duration */}
                    <div className="flex items-start gap-3">
                      <Clock className="mt-1 h-5 w-5 text-orange-500" />
                      <div>
                        <p className="text-sm font-medium text-zinc-500">
                          {t('meetingDetail.duration')}
                        </p>
                        <p className="mt-1 text-base text-zinc-900">
                          {calculateDuration(meetingDetails.startTime, meetingDetails.endTime)}
                        </p>
                      </div>
                    </div>

                    {/* Timezone */}
                    {meetingDetails.timezone && (
                      <div className="flex items-start gap-3">
                        <Clock className="mt-1 h-5 w-5 text-zinc-600" />
                        <div>
                          <p className="text-sm font-medium text-zinc-500">
                            {t('meetingDetail.timezone')}
                          </p>
                          <p className="mt-1 text-base text-zinc-900">{meetingDetails.timezone}</p>
                        </div>
                      </div>
                    )}

                    {/* Location */}
                    {meetingDetails.location && (
                      <div className="flex items-start gap-3">
                        <MapPin className="mt-1 h-5 w-5 text-red-500" />
                        <div>
                          <p className="text-sm font-medium text-zinc-500">
                            {t('meetingDetail.location')}
                          </p>
                          <p className="mt-1 text-base text-zinc-900">{meetingDetails.location}</p>
                        </div>
                      </div>
                    )}

                    {/* Meeting Link */}
                    {meetingDetails.meetingLink && (
                      <div className="flex items-start gap-3">
                        <LinkIcon className="mt-1 h-5 w-5 text-zinc-600" />
                        <div>
                          <p className="text-sm font-medium text-zinc-500">
                            {t('meetingDetail.meetingLink')}
                          </p>
                          <a
                            href={meetingDetails.meetingLink}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="mt-1 text-base break-all text-foreground hover:underline"
                          >
                            {t('meetingDetail.joinMeeting')}
                          </a>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Description */}
                {meetingDetails.description && (
                  <div className="rounded-lg border border-zinc-200 bg-white p-6">
                    <h4 className="mb-3 flex items-center gap-2 title-block">
                      <FileText className="h-5 w-5 text-zinc-900" />
                      {t('meetingDetail.descriptionHeading')}
                    </h4>
                    <p className="leading-relaxed whitespace-pre-wrap text-zinc-700">
                      {meetingDetails.description}
                    </p>
                  </div>
                )}

                {/* Attendees */}
                {meetingDetails.attendees && meetingDetails.attendees.length > 0 && (
                  <div className="rounded-lg border border-zinc-200 bg-white p-6">
                    <h4 className="mb-4 flex items-center gap-2 title-block">
                      <Users className="h-5 w-5 text-zinc-900" />
                      {t('meetingDetail.attendeesCount', {
                        count: meetingDetails.attendees.length,
                      })}
                    </h4>
                    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                      {meetingDetails.attendees.map((attendee, index) => (
                        <div key={index} className="flex items-center gap-2 text-zinc-700">
                          <User className="h-4 w-4 text-zinc-400" />
                          <span className="text-sm">{attendee}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : null}
          </div>

          {/* Footer Actions */}
          {!loading && meetingDetails && !isEditing && (
            <DialogFooter className="border-t border-zinc-200 bg-zinc-50 p-6">
              <div className="flex w-full items-center justify-between">
                <Button
                  variant="outline"
                  onClick={handleDeleteClick}
                  className="border-red-300 text-red-600 hover:bg-red-50"
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  {t('meetingDetail.deleteButton')}
                </Button>
                <Button onClick={() => handleOpenChange(false)} className="px-6">
                  {t('meetingDetail.closeButton')}
                </Button>
              </div>
            </DialogFooter>
          )}
        </DialogContent>
      </Dialog>
      <ConfirmationToast {...toastProps} />
    </>
  )
}

export default CRMMeetingDetailsModal
