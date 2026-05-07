'use client'

import React, { useState, useEffect, useCallback } from 'react'
import { Calendar, RefreshCw, ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import MeetingDetailModal from '../interactions/DeleteMeetingModal'
import type { Customer } from '@/types/crm'
import { crmApiClient } from '@/lib/api/client'
import { useLocale, useTranslations } from 'next-intl'
import { toast } from 'sonner'

// Types

interface CalendarEvent {
  interactionId: string
  title: string
  startTime: string
  endTime: string
  attendees?: string[]
  content?: string | object
}

interface GoogleCalendarViewProps {
  customer?: Customer
  googleAccessToken?: string
  onDateSelect?: (date: string) => void
  onTimeSlotSelect?: (timeSlot: { start: string; end: string }) => void
  refreshTrigger?: number
  events: CalendarEvent[]
  setEvents: (events: CalendarEvent[]) => void
}

type ViewMode = 'month' | 'week' | 'day'
type CalendarProvider = 'google' | 'microsoft'

const GoogleCalendarView: React.FC<GoogleCalendarViewProps> = ({
  customer,
  googleAccessToken,
  onDateSelect,
  onTimeSlotSelect,
  refreshTrigger,
  events,
  setEvents,
}) => {
  const locale = useLocale()
  const t = useTranslations('crm')
  const [currentDate, setCurrentDate] = useState<Date>(new Date())
  const [viewMode, setViewMode] = useState<ViewMode>('month')
  const [loading, setLoading] = useState<boolean>(false)
  const [syncing, setSyncing] = useState<boolean>(false)
  const [selectedMeeting, setSelectedMeeting] = useState<CalendarEvent | null>(null)
  const [showDeleteModal, setShowDeleteModal] = useState<boolean>(false)
  const [calendarProvider, setCalendarProvider] = useState<CalendarProvider>('google')

  // Fetch meetings from CRM
  const fetchMeetings = useCallback(async () => {
    setLoading(true)
    try {
      // Fetch ALL meetings for the current user (across all customers)
      const meetings: CalendarEvent[] = await crmApiClient.get('/meetings')
      setEvents(meetings)

      // Detect calendar provider from meetings if available
      if (meetings.length > 0 && meetings[0].content) {
        try {
          const content =
            typeof meetings[0].content === 'string'
              ? JSON.parse(meetings[0].content)
              : meetings[0].content
          if (content.calendarProvider) {
            setCalendarProvider(content.calendarProvider)
          }
        } catch (e) {
          // Ignore parsing errors
        }
      }
    } catch (error) {
      console.error('Error fetching meetings:', error)
    } finally {
      setLoading(false)
    }
  }, [setEvents])

  // Fetch meetings on mount and when refreshTrigger changes
  useEffect(() => {
    fetchMeetings()
  }, [fetchMeetings, refreshTrigger])

  // Sync from Google Calendar
  const handleSyncFromGoogle = async () => {
    setSyncing(true)
    try {
      // Use auto-refresh method - no need to pass token!
      // Backend will use stored tokens with auto-refresh
      const result = await crmApiClient.post('/sync-all-google-calendar', {})
      const providerName = calendarProvider === 'google' ? 'Google Calendar' : 'Outlook Calendar'
      toast.success(t('calendar.syncSuccess', { count: result.newMeetings, provider: providerName }))
      fetchMeetings() // Refresh list
    } catch (error: any) {
      const errorMsg = error.message || error.detail || t('calendar.syncFailed')
      const providerName = calendarProvider === 'google' ? 'Google Calendar' : 'Outlook Calendar'

      // Check if user needs to connect calendar
      if (
        errorMsg.includes('No valid') ||
        errorMsg.includes('reconnect') ||
        errorMsg.includes('No calendar provider')
      ) {
        toast.error(t('calendar.syncReconnect', { provider: providerName }))
      } else {
        toast.error(t('calendar.syncFailed'), { description: errorMsg })
      }
      console.error('Error syncing calendar:', error)
    } finally {
      setSyncing(false)
    }
  }

  // Calendar navigation
  const navigateMonth = (direction: number) => {
    const newDate = new Date(currentDate)
    newDate.setMonth(currentDate.getMonth() + direction)
    setCurrentDate(newDate)
  }

  const navigateWeek = (direction: number) => {
    const newDate = new Date(currentDate)
    newDate.setDate(currentDate.getDate() + direction * 7)
    setCurrentDate(newDate)
  }

  const navigateDay = (direction: number) => {
    const newDate = new Date(currentDate)
    newDate.setDate(currentDate.getDate() + direction)
    setCurrentDate(newDate)
  }

  const handleNavigate = (direction: number) => {
    if (viewMode === 'month') navigateMonth(direction)
    else if (viewMode === 'week') navigateWeek(direction)
    else navigateDay(direction)
  }

  const goToToday = () => {
    setCurrentDate(new Date())
  }

  // Handle date click
  const handleDateClick = (date: Date) => {
    if (onDateSelect) {
      // Format date as YYYY-MM-DD
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      onDateSelect(`${year}-${month}-${day}`)
    }
  }

  // Handle time slot click
  const handleTimeSlotClick = (hour: number) => {
    if (onTimeSlotSelect) {
      const startTime = `${String(hour).padStart(2, '0')}:00`
      const endTime = `${String(hour + 1).padStart(2, '0')}:00`
      onTimeSlotSelect({ start: startTime, end: endTime })
    }
  }

  // Handle event click for deletion
  const handleEventClick = (event: CalendarEvent, e: React.MouseEvent) => {
    e.stopPropagation() // Prevent date/time selection
    setSelectedMeeting(event)
    setShowDeleteModal(true)
  }

  // Handle successful deletion
  const handleDeleteSuccess = () => {
    setShowDeleteModal(false)
    setSelectedMeeting(null)
    fetchMeetings() // Refresh calendar
  }

  // Render month view
  const renderMonthView = () => {
    const year = currentDate.getFullYear()
    const month = currentDate.getMonth()

    // Get first day of month and number of days
    const firstDay = new Date(year, month, 1).getDay()
    const daysInMonth = new Date(year, month + 1, 0).getDate()

    // Build calendar grid
    const days: React.ReactElement[] = []

    // Previous month days
    for (let i = 0; i < firstDay; i++) {
      days.push(<div key={`empty-${i}`} className="h-24 border border-zinc-200 bg-zinc-50"></div>)
    }

    // Current month days
    for (let day = 1; day <= daysInMonth; day++) {
      const date = new Date(year, month, day)
      const dateStr = date.toISOString().split('T')[0]

      // Find events for this day
      const dayEvents = events.filter((event) => {
        const eventDate = new Date(event.startTime).toISOString().split('T')[0]
        return eventDate === dateStr
      })

      const isToday = dateStr === new Date().toISOString().split('T')[0]

      days.push(
        <div
          key={day}
          onClick={() => handleDateClick(date)}
          className={`h-24 cursor-pointer border border-zinc-200 p-2 transition-colors hover:bg-zinc-50 ${
            isToday ? 'border-zinc-300 bg-zinc-50' : ''
          }`}
        >
          <div
            className={`mb-1 text-sm font-medium ${isToday ? 'text-zinc-800' : 'text-zinc-700'}`}
          >
            {day}
          </div>
          <div className="space-y-1">
            {dayEvents.slice(0, 3).map((event) => (
              <div
                key={event.interactionId}
                onClick={(e) => handleEventClick(event, e)}
                className="cursor-pointer truncate rounded bg-zinc-100 px-1 py-0.5 text-xs text-zinc-800 transition-colors hover:bg-zinc-200"
                title={event.title}
              >
                {new Date(event.startTime).toLocaleTimeString(locale, {
                  hour: 'numeric',
                  minute: '2-digit',
                })}{' '}
                {event.title}
              </div>
            ))}
            {dayEvents.length > 3 && (
              <div className="text-xs text-zinc-500">
                {t('calendar.more', { count: dayEvents.length - 3 })}
              </div>
            )}
          </div>
        </div>
      )
    }

    return (
      <div className="grid grid-cols-7 gap-0 overflow-hidden rounded-lg border border-zinc-200">
        {/* Day headers */}
        {(['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'] as const).map((day) => (
          <div
            key={day}
            className="border-b border-zinc-200 bg-zinc-100 py-2 text-center text-sm font-medium text-zinc-700"
          >
            {t(`calendar.dayNames.${day}`)}
          </div>
        ))}
        {/* Calendar days */}
        {days}
      </div>
    )
  }

  // Render week view
  const renderWeekView = () => {
    const startOfWeek = new Date(currentDate)
    startOfWeek.setDate(currentDate.getDate() - currentDate.getDay())

    const weekDays: Date[] = []
    for (let i = 0; i < 7; i++) {
      const day = new Date(startOfWeek)
      day.setDate(startOfWeek.getDate() + i)
      weekDays.push(day)
    }

    const hours = Array.from({ length: 24 }, (_, i) => i)

    return (
      <div className="overflow-hidden rounded-lg border border-zinc-200">
        {/* Week header */}
        <div className="grid grid-cols-8 border-b border-zinc-200">
          <div className="bg-zinc-100 p-2 text-xs font-medium text-zinc-500">
            {t('calendar.time')}
          </div>
          {weekDays.map((day, i) => {
            const isToday =
              day.toISOString().split('T')[0] === new Date().toISOString().split('T')[0]
            return (
              <div key={i} className={`bg-zinc-100 p-2 text-center ${isToday ? 'bg-zinc-50' : ''}`}>
                <div
                  className={`text-xs font-medium ${isToday ? 'text-zinc-800' : 'text-zinc-700'}`}
                >
                  {day.toLocaleDateString(locale, { weekday: 'short' })}
                </div>
                <div className={`text-lg font-bold ${isToday ? 'text-zinc-800' : 'text-zinc-900'}`}>
                  {day.getDate()}
                </div>
              </div>
            )
          })}
        </div>

        {/* Time slots */}
        <div className="max-h-96 overflow-y-auto">
          {hours.map((hour) => (
            <div key={hour} className="grid grid-cols-8 border-b border-zinc-100">
              <div className="bg-zinc-50 p-2 text-xs text-zinc-500">
                {hour === 0
                  ? '12 AM'
                  : hour < 12
                    ? `${hour} AM`
                    : hour === 12
                      ? '12 PM'
                      : `${hour - 12} PM`}
              </div>
              {weekDays.map((day, i) => {
                const dateStr = day.toISOString().split('T')[0]
                const hourEvents = events.filter((event) => {
                  const eventDate = new Date(event.startTime)
                  const eventDateStr = eventDate.toISOString().split('T')[0]
                  const eventHour = eventDate.getHours()
                  return eventDateStr === dateStr && eventHour === hour
                })

                return (
                  <div
                    key={i}
                    onClick={() => {
                      handleDateClick(day)
                      handleTimeSlotClick(hour)
                    }}
                    className="min-h-[3rem] cursor-pointer border-l border-zinc-100 p-1 transition-colors hover:bg-zinc-50"
                  >
                    {hourEvents.map((event) => (
                      <div
                        key={event.interactionId}
                        onClick={(e) => handleEventClick(event, e)}
                        className="mb-1 cursor-pointer truncate rounded bg-zinc-100 px-1 py-0.5 text-xs text-zinc-800 transition-colors hover:bg-zinc-200"
                        title={event.title}
                      >
                        {event.title}
                      </div>
                    ))}
                  </div>
                )
              })}
            </div>
          ))}
        </div>
      </div>
    )
  }

  // Render day view
  const renderDayView = () => {
    const dateStr = currentDate.toISOString().split('T')[0]
    const hours = Array.from({ length: 24 }, (_, i) => i)

    return (
      <div className="overflow-hidden rounded-lg border border-zinc-200">
        {/* Day header */}
        <div className="border-b border-zinc-200 bg-zinc-100 p-4">
          <div className="text-sm text-zinc-600">
            {currentDate.toLocaleDateString(locale, { weekday: 'long' })}
          </div>
          <div className="title-panel">
            {currentDate.toLocaleDateString(locale, {
              month: 'long',
              day: 'numeric',
              year: 'numeric',
            })}
          </div>
        </div>

        {/* Time slots */}
        <div className="max-h-[500px] overflow-y-auto">
          {hours.map((hour) => {
            const hourEvents = events.filter((event) => {
              const eventDate = new Date(event.startTime)
              const eventDateStr = eventDate.toISOString().split('T')[0]
              const eventHour = eventDate.getHours()
              return eventDateStr === dateStr && eventHour === hour
            })

            return (
              <div
                key={hour}
                onClick={() => handleTimeSlotClick(hour)}
                className="flex cursor-pointer border-b border-zinc-100 transition-colors hover:bg-zinc-50"
              >
                <div className="w-20 border-r border-zinc-200 bg-zinc-50 p-3 text-sm text-zinc-500">
                  {hour === 0
                    ? '12 AM'
                    : hour < 12
                      ? `${hour} AM`
                      : hour === 12
                        ? '12 PM'
                        : `${hour - 12} PM`}
                </div>
                <div className="min-h-[3rem] flex-1 p-2">
                  {hourEvents.map((event) => (
                    <div
                      key={event.interactionId}
                      onClick={(e) => handleEventClick(event, e)}
                      className="mb-2 cursor-pointer rounded bg-zinc-100 px-3 py-2 text-zinc-800 transition-colors hover:bg-zinc-200"
                    >
                      <div className="text-sm font-medium">{event.title}</div>
                      <div className="mt-1 text-xs">
                        {new Date(event.startTime).toLocaleTimeString(locale, {
                          hour: 'numeric',
                          minute: '2-digit',
                        })}{' '}
                        -{' '}
                        {new Date(event.endTime).toLocaleTimeString(locale, {
                          hour: 'numeric',
                          minute: '2-digit',
                        })}
                      </div>
                      {event.attendees && event.attendees.length > 0 && (
                        <div className="mt-1 text-xs text-zinc-700">
                          {event.attendees.join(', ')}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Calendar className="h-5 w-5 text-zinc-700" />
          <h3 className="title-panel">
            {viewMode === 'month' &&
              currentDate.toLocaleDateString(locale, { month: 'long', year: 'numeric' })}
            {viewMode === 'week' &&
              t('calendar.weekOf', {
                date: currentDate.toLocaleDateString(locale, {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric',
                }),
              })}
            {viewMode === 'day' &&
              currentDate.toLocaleDateString(locale, {
                month: 'long',
                day: 'numeric',
                year: 'numeric',
              })}
          </h3>
        </div>

        <div className="flex items-center gap-2">
          {/* View mode toggle */}
          <div className="flex rounded-lg bg-zinc-100 p-1">
            <button
              onClick={() => setViewMode('month')}
              className={`rounded px-3 py-1 text-xs transition-colors ${
                viewMode === 'month'
                  ? 'bg-white text-zinc-900 shadow-sm'
                  : 'text-zinc-600 hover:text-zinc-900'
              }`}
            >
              {t('calendar.month')}
            </button>
            <button
              onClick={() => setViewMode('week')}
              className={`rounded px-3 py-1 text-xs transition-colors ${
                viewMode === 'week'
                  ? 'bg-white text-zinc-900 shadow-sm'
                  : 'text-zinc-600 hover:text-zinc-900'
              }`}
            >
              {t('calendar.week')}
            </button>
            <button
              onClick={() => setViewMode('day')}
              className={`rounded px-3 py-1 text-xs transition-colors ${
                viewMode === 'day'
                  ? 'bg-white text-zinc-900 shadow-sm'
                  : 'text-zinc-600 hover:text-zinc-900'
              }`}
            >
              {t('calendar.day')}
            </button>
          </div>

          {/* Navigation */}
          <Button variant="ghost" size="sm" onClick={() => handleNavigate(-1)} className="p-1">
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="sm" onClick={goToToday} className="px-2 text-xs">
            {t('calendar.today')}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => handleNavigate(1)} className="p-1">
            <ChevronRight className="h-4 w-4" />
          </Button>

          {/* Sync button */}
          <Button
            variant="outline"
            size="sm"
            onClick={handleSyncFromGoogle}
            disabled={syncing}
            className="text-xs"
          >
            <RefreshCw className={`mr-1 h-3 w-3 ${syncing ? 'animate-spin' : ''}`} />
            {t('calendar.sync')}
          </Button>
        </div>
      </div>

      {/* Calendar View */}
      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="flex h-full items-center justify-center">
            <RefreshCw className="h-6 w-6 animate-spin text-zinc-400" />
          </div>
        ) : (
          <>
            {viewMode === 'month' && renderMonthView()}
            {viewMode === 'week' && renderWeekView()}
            {viewMode === 'day' && renderDayView()}
          </>
        )}
      </div>

      {/* Legend */}
      <div className="mt-4 flex items-center gap-4 text-xs text-zinc-600">
        <div className="flex items-center gap-1">
          <div className="h-3 w-3 rounded bg-zinc-100"></div>
          <span>{t('calendar.customerMeetings')}</span>
        </div>
        <div className="text-zinc-500">{t('calendar.calendarHint')}</div>
      </div>

      {/* Meeting Detail Modal */}
      {showDeleteModal && selectedMeeting && (
        <MeetingDetailModal
          meeting={selectedMeeting}
          onClose={() => {
            setShowDeleteModal(false)
            setSelectedMeeting(null)
          }}
          onDelete={handleDeleteSuccess}
          googleAccessToken={googleAccessToken}
        />
      )}
    </div>
  )
}

export default GoogleCalendarView
