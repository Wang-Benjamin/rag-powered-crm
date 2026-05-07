import React, { useState, useEffect } from 'react'
import MeetingForm from './MeetingForm'
import GoogleCalendarView from '../calendar/GoogleCalendarView'
import type { Customer } from '@/types/crm'

interface Meeting {
  id?: string
  title: string
  description?: string
  startTime: string
  endTime: string
  location?: string
  attendees?: string[]
}

interface TimeSlot {
  start: string
  end: string
}

interface MeetingSchedulerProps {
  customer: Customer
  onMeetingCreated?: (meeting: Meeting) => Promise<void>
}

const MeetingScheduler: React.FC<MeetingSchedulerProps> = ({ customer, onMeetingCreated }) => {
  const [googleAccessToken, setGoogleAccessToken] = useState<string | null>(null)
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [selectedTimeSlot, setSelectedTimeSlot] = useState<TimeSlot | null>(null)
  const [events, setEvents] = useState<any[]>([])
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  useEffect(() => {
    // Get Google access token from localStorage
    // Try both keys for compatibility
    const token =
      localStorage.getItem('google_calendar_access_token') ||
      localStorage.getItem('google_access_token')
    setGoogleAccessToken(token)
  }, [])

  const handleMeetingCreated = async (meeting: Meeting) => {
    // Trigger calendar refresh
    setRefreshTrigger((prev) => prev + 1)

    // Call parent callback
    if (onMeetingCreated) {
      await onMeetingCreated(meeting)
    }
  }

  const handleDateSelect = (date: string) => {
    setSelectedDate(date)
  }

  const handleTimeSlotSelect = (timeSlot: TimeSlot) => {
    setSelectedTimeSlot(timeSlot)
  }

  return (
    <div className="flex h-full gap-4 bg-zinc-50">
      {/* Left Side: Meeting Form (30%) */}
      <div className="w-[30%] overflow-y-auto rounded-lg border border-zinc-200 bg-white p-6">
        <MeetingForm
          customer={customer}
          onMeetingCreated={handleMeetingCreated}
          googleAccessToken={googleAccessToken}
          selectedDate={selectedDate}
          selectedTimeSlot={selectedTimeSlot}
        />
      </div>

      {/* Right Side: Google Calendar View (70%) */}
      <div className="w-[70%] overflow-y-auto rounded-lg border border-zinc-200 bg-white p-6">
        <GoogleCalendarView
          customer={customer}
          googleAccessToken={googleAccessToken || undefined}
          onDateSelect={handleDateSelect}
          onTimeSlotSelect={handleTimeSlotSelect}
          refreshTrigger={refreshTrigger}
          events={events}
          setEvents={setEvents}
        />
      </div>
    </div>
  )
}

export default MeetingScheduler
