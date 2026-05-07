import React, { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  TrendingUp,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Mail,
  PhoneCall,
  Calendar,
  Search,
  Plus,
  FileText,
  Activity,
  User,
  Clock,
  Star,
  Trash2,
  SendHorizontal,
  MailOpen,
  Users,
  Filter,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import AddActivityModal from './AddActivityModal'
import { ConfirmationToast } from '@/components/ui/confirmation-toast'
import { useConfirmationToast } from '@/hooks/useConfirmationToast'
import { crmApiClient } from '@/lib/api/client'
import { useLocale, useTranslations } from 'next-intl'
import { toast } from 'sonner'
import type { Customer, Interaction } from '@/types/crm'
import {
  isNoteStarred,
  getStarDisplayText as getStarDisplayTextHelper,
  getEmailDirectionBadge as getEmailDirectionBadgeHelper,
  getTypeConfig,
  stripHtml,
} from '../utils/activity-helpers'

interface Note {
  id: string
  title?: string
  body?: string
  content?: string
  date: string
  updatedAt?: string
  isStarred?: boolean
  star?: string
  interactionId?: string
  author?: string
}

interface CustomerInteraction extends Omit<Interaction, 'createdAt'> {
  date: string
}

interface TimelineEvent {
  type: string
  originalType: string
  title: string
  description?: string
  date: string
  employeeName?: string
  metadata?: {
    noteId?: string
    interactionId?: string
    isStarred?: boolean
    star?: string
    theme?: string
    subject?: string
    direction?: string
    sourceName?: string
    sourceType?: string
    fromEmail?: string
    emailId?: string
    threadId?: string
  }
}

interface ThreadGroup {
  threadId: string
  subject: string
  latestEvent: TimelineEvent
  events: TimelineEvent[]
  messageCount: number
}

interface ActivityPanelProps {
  customer: Customer
  customerInteractions: CustomerInteraction[]
  loadingInteractions: boolean
  timelineFilter: string
  setTimelineFilter: (filter: string) => void
  timelineSearch: string
  setTimelineSearch: (search: string) => void
  isTimelineExpanded: boolean
  handleTimelineToggle: () => void
  expandedPanel?: string | null
  setExpandedPanel?: (panel: string | null) => void
  handleEventClick?: (event: TimelineEvent) => void
  getTimelineEvents: () => TimelineEvent[]
  onNoteAdded?: () => void
  onInteractionAdded?: () => void
  // Notes props
  notes: Note[]
  isLoadingNotes: boolean
  isRefreshingNotes: boolean
  handleDeleteNote?: (noteId: string) => Promise<void>
  handleToggleNoteStar?: (noteId: string, currentStar?: string) => void
  isDeletingNote?: string
  // Call events props
  onCallDeleted?: (callId: string) => Promise<void>
  // Employee filter props
  customerEmployees?: Array<{
    employeeId: number
    name: string
    email: string
    role: string
    department: string
  }>
  selectedEmployeeId?: number | null
  onEmployeeFilterChange?: (employeeId: number | null) => void
  currentUserEmployeeId?: number
}

const ActivityPanel: React.FC<ActivityPanelProps> = ({
  customer,
  customerInteractions,
  loadingInteractions,
  timelineFilter,
  setTimelineFilter,
  timelineSearch,
  setTimelineSearch,
  isTimelineExpanded,
  handleTimelineToggle,
  expandedPanel,
  setExpandedPanel,
  handleEventClick,
  getTimelineEvents,
  onNoteAdded,
  onInteractionAdded,
  // Notes props
  notes,
  isLoadingNotes,
  isRefreshingNotes,
  handleDeleteNote,
  handleToggleNoteStar,
  isDeletingNote,
  // Call events props
  onCallDeleted,
  // Employee filter props
  customerEmployees,
  selectedEmployeeId,
  onEmployeeFilterChange,
  currentUserEmployeeId,
}) => {
  const locale = useLocale()
  const t = useTranslations('crm')
  const [showAddActivityDropdown, setShowAddActivityDropdown] = useState(false)
  const [showAddActivityModal, setShowAddActivityModal] = useState(false)
  const [selectedActivityType, setSelectedActivityType] = useState('note')
  const [showCommunicationDropdown, setShowCommunicationDropdown] = useState(false)
  const [showEmployeeDropdown, setShowEmployeeDropdown] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const communicationDropdownRef = useRef<HTMLDivElement>(null)
  const employeeDropdownRef = useRef<HTMLDivElement>(null)

  // Confirmation toast
  const { confirm, toastProps } = useConfirmationToast()

  // Determine if viewing own data (for showing/hiding destructive actions)
  const isViewingOwnData =
    selectedEmployeeId === null ||
    selectedEmployeeId === undefined ||
    selectedEmployeeId === currentUserEmployeeId

  // Whether to show employee filter (only when >1 employee on this customer)
  const showEmployeeFilter = customerEmployees && customerEmployees.length > 1

  // Close any open dropdown when clicking outside its ref
  useEffect(() => {
    const dropdowns: Array<{
      ref: React.RefObject<HTMLDivElement | null>
      isOpen: boolean
      close: () => void
    }> = [
      { ref: dropdownRef, isOpen: showAddActivityDropdown, close: () => setShowAddActivityDropdown(false) },
      { ref: communicationDropdownRef, isOpen: showCommunicationDropdown, close: () => setShowCommunicationDropdown(false) },
      { ref: employeeDropdownRef, isOpen: showEmployeeDropdown, close: () => setShowEmployeeDropdown(false) },
    ]

    const openDropdowns = dropdowns.filter((d) => d.isOpen)
    if (openDropdowns.length === 0) return

    const handleClickOutside = (event: MouseEvent) => {
      for (const { ref, close } of openDropdowns) {
        if (ref.current && !ref.current.contains(event.target as Node)) {
          close()
        }
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [showAddActivityDropdown, showCommunicationDropdown, showEmployeeDropdown])

  // Handle activity option click
  const handleActivityOptionClick = (activityType: string) => {
    setSelectedActivityType(activityType)
    setShowAddActivityDropdown(false)
    setShowAddActivityModal(true)
  }

  // Handle delete with confirmation toast
  const handleDeleteWithConfirmation = (type: 'note' | 'call', id: string) => {
    confirm({
      title:
        type === 'note'
          ? t('activityPanel.deleteNoteConfirm')
          : t('activityPanel.deleteCallConfirm'),
      description: t('activityPanel.cannotUndo'),
      confirmLabel: t('activityPanel.deleteConfirmLabel'),
      variant: 'destructive',
      onConfirm: async () => {
        try {
          if (type === 'note' && handleDeleteNote) {
            await handleDeleteNote(id)
          } else if (type === 'call') {
            await crmApiClient.delete(`/customers/${customer.id}/call-summaries/${id}`)

            if (onCallDeleted) {
              await onCallDeleted(id)
            }
          }
          toast.success(t('activityPanel.deleteSuccess'))
        } catch (error) {
          console.error(`Error deleting ${type}:`, error)
          toast.error(t('activityPanel.deleteFailed'))
        }
      },
    })
  }

  // Helper function to check if current filter is a communication type
  const isCommunicationFilter = (): boolean => {
    return ['email', 'call', 'meeting'].includes(timelineFilter)
  }

  // Format date helper
  const formatDate = (date: string): string => {
    if (!date) return t('noteDetail.notApplicable')
    const parsedDate = new Date(date)
    if (isNaN(parsedDate.getTime())) {
      return t('noteDetail.invalidDate')
    }
    return new Intl.DateTimeFormat(locale, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    }).format(parsedDate)
  }

  // Wrappers that close over `t` for the shared helpers
  const getStarDisplayText = (star?: string): string => getStarDisplayTextHelper(star, t)
  const getEmailDirectionBadge = (direction?: string) => getEmailDirectionBadgeHelper(direction, t)

  // Get combined timeline events including notes
  const getCombinedTimelineEvents = (): TimelineEvent[] => {
    const timelineEvents = getTimelineEvents()

    // Convert notes to timeline event format
    const noteEvents: TimelineEvent[] = (notes || []).map((note) => ({
      type: 'note',
      originalType: 'note',
      title: note.title || t('noteDetail.defaultTitle'),
      description: note.body || note.content,
      date: note.date,
      employeeName: (note as any).author || t('noteDetail.defaultAuthor'),
      metadata: {
        noteId: note.id,
        isStarred: note.isStarred,
        star: note.star,
        interactionId: note.interactionId,
      },
    }))

    // Combine and sort by date
    const allEvents = [...timelineEvents, ...noteEvents]
    return allEvents.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
  }

  const combinedEvents = getCombinedTimelineEvents()

  // Filter events based on timelineFilter
  const filteredEvents =
    timelineFilter === 'all'
      ? combinedEvents
      : timelineFilter === 'note'
        ? combinedEvents.filter((e) => e.originalType === 'note')
        : combinedEvents.filter((e) => e.originalType === timelineFilter)

  // Thread grouping: group emails by threadId, keep non-emails as-is
  const [expandedThreads, setExpandedThreads] = useState<Set<string>>(new Set())

  const groupedItems = React.useMemo(() => {
    const items: Array<{ kind: 'event'; event: TimelineEvent } | { kind: 'thread'; thread: ThreadGroup }> = []
    const threadMap = new Map<string, TimelineEvent[]>()
    const standalone: TimelineEvent[] = []

    for (const event of filteredEvents) {
      const tid = event.metadata?.threadId
      if (event.originalType === 'email' && tid) {
        const arr = threadMap.get(tid) || []
        arr.push(event)
        threadMap.set(tid, arr)
      } else {
        standalone.push(event)
      }
    }

    // Convert thread groups (2+ emails) into ThreadGroup items; singletons stay as events
    const threadGroups: ThreadGroup[] = []
    for (const [threadId, events] of threadMap) {
      if (events.length >= 2) {
        // Events are already sorted newest-first from the combined sort
        const latestEvent = events[0]
        const subject = (latestEvent.title || '').replace(/^(Re:|Fwd:|转发:|回���:)\s*/gi, '').trim()
        threadGroups.push({ threadId, subject: subject || latestEvent.title, latestEvent, events, messageCount: events.length })
      } else {
        standalone.push(...events)
      }
    }

    // Merge threads and standalone events, sort by date
    const allItems: Array<{ date: string; item: typeof items[number] }> = []
    for (const event of standalone) {
      allItems.push({ date: event.date, item: { kind: 'event', event } })
    }
    for (const thread of threadGroups) {
      allItems.push({ date: thread.latestEvent.date, item: { kind: 'thread', thread } })
    }
    allItems.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())

    return allItems.map(a => a.item)
  }, [filteredEvents])

  const TIMELINE_COLLAPSED_LIMIT = 3
  const displayedItems = isTimelineExpanded
    ? groupedItems
    : groupedItems.slice(0, TIMELINE_COLLAPSED_LIMIT)


  return (
    <>
      <div
        className={`flex flex-col rounded-lg border border-rule bg-bone transition-all duration-300 ${
          expandedPanel === 'activity'
            ? 'h-[calc(1000px+1rem-60px-1rem)] p-6'
            : expandedPanel === 'summary'
              ? 'h-[60px] overflow-visible px-6 py-3'
              : 'h-[500px] p-6'
        }`}
      >
        {/* Header with Add Activity Button */}
        <div
          className={`flex flex-shrink-0 items-center justify-between ${expandedPanel === 'summary' ? 'mb-0' : 'mb-4'}`}
        >
          <h3 className="title-panel flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-deep" />
            {t('activityPanel.title')}
            {(loadingInteractions || isLoadingNotes || isRefreshingNotes) && (
              <RefreshCw className="h-4 w-4 animate-spin" />
            )}
          </h3>
          <div className="flex flex-shrink-0 items-center gap-2">
            {/* Add Activity Dropdown (only when viewing own data) */}
            {isViewingOwnData && (
              <div className="relative" ref={dropdownRef}>
                <button
                  onClick={() => setShowAddActivityDropdown(!showAddActivityDropdown)}
                  className="flex items-center gap-2 rounded-lg bg-deep px-4 py-2 text-sm font-medium whitespace-nowrap text-bone transition-colors hover:bg-deep"
                >
                  <Plus className="h-4 w-4" />
                  {t('activityPanel.addActivity')}
                  <ChevronDown className="h-4 w-4" />
                </button>

                {/* Dropdown Menu */}
                {showAddActivityDropdown && (
                  <div className="absolute right-0 z-50 mt-2 w-56 rounded-lg border border-rule bg-bone py-2 shadow-lg">
                    <button
                      onClick={() => handleActivityOptionClick('meeting')}
                      className="flex w-full items-center gap-3 px-4 py-2 text-sm text-ink transition-colors hover:bg-cream"
                    >
                      <Calendar className="h-4 w-4 text-ink" />
                      {t('activityPanel.scheduleMeeting')}
                    </button>
                    <button
                      onClick={() => handleActivityOptionClick('note')}
                      className="flex w-full items-center gap-3 px-4 py-2 text-sm text-ink transition-colors hover:bg-cream"
                    >
                      <FileText className="h-4 w-4 text-deep" />
                      {t('activityPanel.addNote')}
                    </button>
                    <button
                      onClick={() => handleActivityOptionClick('callSummary')}
                      className="flex w-full items-center gap-3 px-4 py-2 text-sm text-ink transition-colors hover:bg-cream"
                    >
                      <PhoneCall className="h-4 w-4 text-accent" />
                      {t('activityPanel.addCallSummary')}
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Expand/Collapse Button */}
            {setExpandedPanel && (
              <button
                onClick={() => setExpandedPanel(expandedPanel === 'activity' ? null : 'activity')}
                className="flex-shrink-0 rounded p-1 text-mute transition-colors hover:bg-cream hover:text-ink"
                title={
                  expandedPanel === 'activity'
                    ? t('activityPanel.collapse')
                    : t('activityPanel.expand')
                }
              >
                {expandedPanel === 'activity' ? (
                  <ChevronUp className="h-5 w-5" />
                ) : (
                  <ChevronDown className="h-5 w-5" />
                )}
              </button>
            )}
          </div>
        </div>

        {expandedPanel !== 'summary' && (
          <>
            {/* Event Type Filters - Always Visible */}
            <div className="mb-6 flex flex-shrink-0 flex-col gap-4 sm:flex-row">
              {/* Filter Buttons */}
              <div className="flex items-center gap-2">
                {/* All Filter Button */}
                <button
                  onClick={() => setTimelineFilter('all')}
                  className={`flex h-7 items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                    timelineFilter === 'all'
                      ? 'bg-deep text-bone'
                      : 'bg-cream text-mute hover:bg-fog'
                  }`}
                >
                  <Filter className="h-3 w-3" />
                  {t('activityPanel.filterAll')}
                </button>

                {/* Communication Button with Dropdown */}
                <div className="relative" ref={communicationDropdownRef}>
                  <button
                    onClick={() => setShowCommunicationDropdown(!showCommunicationDropdown)}
                    className={`flex h-7 items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                      isCommunicationFilter()
                        ? 'border border-rule bg-cream text-deep'
                        : 'bg-cream text-mute hover:bg-fog'
                    }`}
                  >
                    <Activity className="h-3 w-3" />
                    {t('activityPanel.filterCommunication')}
                    <ChevronDown className="h-3 w-3" />
                  </button>

                  {/* Dropdown Menu */}
                  {showCommunicationDropdown && (
                    <div className="absolute top-full left-0 z-50 mt-1 w-40 rounded-lg border border-rule bg-bone py-1 shadow-lg">
                      <button
                        onClick={() => {
                          setTimelineFilter('email')
                          setShowCommunicationDropdown(false)
                        }}
                        className={`flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors hover:bg-cream ${
                          timelineFilter === 'email' ? 'bg-cream text-deep' : 'text-ink'
                        }`}
                      >
                        <Mail className="h-4 w-4 text-deep" />
                        {t('activityPanel.filterEmail')}
                      </button>
                      <button
                        onClick={() => {
                          setTimelineFilter('call')
                          setShowCommunicationDropdown(false)
                        }}
                        className={`flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors hover:bg-cream ${
                          timelineFilter === 'call' ? 'bg-accent-lo text-accent' : 'text-ink'
                        }`}
                      >
                        <PhoneCall className="h-4 w-4 text-accent" />
                        {t('activityPanel.filterCall')}
                      </button>
                      <button
                        onClick={() => {
                          setTimelineFilter('meeting')
                          setShowCommunicationDropdown(false)
                        }}
                        className={`flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors hover:bg-cream ${
                          timelineFilter === 'meeting'
                            ? 'bg-cream text-ink'
                            : 'text-ink'
                        }`}
                      >
                        <Calendar className="h-4 w-4 text-ink" />
                        {t('activityPanel.filterMeeting')}
                      </button>
                    </div>
                  )}
                </div>

                {/* Notes Button */}
                <button
                  onClick={() => setTimelineFilter('note')}
                  className={`flex h-7 items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                    timelineFilter === 'note'
                      ? 'border border-rule bg-cream text-deep'
                      : 'bg-cream text-mute hover:bg-fog'
                  }`}
                >
                  <FileText className="h-3 w-3" />
                  {t('activityPanel.filterNotes')}
                </button>
                {/* Employee Filter */}
                {showEmployeeFilter && (
                  <div className="relative" ref={employeeDropdownRef}>
                    <button
                      onClick={() => setShowEmployeeDropdown(!showEmployeeDropdown)}
                      className={`flex h-7 items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                        selectedEmployeeId !== null && selectedEmployeeId !== undefined
                          ? 'border border-rule bg-cream text-deep'
                          : 'bg-cream text-mute hover:bg-fog'
                      }`}
                    >
                      <Users className="h-3 w-3" />
                      {selectedEmployeeId === null || selectedEmployeeId === undefined
                        ? t('activityPanel.myActivity')
                        : selectedEmployeeId === 0
                          ? t('activityPanel.allEmployees')
                          : customerEmployees?.find((e) => e.employeeId === selectedEmployeeId)
                              ?.name || t('interactionDetail.employee')}
                      <ChevronDown className="h-3 w-3" />
                    </button>

                    {showEmployeeDropdown && (
                      <div className="absolute top-full left-0 z-50 mt-1 w-44 rounded-lg border border-rule bg-bone py-1 shadow-lg">
                        <button
                          onClick={() => {
                            onEmployeeFilterChange?.(null)
                            setShowEmployeeDropdown(false)
                          }}
                          className={`flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors hover:bg-cream ${
                            selectedEmployeeId === null || selectedEmployeeId === undefined
                              ? 'bg-cream text-deep'
                              : 'text-ink'
                          }`}
                        >
                          <User className="h-4 w-4 text-ink" />
                          {t('activityPanel.myActivity')}
                        </button>
                        <button
                          onClick={() => {
                            onEmployeeFilterChange?.(0)
                            setShowEmployeeDropdown(false)
                          }}
                          className={`flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors hover:bg-cream ${
                            selectedEmployeeId === 0 ? 'bg-cream text-deep' : 'text-ink'
                          }`}
                        >
                          <Users className="h-4 w-4 text-ink" />
                          {t('activityPanel.allEmployees')}
                        </button>
                        {customerEmployees!.map((emp) => (
                          <button
                            key={emp.employeeId}
                            onClick={() => {
                              onEmployeeFilterChange?.(emp.employeeId)
                              setShowEmployeeDropdown(false)
                            }}
                            className={`flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors hover:bg-cream ${
                              selectedEmployeeId === emp.employeeId
                                ? 'bg-cream text-deep'
                                : 'text-ink'
                            }`}
                          >
                            <User className="h-4 w-4 text-ink" />
                            {emp.name}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Search Bar */}
              <div className="relative max-w-xs flex-1">
                <Search className="absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 transform text-mute" />
                <input
                  type="text"
                  placeholder={t('activityPanel.searchPlaceholder')}
                  value={timelineSearch}
                  onChange={(e) => setTimelineSearch(e.target.value)}
                  className="w-full rounded-lg border border-rule py-2 pr-4 pl-10 text-sm focus:border-transparent focus:ring-2 focus:border-accent focus:outline-none"
                />
              </div>
            </div>

            {/* Timeline Content */}
            <div className="flex-1 overflow-y-auto">
              <div className="space-y-4 p-6">
                {groupedItems.length > 0 ? (
                  <AnimatePresence>
                    {displayedItems.map((item, index) => {
                      if (item.kind === 'thread') {
                        const { thread } = item
                        const isExpanded = expandedThreads.has(thread.threadId)
                        const latestDir = thread.latestEvent.metadata?.direction?.toLowerCase()
                        const isSent = latestDir === 'sent'
                        const LatestIcon = isSent ? SendHorizontal : MailOpen
                        const threadBorder = isSent ? 'border-l-2 border-l-rule' : 'border-l-2 border-l-fog'

                        return (
                          <motion.div
                            key={`thread-${thread.threadId}`}
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                            transition={{ duration: 0.2 }}
                            className={`group relative rounded-lg border border-rule bg-bone transition-all hover:shadow-md ${threadBorder}`}
                          >
                            {/* Thread header — always visible */}
                            <div
                              className="flex cursor-pointer gap-4 p-4"
                              onClick={() => handleEventClick && handleEventClick(thread.latestEvent)}
                            >
                              <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-cream">
                                <LatestIcon className="h-5 w-5 text-deep" />
                              </div>
                              <div className="min-w-0 flex-1">
                                <div className="mb-1 flex items-start justify-between gap-2">
                                  <div className="flex min-w-0 flex-1 items-center gap-2">
                                    <h4 className="title-block">{thread.subject}</h4>
                                    {thread.latestEvent.metadata?.direction && (() => {
                                      const badge = getEmailDirectionBadge(thread.latestEvent.metadata.direction)
                                      return badge ? <Badge variant={badge.variant} className="flex-shrink-0">{badge.label}</Badge> : null
                                    })()}
                                    <span className="flex-shrink-0 rounded-full bg-cream px-2 py-0.5 text-xs text-mute">
                                      {thread.messageCount} {t('activityPanel.threadMessages')}
                                    </span>
                                  </div>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation()
                                      setExpandedThreads(prev => {
                                        const next = new Set(prev)
                                        if (next.has(thread.threadId)) next.delete(thread.threadId)
                                        else next.add(thread.threadId)
                                        return next
                                      })
                                    }}
                                    className="flex-shrink-0 rounded px-2 py-1 text-xs text-mute hover:bg-cream hover:text-ink"
                                  >
                                    {isExpanded ? t('activityPanel.threadCollapse') : t('activityPanel.threadExpand')}
                                  </button>
                                </div>
                                <p className="mb-2 line-clamp-2 text-sm text-mute">
                                  {thread.latestEvent.description ? stripHtml(thread.latestEvent.description) : ''}
                                </p>
                                <div className="flex items-center gap-4 text-xs text-mute">
                                  <div className="flex items-center gap-1">
                                    <User className="h-3 w-3" />
                                    {thread.latestEvent.employeeName}
                                  </div>
                                  <div className="flex items-center gap-1">
                                    <Clock className="h-3 w-3" />
                                    {formatDate(thread.latestEvent.date)}
                                  </div>
                                </div>
                              </div>
                            </div>

                            {/* Expanded thread messages */}
                            <AnimatePresence>
                              {isExpanded && (
                                <motion.div
                                  initial={{ height: 0, opacity: 0 }}
                                  animate={{ height: 'auto', opacity: 1 }}
                                  exit={{ height: 0, opacity: 0 }}
                                  transition={{ duration: 0.2 }}
                                  className="overflow-hidden border-t border-rule"
                                >
                                  {thread.events.slice(1).map((ev, i) => {
                                    const evSent = ev.metadata?.direction?.toLowerCase() === 'sent'
                                    const EvIcon = evSent ? SendHorizontal : MailOpen
                                    return (
                                      <div
                                        key={`${thread.threadId}-${i}`}
                                        className="flex cursor-pointer gap-4 border-b border-rule px-4 py-3 last:border-b-0 hover:bg-cream"
                                        onClick={() => handleEventClick && handleEventClick(ev)}
                                      >
                                        <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded bg-paper">
                                          <EvIcon className="h-4 w-4 text-mute" />
                                        </div>
                                        <div className="min-w-0 flex-1">
                                          <p className="line-clamp-1 text-sm text-ink">{ev.description ? stripHtml(ev.description) : ''}</p>
                                          <div className="flex items-center gap-3 text-xs text-mute">
                                            <span>{ev.employeeName}</span>
                                            <span>{formatDate(ev.date)}</span>
                                          </div>
                                        </div>
                                      </div>
                                    )
                                  })}
                                </motion.div>
                              )}
                            </AnimatePresence>
                          </motion.div>
                        )
                      }

                      // Single event card (non-threaded)
                      const { event } = item
                      const typeConfig = getTypeConfig(event.originalType)
                      const isEmail = event.originalType === 'email'
                      const isSent = isEmail && event.metadata?.direction?.toLowerCase() === 'sent'
                      const TypeIcon = isEmail ? (isSent ? SendHorizontal : MailOpen) : typeConfig.icon
                      const emailBorderClass = isEmail ? (isSent ? 'border-l-2 border-l-rule' : 'border-l-2 border-l-fog') : ''

                      const isNote = event.originalType === 'note'

                      return (
                        <motion.div
                          key={`${event.type || 'event'}-${event.date || index}-${event.metadata?.noteId || event.metadata?.interactionId || index}`}
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -10 }}
                          transition={{ duration: 0.2 }}
                          className={`group relative rounded-lg border bg-bone p-4 transition-all ${
                            isNote
                              ? event.metadata?.isStarred
                                ? 'border-gold-lo bg-gold-lo hover:shadow-md'
                                : 'border-rule hover:shadow-md'
                              : 'border-rule hover:shadow-md'
                          } ${emailBorderClass}`}
                        >
                          {/* Trash icon button for note and call events (only when viewing own data) */}
                          {isViewingOwnData && (isNote || event.originalType === 'call') && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                if (isNote && event.metadata?.noteId) {
                                  handleDeleteWithConfirmation('note', event.metadata.noteId)
                                } else if (event.originalType === 'call') {
                                  const interactionId = event.metadata?.interactionId
                                  if (interactionId) {
                                    handleDeleteWithConfirmation('call', interactionId)
                                  }
                                }
                              }}
                              disabled={isDeletingNote === event.metadata?.noteId}
                              className="absolute top-2 right-2 rounded p-1.5 text-mute opacity-0 transition-colors group-hover:opacity-100 hover:bg-threat-lo hover:text-threat"
                              title={t('activityPanel.deleteConfirmLabel')}
                            >
                              {isDeletingNote === event.metadata?.noteId ? (
                                <RefreshCw className="h-4 w-4 animate-spin" />
                              ) : (
                                <Trash2 className="h-4 w-4" />
                              )}
                            </button>
                          )}

                          <div
                            className="flex gap-4"
                            onClick={() => handleEventClick && handleEventClick(event)}
                          >
                            {/* Icon */}
                            <div
                              className={`h-10 w-10 flex-shrink-0 ${typeConfig.bgColor} flex items-center justify-center rounded-lg`}
                            >
                              <TypeIcon className={`h-5 w-5 ${typeConfig.textColor}`} />
                            </div>

                            {/* Content */}
                            <div className="min-w-0 flex-1">
                              <div className="mb-1 flex items-start justify-between gap-2">
                                <div className="flex min-w-0 flex-1 items-center gap-2">
                                  <h4
                                    className={`text-sm font-semibold text-deep transition-colors group-hover:text-deep`}
                                  >
                                    {event.title}
                                  </h4>
                                  {/* Email Direction Badge */}
                                  {event.originalType === 'email' &&
                                    event.metadata?.direction &&
                                    (() => {
                                      const directionBadge = getEmailDirectionBadge(
                                        event.metadata.direction
                                      )
                                      if (!directionBadge) return null
                                      return (
                                        <Badge
                                          variant={directionBadge.variant}
                                          className="flex-shrink-0"
                                        >
                                          {directionBadge.label}
                                        </Badge>
                                      )
                                    })()}
                                  {/* Note Star Badge */}
                                  {isNote && event.metadata?.isStarred && (
                                    <div className="flex flex-shrink-0 items-center gap-1 rounded-full bg-gold-lo px-1.5 py-0.5 text-xs text-gold">
                                      <Star className="h-2.5 w-2.5 fill-gold text-gold" />
                                      {getStarDisplayText(event.metadata.star)}
                                    </div>
                                  )}
                                </div>
                              </div>

                              <p className="mb-2 line-clamp-2 text-sm text-mute">
                                {event.description && event.originalType === 'email' ? stripHtml(event.description) : event.description}
                              </p>

                              <div className="flex items-center gap-4 text-xs text-mute">
                                <div className="flex items-center gap-1">
                                  <User className="h-3 w-3" />
                                  {event.employeeName}
                                </div>
                                <div className="flex items-center gap-1">
                                  <Clock className="h-3 w-3" />
                                  {formatDate(event.date)}
                                </div>
                              </div>
                            </div>
                          </div>
                        </motion.div>
                      )
                    })}
                  </AnimatePresence>
                ) : (
                  <div className="py-12 text-center">
                    <Activity className="mx-auto mb-3 h-12 w-12 text-fog" />
                    <p className="mb-1 font-medium text-mute">
                      {timelineFilter !== 'all'
                        ? timelineFilter === 'note'
                          ? t('activityPanel.emptyNotes')
                          : timelineFilter === 'email'
                            ? t('activityPanel.emptyEmails')
                            : timelineFilter === 'call'
                              ? t('activityPanel.emptyCalls')
                              : t('activityPanel.emptyMeetings')
                        : t('activityPanel.emptyState')}
                    </p>
                    <p className="text-sm text-mute">
                      {timelineSearch
                        ? t('activityPanel.adjustSearch')
                        : t('activityPanel.emptyStateDescription')}
                    </p>
                  </div>
                )}

                {/* Show More/Less Button */}
                {groupedItems.length > TIMELINE_COLLAPSED_LIMIT && (
                  <button
                    onClick={handleTimelineToggle}
                    className="w-full py-2 text-sm font-medium text-deep transition-colors hover:text-deep"
                  >
                    {isTimelineExpanded
                      ? t('activityPanel.showLess')
                      : t('activityPanel.showMore', {
                          count: filteredEvents.length - TIMELINE_COLLAPSED_LIMIT,
                        })}
                  </button>
                )}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Add Activity Modal */}
      <AddActivityModal
        isOpen={showAddActivityModal}
        onClose={() => setShowAddActivityModal(false)}
        customer={customer}
        onNoteAdded={onNoteAdded}
        onInteractionAdded={onInteractionAdded}
        initialActivityType={selectedActivityType}
      />

      {/* Confirmation Toast */}
      <ConfirmationToast {...toastProps} />
    </>
  )
}

export default ActivityPanel
