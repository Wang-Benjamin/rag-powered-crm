'use client'

import React, { useState, useEffect } from 'react'
import { Calendar, Clock, Users, MapPin, FileText, RefreshCw, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { crmApiClient } from '@/lib/api/client'
import { useTranslations } from 'next-intl'
import { toast } from 'sonner'
import type { Customer } from '@/types/crm'

interface Meeting {
  id?: string
  title: string
  description?: string
  startTime: string
  endTime: string
  location?: string
  attendees?: string[]
  timezone?: string
}

interface TimeSlot {
  start: string
  end: string
}

interface MeetingFormProps {
  customer: Customer
  onMeetingCreated?: (meeting: Meeting) => Promise<void>
  googleAccessToken?: string | null
  selectedDate?: string | null
  selectedTimeSlot?: TimeSlot | null
}

const MeetingForm: React.FC<MeetingFormProps> = ({
  customer,
  onMeetingCreated,
  selectedDate,
  selectedTimeSlot,
}) => {
  const t = useTranslations('crm')

  // Form state
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [date, setDate] = useState('')
  const [startTime, setStartTime] = useState('')
  const [endTime, setEndTime] = useState('')
  const [attendees, setAttendees] = useState<string[]>([])
  const [attendeeInput, setAttendeeInput] = useState('')
  const [location, setLocation] = useState('Google Meet')

  const [isSubmitting, setIsSubmitting] = useState(false)

  const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone

  // Pre-fill customer email as attendee
  useEffect(() => {
    const customerEmail = customer?.clientEmail
    if (customerEmail && !attendees.includes(customerEmail)) {
      setAttendees([customerEmail])
    }
  }, [customer, attendees])

  // Auto-fill date/time when user clicks on calendar
  useEffect(() => {
    if (selectedDate) {
      setDate(selectedDate)
    }
  }, [selectedDate])

  useEffect(() => {
    if (selectedTimeSlot) {
      setStartTime(selectedTimeSlot.start)
      setEndTime(selectedTimeSlot.end)
    }
  }, [selectedTimeSlot])

  const handleAddAttendee = (e: React.MouseEvent | React.KeyboardEvent) => {
    e.preventDefault()
    const email = attendeeInput.trim()

    if (!email) return

    // Basic email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(email)) {
      toast.error(t('meetingForm.invalidEmail'))
      return
    }

    if (!attendees.includes(email)) {
      setAttendees([...attendees, email])
      setAttendeeInput('')
    }
  }

  const handleRemoveAttendee = (emailToRemove: string) => {
    setAttendees(attendees.filter((email) => email !== emailToRemove))
  }

  const validateForm = (): string | null => {
    if (!title.trim()) return 'Meeting title is required'
    if (!date) return 'Meeting date is required'
    if (!startTime) return 'Start time is required'
    if (!endTime) return 'End time is required'

    // Validate end time is after start time
    if (endTime <= startTime) {
      return 'End time must be after start time'
    }

    if (attendees.length === 0) {
      return 'At least one attendee is required'
    }

    return null
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    // Validate form
    const validationError = validateForm()
    if (validationError) {
      toast.error(validationError)
      return
    }

    setIsSubmitting(true)

    try {
      // Combine date and time and convert to ISO format
      const startDateTime = `${date}T${startTime}:00`
      const endDateTime = `${date}T${endTime}:00`

      // Convert local datetime to ISO string using proper timezone handling
      const convertToIso = (dateTimeLocal: string): string => {
        const date = new Date(dateTimeLocal)
        return date.toISOString()
      }

      const meetingData: Meeting = {
        title: title.trim(),
        description: description.trim(),
        startTime: convertToIso(startDateTime),
        endTime: convertToIso(endDateTime),
        attendees: attendees,
        location: location.trim(),
        timezone: userTimezone,
      }

      // Use auto-refresh method - backend will use stored tokens with auto-refresh
      const meeting = await crmApiClient.post(`/customers/${customer.id}/meetings`, meetingData)

      // Reset form
      setTitle('')
      setDescription('')
      setDate('')
      setStartTime('')
      setEndTime('')
      setAttendees(customer.clientEmail ? [customer.clientEmail] : [])
      setLocation('Google Meet')

      // Callback to parent (parent will show success message)
      if (onMeetingCreated) {
        await onMeetingCreated(meeting)
      }
    } catch (err: any) {
      console.error('Error creating meeting:', err)
      const errorCode = err?.data?.detail?.code

      if (errorCode === 'CALENDAR_RECONNECT_REQUIRED') {
        toast.error(t('deleteMeetingErrors.reconnectCalendar'))
      } else if (errorCode === 'MEETING_PERMISSION_DENIED') {
        toast.error(t('deleteMeetingErrors.noPermission'))
      } else if (errorCode === 'CALENDAR_PROVIDER_NOT_CONNECTED') {
        toast.error(t('deleteMeetingErrors.reconnectCalendar'))
      } else {
        toast.error(t('deleteMeetingErrors.deleteFailed'))
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex h-full flex-col">
      <h3 className="mb-4 title-panel">Create New Meeting</h3>

      <form onSubmit={handleSubmit} className="flex flex-1 flex-col gap-4">
        {/* Title */}
        <div>
          <Label htmlFor="meeting-title">
            Meeting Title <span className="text-threat">*</span>
          </Label>
          <div className="relative">
            <FileText className="absolute top-2.5 left-3 h-4 w-4 text-mute" />
            <Input
              id="meeting-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g., Quarterly Business Review"
              className="pl-10"
              maxLength={200}
              disabled={isSubmitting}
            />
          </div>
        </div>

        {/* Date */}
        <div>
          <Label htmlFor="meeting-date">
            Date <span className="text-threat">*</span>
          </Label>
          <div className="relative">
            <Calendar className="absolute top-2.5 left-3 h-4 w-4 text-mute" />
            <Input
              id="meeting-date"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="pl-10"
              disabled={isSubmitting}
            />
          </div>
        </div>

        {/* Time Range */}
        <div className="grid grid-cols-2 gap-2">
          <div>
            <Label htmlFor="meeting-start-time">
              Start Time <span className="text-threat">*</span>
            </Label>
            <div className="relative">
              <Clock className="absolute top-2.5 left-3 h-4 w-4 text-mute" />
              <Input
                id="meeting-start-time"
                type="time"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
                placeholder="HH:MM"
                className="pl-10"
                disabled={isSubmitting}
                title="Enter time in HH:MM format or use picker"
              />
            </div>
          </div>
          <div>
            <Label htmlFor="meeting-end-time">
              End Time <span className="text-threat">*</span>
            </Label>
            <div className="relative">
              <Clock className="absolute top-2.5 left-3 h-4 w-4 text-mute" />
              <Input
                id="meeting-end-time"
                type="time"
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
                placeholder="HH:MM"
                className="pl-10"
                disabled={isSubmitting}
                title="Enter time in HH:MM format or use picker"
              />
            </div>
          </div>
        </div>

        {/* Attendees */}
        <div>
          <Label htmlFor="meeting-attendee">
            Attendees <span className="text-threat">*</span>
          </Label>

          {/* Attendee chips */}
          <div className="mb-2 flex flex-wrap gap-2">
            {attendees.map((email) => (
              <div
                key={email}
                className="flex items-center gap-1 rounded-full bg-cream px-2 py-1 text-xs text-ink"
              >
                <Users className="h-3 w-3" />
                <span>{email}</span>
                <button
                  type="button"
                  onClick={() => handleRemoveAttendee(email)}
                  className="ml-1 hover:text-ink"
                  disabled={isSubmitting}
                >
                  ×
                </button>
              </div>
            ))}
          </div>

          {/* Add attendee input */}
          <div className="flex gap-2">
            <Input
              id="meeting-attendee"
              type="email"
              value={attendeeInput}
              onChange={(e) => setAttendeeInput(e.target.value)}
              placeholder="Enter email address"
              className="flex-1"
              disabled={isSubmitting}
              onKeyPress={(e) => {
                if (e.key === 'Enter') {
                  handleAddAttendee(e)
                }
              }}
            />
            <Button
              type="button"
              onClick={handleAddAttendee}
              variant="outline"
              size="sm"
              disabled={isSubmitting}
            >
              <Plus className="h-3 w-3" />
            </Button>
          </div>
        </div>

        {/* Description */}
        <div>
          <Label htmlFor="meeting-description">
            Description <span className="text-mute">(Optional)</span>
          </Label>
          <Textarea
            id="meeting-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Add meeting agenda, notes, or context..."
            className="resize-none"
            rows={4}
            maxLength={2000}
            disabled={isSubmitting}
          />
          <div className="mt-1 text-right text-xs text-mute">{description.length}/2000</div>
        </div>

        {/* Location */}
        <div>
          <Label htmlFor="meeting-location">
            Location <span className="text-mute">(Optional)</span>
          </Label>
          <div className="relative">
            <MapPin className="absolute top-2.5 left-3 h-4 w-4 text-mute" />
            <Input
              id="meeting-location"
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="Google Meet (auto-generated)"
              className="pl-10"
              disabled={isSubmitting}
            />
          </div>
        </div>

        {/* Submit Button */}
        <div className="mt-auto pt-4">
          <Button
            type="submit"
            className="w-full bg-deep text-bone hover:bg-deep"
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <>
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                Creating Meeting...
              </>
            ) : (
              <>
                <Plus className="mr-2 h-4 w-4" />
                Create Meeting
              </>
            )}
          </Button>
        </div>
      </form>
    </div>
  )
}

export default MeetingForm
