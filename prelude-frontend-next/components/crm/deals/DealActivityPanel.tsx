import React, { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Plus,
  FileText,
  PhoneCall,
  Calendar,
  Clock,
  User,
  Star,
  RefreshCw,
  Filter,
  Search,
  TrendingUp,
  ChevronDown,
  ChevronUp,
  Activity,
  Mail,
  MessageSquare,
  Trash2,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import AddDealActivityModal from './AddDealActivityModal'
import { ConfirmationToast } from '@/components/ui/confirmation-toast'
import { useConfirmationToast } from '@/hooks/useConfirmationToast'
import { crmApiClient } from '@/lib/api/client'
import { useLocale, useTranslations } from 'next-intl'
import { toast } from 'sonner'
import type { Deal } from '@/types/crm'

interface Note {
  noteId: string
  title?: string
  body: string
  star?: string
  createdAt: string
  employeeName?: string
}

interface Activity {
  noteId?: string
  interactionId?: string
  activityType: string
  title?: string
  body?: string
  content?: string
  theme?: string
  subject?: string
  description?: string
  createdAt: string
  employeeName?: string
  star?: string
}

interface ActivityData {
  notes: Note[]
  interactions: any[]
  timeline: Activity[]
}

interface DealActivityPanelProps {
  deal: Deal
  onActivityAdded?: () => void
  expandedPanel?: string | null
  setExpandedPanel?: (panel: string | null) => void
  handleEventClick?: (activity: Activity) => void
  notes?: Note[]
  isDeletingNote?: string
  handleDeleteNote?: (noteId: string) => Promise<void>
  onCallDeleted?: (callId: string) => Promise<void>
}

const DealActivityPanel: React.FC<DealActivityPanelProps> = ({
  deal,
  onActivityAdded,
  expandedPanel,
  setExpandedPanel,
  handleEventClick,
  notes = [],
  isDeletingNote,
  handleDeleteNote,
  onCallDeleted,
}) => {
  const locale = useLocale()
  const t = useTranslations('crm')
  const [activities, setActivities] = useState<ActivityData>({
    notes: [],
    interactions: [],
    timeline: [],
  })
  const [isLoading, setIsLoading] = useState(false)
  const [showAddActivityModal, setShowAddActivityModal] = useState(false)
  const [showAddActivityDropdown, setShowAddActivityDropdown] = useState(false)
  const [selectedActivityType, setSelectedActivityType] = useState('note')
  const [filterType, setFilterType] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [showCommunicationDropdown, setShowCommunicationDropdown] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const communicationDropdownRef = useRef<HTMLDivElement>(null)

  // Confirmation toast
  const { confirm, toastProps } = useConfirmationToast()

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowAddActivityDropdown(false)
      }
    }

    if (showAddActivityDropdown) {
      document.addEventListener('mousedown', handleClickOutside)
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [showAddActivityDropdown])

  // Close communication dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        communicationDropdownRef.current &&
        !communicationDropdownRef.current.contains(event.target as Node)
      ) {
        setShowCommunicationDropdown(false)
      }
    }

    if (showCommunicationDropdown) {
      document.addEventListener('mousedown', handleClickOutside)
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [showCommunicationDropdown])

  // Load activities when deal changes
  useEffect(() => {
    if (deal?.dealId) {
      loadActivities()
    }
  }, [deal?.dealId])

  const loadActivities = async () => {
    if (!deal?.dealId) return

    setIsLoading(true)
    try {
      const data = await crmApiClient.get<ActivityData>(`/deals/${deal.dealId}/activities`)
      setActivities(data)
    } catch (error) {
      console.error('Error loading deal activities:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleActivityAdded = async () => {
    await loadActivities()
    if (onActivityAdded) {
      onActivityAdded()
    }
  }

  const handleActivityOptionClick = (activityType: string) => {
    setSelectedActivityType(activityType)
    setShowAddActivityDropdown(false)
    setShowAddActivityModal(true)
  }

  // Helper function to check if current filter is a communication type
  const isCommunicationFilter = () => {
    return ['email', 'call', 'meeting'].includes(filterType)
  }

  // Filter activities based on type and search
  const getFilteredActivities = () => {
    let filtered = activities.timeline || []

    // Filter by type
    if (filterType !== 'all') {
      filtered = filtered.filter((activity) => {
        if (filterType === 'notes') return activity.activityType === 'note'
        if (filterType === 'email') return activity.activityType === 'email'
        if (filterType === 'calls') return activity.activityType === 'call'
        if (filterType === 'meetings') return activity.activityType === 'meet'
        return true
      })
    }

    // Filter by search query
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      filtered = filtered.filter((activity) => {
        const title = activity.title?.toLowerCase() || ''
        const body = activity.body?.toLowerCase() || ''
        const content = activity.content?.toLowerCase() || ''
        const theme = activity.theme?.toLowerCase() || ''
        return (
          title.includes(query) ||
          body.includes(query) ||
          content.includes(query) ||
          theme.includes(query)
        )
      })
    }

    return filtered
  }

  const formatDate = (dateString: string): string => {
    if (!dateString) return t('noteDetail.notApplicable')
    const date = new Date(dateString)
    return new Intl.DateTimeFormat(locale, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date)
  }

  const getTypeConfig = (type: string) => {
    switch (type) {
      case 'note':
        return {
          icon: FileText,
          bgColor: 'bg-cream',
          textColor: 'text-ink',
        }
      case 'call':
        // Communication type, not success — keep neutral per kit rule.
        return {
          icon: PhoneCall,
          bgColor: 'bg-cream',
          textColor: 'text-ink',
        }
      case 'meeting':
      case 'meet':
        return {
          icon: Calendar,
          bgColor: 'bg-cream',
          textColor: 'text-ink',
        }
      case 'email':
        return {
          icon: Mail,
          bgColor: 'bg-cream',
          textColor: 'text-ink',
        }
      case 'quote_request':
        // Quote requests are warning-band metadata (warrants attention) — gold.
        return {
          icon: MessageSquare,
          bgColor: 'bg-gold-lo',
          textColor: 'text-gold',
        }
      default:
        return {
          icon: FileText,
          bgColor: 'bg-cream',
          textColor: 'text-mute',
        }
    }
  }

  const getStarDisplayText = (star?: string): string => {
    if (star === 'important') return t('activityPanel.starImportant')
    return ''
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
          if (type === 'note') {
            if (handleDeleteNote) {
              await handleDeleteNote(id)
            }
          } else if (type === 'call') {
            await crmApiClient.delete(`/deals/${deal.dealId}/call-summaries/${id}`)

            if (onCallDeleted) {
              await onCallDeleted(id)
            }
          }
          await loadActivities()
          toast.success(t('activityPanel.deleteSuccess'))
        } catch (error) {
          console.error(`Error deleting ${type}:`, error)
          toast.error(t('activityPanel.deleteFailed'))
        }
      },
    })
  }

  const filteredActivities = getFilteredActivities()

  return (
    <div className="flex h-full flex-col rounded-lg border border-rule bg-bone p-6">
      {/* Header */}
      <div className="mb-6 flex flex-shrink-0 items-center justify-between">
        <h3 className="title-panel flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-deep" />
          {t('activityPanel.title')}
          {isLoading && <RefreshCw className="h-4 w-4 animate-spin" />}
        </h3>
        <div className="flex flex-shrink-0 items-center gap-2">
          {/* Add Activity Dropdown */}
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setShowAddActivityDropdown(!showAddActivityDropdown)}
              className="flex items-center gap-2 rounded-lg bg-deep px-4 py-2 text-sm font-medium whitespace-nowrap text-bone transition-colors hover:bg-deep/90"
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
                  <FileText className="h-4 w-4 text-ink" />
                  {t('activityPanel.addNote')}
                </button>
                <button
                  onClick={() => handleActivityOptionClick('callSummary')}
                  className="flex w-full items-center gap-3 px-4 py-2 text-sm text-ink transition-colors hover:bg-cream"
                >
                  <PhoneCall className="h-4 w-4 text-mute" />
                  {t('activityPanel.addCallSummary')}
                </button>
              </div>
            )}
          </div>

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

      {/* Event Type Filters */}
      {(!expandedPanel || expandedPanel !== 'summary') && (
        <div className="mb-6 flex flex-shrink-0 flex-col gap-4 sm:flex-row">
          {/* Filter Buttons */}
          <div className="flex flex-wrap items-center gap-2">
            {/* All Button */}
            <button
              onClick={() => setFilterType('all')}
              className={`flex h-7 items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                filterType === 'all'
                  ? 'border border-rule bg-cream text-ink'
                  : 'bg-cream text-mute hover:bg-paper'
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
                    ? 'border border-rule bg-cream text-ink'
                    : 'bg-cream text-mute hover:bg-paper'
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
                      setFilterType('email')
                      setShowCommunicationDropdown(false)
                    }}
                    className={`flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors hover:bg-cream ${
                      filterType === 'email' ? 'bg-paper text-ink' : 'text-ink'
                    }`}
                  >
                    <Mail className="h-4 w-4 text-ink" />
                    {t('activityPanel.filterEmail')}
                  </button>
                  <button
                    onClick={() => {
                      setFilterType('calls')
                      setShowCommunicationDropdown(false)
                    }}
                    className={`flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors hover:bg-cream ${
                      filterType === 'calls' ? 'bg-cream text-ink' : 'text-ink'
                    }`}
                  >
                    <PhoneCall className="h-4 w-4 text-mute" />
                    {t('activityPanel.filterCall')}
                  </button>
                  <button
                    onClick={() => {
                      setFilterType('meetings')
                      setShowCommunicationDropdown(false)
                    }}
                    className={`flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors hover:bg-cream ${
                      filterType === 'meetings' ? 'bg-paper text-ink' : 'text-ink'
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
              onClick={() => setFilterType('notes')}
              className={`flex h-7 items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                filterType === 'notes'
                  ? 'border border-rule bg-cream text-ink'
                  : 'bg-cream text-mute hover:bg-paper'
              }`}
            >
              <FileText className="h-3 w-3" />
              {t('activityPanel.filterNotes')}
            </button>
          </div>

          {/* Search Bar */}
          <div className="relative min-w-[200px] flex-1">
            <Search className="absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 transform text-mute" />
            <input
              type="text"
              placeholder={t('dealActivityPanel.searchPlaceholder')}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded border border-rule bg-bone py-1.5 pr-4 pl-10 text-sm focus:ring-2 focus:border-accent focus:outline-none"
            />
          </div>
        </div>
      )}

      {/* Activities Timeline */}
      <div className="max-h-[400px] flex-1 space-y-3 overflow-y-auto">
        {isLoading ? (
          <div className="py-8 text-center text-mute">
            <RefreshCw className="mx-auto mb-2 h-6 w-6 animate-spin" />
            {t('dealActivityPanel.loading')}
          </div>
        ) : filteredActivities.length === 0 ? (
          <div className="py-8 text-center text-mute">
            <FileText className="mx-auto mb-3 h-12 w-12 text-mute" />
            <p className="text-sm">{t('dealActivityPanel.emptyState')}</p>
            <p className="mt-1 text-xs text-mute">{t('dealActivityPanel.emptyStateHelper')}</p>
          </div>
        ) : (
          filteredActivities.map((activity, index) => {
            const typeConfig = getTypeConfig(activity.activityType)
            const TypeIcon = typeConfig.icon
            const isNote = activity.activityType === 'note'
            const isCall = activity.activityType === 'call'

            return (
              <motion.div
                key={`${activity.activityType}-${activity.noteId || activity.interactionId}-${index}`}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
                className={`group relative rounded-lg border bg-bone p-4 transition-all ${
                  isNote
                    ? activity.star === 'important'
                      ? 'border-gold/30 bg-gold-lo/40 hover:shadow-md'
                      : 'border-rule hover:shadow-md'
                    : 'border-rule hover:shadow-md'
                }`}
              >
                {/* Trash icon button for note and call events */}
                {(isNote || isCall) && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      if (isNote && activity.noteId) {
                        handleDeleteWithConfirmation('note', activity.noteId)
                      } else if (isCall && activity.interactionId) {
                        handleDeleteWithConfirmation('call', activity.interactionId)
                      }
                    }}
                    disabled={isDeletingNote === activity.noteId}
                    className="absolute top-2 right-2 rounded p-1.5 text-mute opacity-0 transition-colors group-hover:opacity-100 hover:bg-threat-lo hover:text-threat"
                    title={t('activityPanel.deleteConfirmLabel')}
                  >
                    {isDeletingNote === activity.noteId ? (
                      <RefreshCw className="h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                  </button>
                )}

                <div
                  className="flex gap-4"
                  onClick={() => handleEventClick && handleEventClick(activity)}
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
                        <h4 className="title-block transition-colors">
                          {activity.activityType === 'email'
                            ? activity.theme ||
                              activity.subject ||
                              (activity.content
                                ? activity.content.substring(0, 50) +
                                  (activity.content.length > 50 ? '...' : '')
                                : t('interactionDetail.noSubject'))
                            : activity.title ||
                              activity.theme ||
                              `${activity.activityType === 'note' ? t('interactions.note') : activity.activityType === 'call' ? t('interactions.call') : t('interactions.meeting')}`}
                        </h4>
                        {isNote && activity.star === 'important' && (
                          <div className="flex flex-shrink-0 items-center gap-1 rounded-full bg-gold-lo px-1.5 py-0.5 text-xs text-gold">
                            <Star className="h-2.5 w-2.5 fill-gold text-gold" />
                            {getStarDisplayText(activity.star)}
                          </div>
                        )}
                      </div>
                    </div>

                    <p className="mb-2 line-clamp-2 text-sm text-mute">
                      {activity.activityType === 'note' && activity.body}
                      {activity.activityType === 'call' && activity.content}
                      {activity.activityType === 'email' && (activity.content || '')}
                      {(activity.activityType === 'meet' || activity.activityType === 'meeting') &&
                        activity.description}
                    </p>

                    <div className="flex items-center gap-4 text-xs text-mute">
                      <div className="flex items-center gap-1">
                        <User className="h-3 w-3" />
                        {activity.employeeName || t('interactionDetail.unknown')}
                      </div>
                      <div className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        <span className="tabular-nums">{formatDate(activity.createdAt)}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </motion.div>
            )
          })
        )}
      </div>

      {/* Add Activity Modal */}
      <AddDealActivityModal
        isOpen={showAddActivityModal}
        onClose={() => setShowAddActivityModal(false)}
        deal={deal}
        onActivityAdded={handleActivityAdded}
        initialActivityType={selectedActivityType}
      />

      {/* Confirmation Toast */}
      <ConfirmationToast {...toastProps} />
    </div>
  )
}

export default DealActivityPanel
