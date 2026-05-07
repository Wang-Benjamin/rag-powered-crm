'use client'

import React, { Fragment, useState, useEffect, useCallback } from 'react'
import {
  Home,
  RefreshCw,
  AlertCircle,
  DoorOpen,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { PageLoader } from '@/components/ui/page-loader'
import { toast } from 'sonner'
import { crmService } from '@/lib/api/crm'
import NoteDetailsModal from '../interactions/NoteDetailsModal'
import InteractionDetailsModal from '../interactions/InteractionDetailsModal'
import CRMMeetingDetailsModal from '../interactions/CRMMeetingDetailsModal'
import { useCRM } from '@/contexts/CRMContext'
import { useAuth } from '@/hooks/useAuth'

import { crmApiClient } from '@/lib/api/client'
import { useLocale, useTranslations } from 'next-intl'
import type { Deal } from '@/types/crm'
import DealOverviewTab from './DealOverviewTab'
import DealRoomTab from './DealRoomTab'

interface Note {
  id: string
  star?: string
  date: string
  title?: string
  body?: string
  content?: string
  updatedAt?: string
  author?: string
  [key: string]: any
}

interface Activity {
  activityType: string
  type?: string
  originalType?: string
  title?: string
  theme?: string
  body?: string
  content?: string
  createdAt: string
  date?: string
  employeeName?: string
  interactionId?: string
  noteId?: string
  source?: string
  sourceName?: string
  sourceType?: string
  subject?: string
  direction?: string
  fromEmail?: string
  toEmail?: string
  gmailMessageId?: string
  description?: string
  startTime?: string
  endTime?: string
  location?: string
  metadata?: any
}

interface SelectedMeeting {
  id: string
  data: {
    title?: string
    description?: string
    startTime?: string
    endTime?: string
    location?: string
    employeeName?: string
  }
}

interface DealDetailPageProps {
  dealId: string
  initialTab?: string
}

// Hide the legacy 报价 / 交易室 / 买家兴趣 / 访问记录 four-card dashboard.
// The dashboard JSX, share-link copy logic, and view-tracking polling all stay
// behind this flag so they can be revived without rewriting.
const SHOW_LEGACY_ROOM_DASHBOARD = false

interface DraftColumnState {
  subject: string
  body: string
  loading: boolean
  error: string | null
}

const emptyDraftColumn: DraftColumnState = {
  subject: '',
  body: '',
  loading: false,
  error: null,
}

const DealDetailPage: React.FC<DealDetailPageProps> = ({ dealId, initialTab = 'overview' }) => {
  // Get employees and updateDeal from CRM context
  const { employees, loadEmployees, updateDeal, loadDeals } = useCRM()
  const { user } = useAuth()
  const locale = useLocale()
  const t = useTranslations('crm')

  // Loading and error state
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Local deal state for managing updates
  const [localDeal, setLocalDeal] = useState<Deal | null>(null)

  // Tab state
  const [activeTab, setActiveTab] = useState(initialTab)

  // Sync tab state when initialTab prop changes (e.g., from notification navigation)
  useEffect(() => {
    setActiveTab(initialTab)
  }, [initialTab])

  // Load employees on mount (ensures dropdown is populated on direct navigation)
  useEffect(() => {
    loadEmployees()
  }, [loadEmployees])

  // Fetch deal data on mount
  useEffect(() => {
    const fetchDeal = async () => {
      const numericDealId = Number(dealId)
      if (!dealId || isNaN(numericDealId)) {
        setError(t('dealModal.noIdProvided'))
        setIsLoading(false)
        return
      }

      try {
        setIsLoading(true)
        setError(null)
        const dealData = await crmService.getDeal(numericDealId)
        if (dealData) {
          setLocalDeal(dealData)
        } else {
          setError(t('dealModal.notFound'))
        }
      } catch (err) {
        console.error('Error fetching deal:', err)
        setError(t('dealModal.loadFailed'))
      } finally {
        setIsLoading(false)
      }
    }

    fetchDeal()
  }, [dealId])

  // Editable fields state (matching CustomerProfileDisplay pattern)
  const [editingField, setEditingField] = useState<string | null>(null)
  const [editingValue, setEditingValue] = useState('')
  const [isSavingField, setIsSavingField] = useState(false)

  // Modal state for event details
  const [selectedNote, setSelectedNote] = useState<Note | null>(null)
  const [showNoteModal, setShowNoteModal] = useState(false)
  const [selectedMeeting, setSelectedMeeting] = useState<SelectedMeeting | null>(null)
  const [showMeetingModal, setShowMeetingModal] = useState(false)
  const [selectedInteraction, setSelectedInteraction] = useState<Activity | null>(null)
  const [isInteractionModalOpen, setIsInteractionModalOpen] = useState(false)

  // Notes and activities state
  const [notes, setNotes] = useState<Note[]>([])
  const [isDeletingNote, setIsDeletingNote] = useState<string | null>(null)
  const [activityRefreshTrigger, setActivityRefreshTrigger] = useState(0)

  // Deal room state
  const [roomData, setRoomData] = useState<any>(null)
  const [roomAnalytics, setRoomAnalytics] = useState<any>(null)
  const [isLoadingRoom, setIsLoadingRoom] = useState(false)
  const [isCreatingRoom, setIsCreatingRoom] = useState(false)
  const [linkCopied, setLinkCopied] = useState(false)
  const [isTranslating, setIsTranslating] = useState(false)

  // Deal room creation form
  const [roomForm, setRoomForm] = useState({
    fobPrice: '',
    landedPrice: '',
    currency: 'USD',
    moq: '',
    leadTimeDays: '',
    productName: '',
    customMessageZh: '',
    customMessageEn: '',
  })

  // Bilingual quote-confirmation email draft panel state
  const [draftOpen, setDraftOpen] = useState(false)
  const [draftZh, setDraftZh] = useState<DraftColumnState>(emptyDraftColumn)
  const [draftEn, setDraftEn] = useState<DraftColumnState>(emptyDraftColumn)
  const [sendLanguage, setSendLanguage] = useState<'zh' | 'en'>(
    locale?.startsWith('zh') ? 'zh' : 'en'
  )
  const [isSendingDraft, setIsSendingDraft] = useState(false)

  // Load deal notes (extracted from the activities endpoint)
  const loadDealNotes = async () => {
    if (!localDeal?.dealId) return
    try {
      const data = await crmApiClient.get<{ notes: any[] }>(`/deals/${localDeal.dealId}/activities`)
      const transformedNotes: Note[] = (data.notes || []).map((note: any) => ({
        id: String(note.noteId),
        title: note.title,
        body: note.body,
        content: note.title ? `${note.title}: ${note.body}` : note.body,
        date: note.createdAt,
        updatedAt: note.updatedAt,
        author: note.employeeName || t('noteDetail.defaultAuthor'),
        star: note.star,
      }))
      setNotes(transformedNotes)
    } catch (error) {
      console.error('Error loading deal notes:', error)
    }
  }

  useEffect(() => {
    if (localDeal?.dealId) {
      loadDealNotes()
    }
  }, [localDeal?.dealId])

  // Fetch deal room data and sync room_status to localDeal
  const loadDealRoom = useCallback(async () => {
    if (!localDeal?.dealId) return
    setIsLoadingRoom(true)
    try {
      const data = await crmApiClient.get<{ success: boolean; dealRoom: any }>(
        `/deals/${localDeal.dealId}/room`
      )
      setRoomData(data.dealRoom)
      // Sync room_status back to localDeal so the badge updates
      if (data.dealRoom?.roomStatus && data.dealRoom.roomStatus !== localDeal.roomStatus) {
        setLocalDeal((prev) => (prev ? { ...prev, roomStatus: data.dealRoom.roomStatus } : prev))
      }
      // Also fetch analytics if room exists
      try {
        const analytics = await crmApiClient.get<{ success: boolean; analytics: any }>(
          `/deals/${localDeal.dealId}/room/analytics`
        )
        setRoomAnalytics(analytics.analytics)
      } catch {
        // Analytics may not exist yet
      }
    } catch {
      // 404 means no room exists — that's expected
      setRoomData(null)
    } finally {
      setIsLoadingRoom(false)
    }
  }, [localDeal?.dealId, localDeal?.roomStatus])

  // Load room data when deal room tab is active + poll for status changes
  useEffect(() => {
    if (activeTab === 'dealroom' && localDeal?.dealId) {
      loadDealRoom()
      // Poll every 15s to pick up room_status changes (e.g. draft → viewed)
      const interval = setInterval(() => {
        loadDealRoom()
      }, 15000)
      return () => clearInterval(interval)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, localDeal?.dealId, loadDealRoom])

  // Create deal room
  const handleCreateDealRoom = async () => {
    if (!localDeal?.dealId) return
    setIsCreatingRoom(true)

    const fob = parseFloat(roomForm.fobPrice)
    const landed = parseFloat(roomForm.landedPrice)
    const qty = parseInt(roomForm.moq) || undefined

    try {
      // First save pricing fields to the deal (single source of truth)
      const dealUpdate: Record<string, any> = {}
      if (!isNaN(fob)) dealUpdate.fobPrice = fob
      if (!isNaN(landed)) dealUpdate.landedPrice = landed
      if (roomForm.currency) dealUpdate.fobCurrency = roomForm.currency
      if (qty) dealUpdate.moq = qty
      if (roomForm.productName) dealUpdate.productName = roomForm.productName
      if (Object.keys(dealUpdate).length > 0) {
        await crmApiClient.put(`/deals/${localDeal.dealId}`, dealUpdate)
      }

      // Re-fetch the deal to get updated pricing + share token
      const freshDeal = await crmApiClient.get<any>(`/deals/${localDeal.dealId}`)

      // Load the deal room data
      let dealRoom: any = null
      if (freshDeal?.shareToken) {
        try {
          const roomResp = await crmApiClient.get<{ success: boolean; dealRoom: any }>(
            `/deals/${localDeal.dealId}/room`
          )
          dealRoom = roomResp.dealRoom
        } catch {
          // Room data fetch failed — still show deal with updated pricing
        }
      }

      // Update room settings (custom message) via the room API
      if (freshDeal?.shareToken && (roomForm.customMessageZh || roomForm.customMessageEn)) {
        try {
          await crmApiClient.put(`/deals/${localDeal.dealId}/room`, {
            roomSettings: {
              customMessageZh: roomForm.customMessageZh,
              customMessageEn: roomForm.customMessageEn,
            },
          })
        } catch {
          // Non-critical — room still works without custom message
        }
      }

      if (dealRoom) setRoomData(dealRoom)
      const updatedDeal = {
        ...localDeal,
        ...freshDeal,
        shareToken: dealRoom?.shareToken || freshDeal?.shareToken,
        roomStatus: freshDeal?.roomStatus || 'draft',
      }
      setLocalDeal(updatedDeal)
      if (updateDeal) {
        await updateDeal(String(updatedDeal.dealId), updatedDeal)
      }
      loadDeals(true)
      toast(t('dealRoom.created'))
      // Swap the form for the bilingual quote-confirmation email draft.
      openBilingualDraft()
    } catch (err: any) {
      const message = err?.message || t('dealRoom.createFailed')
      toast.error(t('toasts.error'), { description: message })
    } finally {
      setIsCreatingRoom(false)
    }
  }

  // Generate one column of the bilingual quote-confirmation draft.
  // Errors are scoped to the column so the other column stays usable.
  const generateDraft = async (language: 'zh' | 'en') => {
    const customerId = localDeal?.clientId
    const setColumn = language === 'zh' ? setDraftZh : setDraftEn
    const promptKey =
      language === 'zh' ? 'dealRoom.quoteEmailPromptZh' : 'dealRoom.quoteEmailPromptEn'
    if (!customerId) {
      setColumn({ ...emptyDraftColumn, error: t('dealRoom.draftFailed') })
      return
    }
    setColumn((prev) => ({ ...prev, loading: true, error: null }))
    try {
      const data = await crmApiClient.post<{
        emailData?: { subject?: string; body?: string }
        classification?: any
      }>('/generate-email', {
        customerId,
        customPrompt: t(promptKey),
        templateId: null,
        language,
      })
      setColumn({
        subject: data.emailData?.subject || '',
        body: data.emailData?.body || '',
        loading: false,
        error: null,
      })
    } catch (err: any) {
      setColumn((prev) => ({
        ...prev,
        loading: false,
        error: err?.message || t('dealRoom.draftFailed'),
      }))
    }
  }

  const openBilingualDraft = () => {
    setDraftOpen(true)
    setDraftZh({ ...emptyDraftColumn, loading: true })
    setDraftEn({ ...emptyDraftColumn, loading: true })
    void generateDraft('zh')
    void generateDraft('en')
  }

  const handleCancelDraft = () => {
    setDraftOpen(false)
  }

  const handleSendDraft = async () => {
    if (!localDeal?.clientId || !localDeal?.clientEmail || !localDeal?.dealId) {
      toast.error(t('dealRoom.draftSendFailed'))
      return
    }
    const column = sendLanguage === 'zh' ? draftZh : draftEn
    if (!column.subject.trim() || !column.body.trim()) return
    setIsSendingDraft(true)
    try {
      const result = await crmService.sendEmailWithReply(
        Number(localDeal.clientId),
        localDeal.clientEmail,
        column.subject,
        column.body,
        undefined,
        String(localDeal.dealId)
      )
      if (!result.success) {
        throw new Error(result.error || t('dealRoom.draftSendFailed'))
      }
      toast(t('dealRoom.draftSent'))
      setDraftOpen(false)
      setActivityRefreshTrigger((prev) => prev + 1)
    } catch (err: any) {
      toast.error(t('dealRoom.draftSendFailed'), { description: err?.message })
    } finally {
      setIsSendingDraft(false)
    }
  }

  const handleCopyDraftColumn = async (language: 'zh' | 'en') => {
    const column = language === 'zh' ? draftZh : draftEn
    const text = column.subject ? `${column.subject}\n\n${column.body}` : column.body
    if (!text) return
    try {
      await navigator.clipboard.writeText(text)
      toast(t('dealRoom.draftCopied'))
    } catch {
      // Clipboard write can fail in non-secure contexts; silent is fine.
    }
  }

  // Copy deal room link
  const handleCopyLink = (shareToken: string) => {
    const url = `${window.location.origin}/deal/${shareToken}`
    navigator.clipboard.writeText(url).then(() => {
      setLinkCopied(true)
      toast(t('dealRoom.linkCopied'))
      setTimeout(() => setLinkCopied(false), 2000)
    })
  }

  // Get room status badge variant
  const getRoomStatusVariant = (
    status: string
  ): 'neutral' | 'info' | 'progress' | 'warning' | 'success' | 'danger' => {
    switch (status) {
      case 'draft':
        return 'neutral'
      case 'sent':
        return 'info'
      case 'viewed':
        return 'progress'
      case 'quote_requested':
        return 'warning'
      case 'closed-won':
        return 'success'
      case 'closed-lost':
        return 'danger'
      default:
        return 'neutral'
    }
  }

  // Format room status label
  const formatRoomStatus = (status: string): string => {
    switch (status) {
      case 'draft':
        return t('dealStages.draft')
      case 'sent':
        return t('dealStages.sent')
      case 'viewed':
        return t('dealStages.viewed')
      case 'quote_requested':
        return t('dealStages.quoteRequested')
      case 'closed-won':
        return t('dealStages.closedWon')
      case 'closed-lost':
        return t('dealStages.closedLost')
      default:
        return status
    }
  }

  const formatCurrency = (value?: number | null) => {
    if (!value && value !== 0) return '-'
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value)
  }

  const formatDate = (dateString?: string | null) => {
    if (!dateString) return '-'
    return new Date(dateString).toLocaleDateString()
  }

  // Get current user's employee ID
  const getCurrentUserEmployeeId = (): number | undefined => {
    if (!user?.email || !employees || employees.length === 0) return undefined
    const currentEmployee = employees.find((emp: any) => emp.email === user.email)
    return currentEmployee?.employeeId
  }

  // Event click handler
  const handleEventClick = (activity: Activity) => {
    // Normalize the activity object to match the format expected by InteractionDetailsModal
    const normalizedEvent: Activity = {
      type: activity.activityType,
      originalType: activity.activityType,
      title:
        activity.title ||
        activity.theme ||
        `${activity.activityType === 'note' ? t('interactions.note') : activity.activityType === 'call' ? t('interactions.call') : activity.activityType === 'email' ? t('interactions.email') : t('interactions.meeting')}`,
      description: activity.body || activity.content || '',
      date: activity.createdAt,
      employeeName: activity.employeeName || t('interactionDetail.unknown'),
      metadata: {
        interactionId: activity.interactionId,
        noteId: activity.noteId,
        theme: activity.theme,
        source: activity.source,
        sourceName: activity.sourceName,
        sourceType: activity.sourceType,
        subject: activity.subject,
        direction: activity.direction,
        fromEmail: activity.fromEmail,
        toEmail: activity.toEmail,
        gmailMessageId: activity.gmailMessageId,
      },
      ...activity,
    }

    if (activity.activityType === 'note') {
      // Handle note click - open NoteDetailsModal
      const noteData = notes.find((n) => String(n.id) === String(activity.noteId))
      if (noteData) {
        setSelectedNote(noteData)
        setShowNoteModal(true)
      } else {
        console.error('Note not found:', activity.noteId)
      }
    } else if (activity.activityType === 'meeting' || activity.activityType === 'meet') {
      // Handle meeting click
      const interactionId = activity.interactionId
      if (!interactionId) {
        console.error('No interaction ID found for meeting activity:', activity)
        return
      }

      const meetingData = {
        title: activity.title,
        description: activity.description,
        startTime: activity.startTime,
        endTime: activity.endTime,
        location: activity.location,
        employeeName: activity.employeeName,
      }

      setSelectedMeeting({
        id: interactionId,
        data: meetingData,
      })
      setShowMeetingModal(true)
    } else {
      // For call and email events, use interaction details modal with normalized data
      handleInteractionClick(normalizedEvent)
    }
  }

  const handleInteractionClick = (activity: Activity) => {
    setSelectedInteraction(activity)
    setIsInteractionModalOpen(true)
  }

  const handleNoteModalClose = () => {
    setShowNoteModal(false)
    setSelectedNote(null)
  }

  const handleMeetingModalClose = () => {
    setShowMeetingModal(false)
    setSelectedMeeting(null)
  }

  const handleMeetingUpdate = async (_updatedMeeting: any) => {
    setActivityRefreshTrigger((prev) => prev + 1)
  }

  const handleMeetingDelete = async () => {
    setShowMeetingModal(false)
    setSelectedMeeting(null)
    // Trigger activity refresh
    setActivityRefreshTrigger((prev) => prev + 1)
  }

  const handleInteractionModalClose = () => {
    setIsInteractionModalOpen(false)
    setSelectedInteraction(null)
  }

  const handleDeleteNote = async (noteId: string) => {
    if (!noteId || !localDeal?.dealId) return
    setIsDeletingNote(noteId)
    try {
      await crmApiClient.delete(`/deals/${localDeal.dealId}/notes/${noteId}`)
      setNotes(notes.filter((n) => n.id !== noteId))
      setActivityRefreshTrigger((prev) => prev + 1)
      toast(t('toasts.success'), { description: t('dealModal.noteDeleted') })
    } catch (error) {
      console.error('Error deleting note:', error)
      toast.error(t('dealModal.noteDeleteFailed'))
    } finally {
      setIsDeletingNote(null)
    }
  }

  const handleToggleNoteStar = async (noteId: string, currentStar?: string) => {
    if (!localDeal?.dealId) return
    try {
      const newStar = currentStar === 'important' ? undefined : 'important'
      await crmApiClient.put(`/deals/${localDeal.dealId}/notes/${noteId}`, {
        star: newStar || null,
      })
      // Update note in state
      setNotes(notes.map((n) => (n.id === noteId ? { ...n, star: newStar } : n)))
      toast(t('toasts.success'), { description: newStar === 'important' ? t('dealModal.noteStarred') : t('dealModal.noteUnstarred') })
    } catch (error) {
      console.error('Error toggling note star:', error)
      toast.error(t('dealModal.noteStarFailed'))
    }
  }

  const handleNoteUpdate = async (updatedNote: any) => {
    // Refresh both the activity panel and the local notes state
    setActivityRefreshTrigger((prev) => prev + 1)
    await loadDealNotes()
    // Update selectedNote with new data so modal shows updated content immediately
    if (updatedNote && selectedNote) {
      setSelectedNote({
        ...selectedNote,
        id: String(updatedNote.noteId || updatedNote.id || selectedNote.id),
        title: updatedNote.title || '',
        body: updatedNote.body || updatedNote.content || '',
        content: updatedNote.body || updatedNote.content || '',
        date: updatedNote.createdAt || selectedNote.date,
        updatedAt: updatedNote.updatedAt,
        author: selectedNote.author,
        star: updatedNote.star,
      })
    }
  }

  const handleCallEventDelete = async (_interactionId?: string) => {
    // Trigger activity refresh after delete
    setActivityRefreshTrigger((prev) => prev + 1)
  }

  // Inline field editing handlers (similar to CustomerProfileDisplay)
  const handleFieldClick = (fieldName: string, currentValue?: any) => {
    setEditingField(fieldName)
    setEditingValue(currentValue || '')
  }

  const handleFieldCancel = () => {
    setEditingField(null)
    setEditingValue('')
  }

  const handleFieldSave = async (fieldName: string) => {
    if (!localDeal?.dealId || !updateDeal) {
      console.error('[Deal Edit] No deal ID found, cannot save')
      return
    }

    // Check if value actually changed
    let currentValue = (localDeal as Record<string, any>)[fieldName]
    let newValue = editingValue

    // Normalize values for comparison
    if (fieldName === 'employeeId') {
      currentValue = currentValue || ''
      newValue = newValue || ''

      // If values are the same, just cancel editing without saving
      if (String(currentValue) === String(newValue)) {
        handleFieldCancel()
        return
      }
    }

    setIsSavingField(true)

    try {
      // Prepare update data based on field type
      const updateData: Record<string, any> = {}

      if (fieldName === 'valueUsd' || fieldName === 'fobPrice') {
        updateData[fieldName] = parseFloat(editingValue) || 0
      } else if (fieldName === 'employeeId') {
        // Convert empty string to null, otherwise parse as integer
        updateData[fieldName] = editingValue === '' ? null : parseInt(editingValue)
      } else {
        updateData[fieldName] = editingValue
      }

      const updatedDeal = await crmApiClient.put(`/deals/${localDeal.dealId}`, updateData)

      // Update local state with the response from backend
      setLocalDeal(updatedDeal)

      // Update the deal in CRM context to sync with dashboard
      await updateDeal(updatedDeal.dealId, updatedDeal)

      // Clear editing state
      setEditingField(null)
      setEditingValue('')
      toast(t('toasts.success'), { description: t('dealModal.fieldSaved') })
    } catch (error) {
      console.error('[Deal Edit] Error updating deal:', error)
      toast.error(t('toasts.error'), {
        description: t('dealModal.updateFailed') + ': ' + (error as Error).message,
      })
    } finally {
      setIsSavingField(false)
    }
  }

  // Render editable text field
  const renderEditableField = (fieldName: string, value?: any, placeholder = '', type = 'text') => {
    const isEditing = editingField === fieldName

    if (isEditing) {
      return (
        <div>
          <div className="relative">
            <input
              type={type}
              value={editingValue}
              onChange={(e) => setEditingValue(e.target.value)}
              onBlur={() => {
                if (!isSavingField) {
                  handleFieldSave(fieldName)
                }
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  handleFieldSave(fieldName)
                } else if (e.key === 'Escape') {
                  handleFieldCancel()
                }
              }}
              className="w-full rounded border border-rule bg-bone px-2 py-1 pr-8 text-sm focus:ring-2 focus:border-accent focus:outline-none"
              autoFocus
              disabled={isSavingField}
              step={type === 'number' ? '0.01' : undefined}
            />
            {isSavingField && (
              <div className="absolute top-1/2 right-2 -translate-y-1/2 transform">
                <RefreshCw className="h-4 w-4 animate-spin text-deep" />
              </div>
            )}
          </div>
          <div className="mt-1 text-xs text-mute">{t('dealModal.saveHint')}</div>
        </div>
      )
    }

    return (
      <div
        onClick={() => handleFieldClick(fieldName, value)}
        className="cursor-pointer rounded border border-transparent px-2 py-1 transition-colors hover:border-rule hover:bg-cream"
        title={t('dealModal.clickToEdit')}
      >
        <p className="text-ink">
          <span className={value ? '' : 'text-mute italic'}>{value || placeholder}</span>
        </p>
      </div>
    )
  }

  // Render editable textarea field
  const renderEditableTextarea = (fieldName: string, value?: any, placeholder = '') => {
    const isEditing = editingField === fieldName

    if (isEditing) {
      return (
        <div>
          <div className="relative">
            <textarea
              value={editingValue}
              onChange={(e) => setEditingValue(e.target.value)}
              onBlur={() => {
                if (!isSavingField) {
                  handleFieldSave(fieldName)
                }
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && e.ctrlKey) {
                  handleFieldSave(fieldName)
                } else if (e.key === 'Escape') {
                  handleFieldCancel()
                }
              }}
              className="w-full resize-none rounded border border-rule bg-bone px-2 py-1 text-sm focus:ring-2 focus:border-accent focus:outline-none"
              rows={4}
              autoFocus
              disabled={isSavingField}
            />
            {isSavingField && (
              <div className="absolute top-2 right-2">
                <RefreshCw className="h-4 w-4 animate-spin text-deep" />
              </div>
            )}
          </div>
          <div className="mt-1 text-xs text-mute">{t('dealModal.saveHintTextarea')}</div>
        </div>
      )
    }

    return (
      <div
        onClick={() => handleFieldClick(fieldName, value)}
        className="cursor-pointer rounded border border-transparent px-2 py-1 transition-colors hover:border-rule hover:bg-cream"
        title={t('dealModal.clickToEdit')}
      >
        <p className="whitespace-pre-wrap text-ink">
          <span className={value ? '' : 'text-mute italic'}>{value || placeholder}</span>
        </p>
      </div>
    )
  }

  // Render editable employee dropdown
  const renderEditableEmployeeDropdown = (
    fieldName: string,
    employeeId?: number | null,
    employeeName?: string
  ) => {
    const isEditing = editingField === fieldName

    if (isEditing) {
      return (
        <div>
          <div className="relative">
            <select
              value={editingValue}
              onChange={(e) => {
                setEditingValue(e.target.value)
              }}
              onBlur={() => {
                // Save on blur (like EditableDealsTable pattern)
                if (!isSavingField) {
                  handleFieldSave(fieldName)
                }
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  handleFieldSave(fieldName)
                } else if (e.key === 'Escape') {
                  handleFieldCancel()
                }
              }}
              className="w-full rounded border border-rule bg-bone px-2 py-1 pr-8 text-sm focus:ring-2 focus:border-accent focus:outline-none"
              autoFocus
              disabled={isSavingField}
            >
              <option value="">{t('dealModal.unassigned')}</option>
              {employees?.map((emp: any) => (
                <option key={emp.employeeId || emp.id} value={emp.employeeId || emp.id}>
                  {emp.name}
                </option>
              ))}
            </select>
            {isSavingField && (
              <div className="absolute top-1/2 right-2 -translate-y-1/2 transform">
                <RefreshCw className="h-4 w-4 animate-spin text-deep" />
              </div>
            )}
          </div>
          <div className="mt-1 text-xs text-mute">{t('dealModal.saveHintSelect')}</div>
        </div>
      )
    }

    return (
      <div
        onClick={() => handleFieldClick(fieldName, employeeId || '')}
        className="cursor-pointer rounded border border-transparent px-2 py-1 transition-colors hover:border-rule hover:bg-cream"
        title={t('dealModal.clickToEdit')}
      >
        <p className="text-ink">
          <span className={employeeName ? '' : 'text-mute italic'}>
            {employeeName || t('dealModal.unassigned')}
          </span>
        </p>
      </div>
    )
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="flex h-full min-h-[400px] items-center justify-center">
        <PageLoader label={t('dealModal.loading')} />
      </div>
    )
  }

  // Error state
  if (error || !localDeal) {
    return (
      <div className="flex h-full min-h-[400px] items-center justify-center">
        <div className="text-center">
          <AlertCircle className="mx-auto mb-3 h-8 w-8 text-threat" />
          <p className="font-medium text-ink">{error || t('dealModal.notFound')}</p>
        </div>
      </div>
    )
  }

  return (
    <Fragment>
      <div className="flex h-full flex-col">
        {/* Header */}
        <div className="flex-shrink-0 px-6 pt-5">
          <h2 className="title-page">
            {localDeal.dealName || t('dealModal.noDealName')}
          </h2>
        </div>

        {/* Tabs */}
        <div className="flex-shrink-0 border-b border-rule px-6">
          <div className="flex gap-4">
            <button
              onClick={() => setActiveTab('overview')}
              className={`flex items-center gap-2 border-b-2 pb-3 text-sm font-medium transition-colors ${
                activeTab === 'overview'
                  ? 'border-deep text-deep'
                  : 'border-transparent text-mute hover:text-ink'
              }`}
            >
              <Home className="h-4 w-4" />
              {t('dealModal.overview')}
            </button>
            <button
              onClick={() => setActiveTab('dealroom')}
              className={`flex items-center gap-2 border-b-2 pb-3 text-sm font-medium transition-colors ${
                activeTab === 'dealroom'
                  ? 'border-deep text-deep'
                  : 'border-transparent text-mute hover:text-ink'
              }`}
            >
              <DoorOpen className="h-4 w-4" />
              {t('dealRoom.tab')}
            </button>
          </div>
        </div>

        {/* Content Area - Scrollable */}
        <div className="flex-1 overflow-y-auto bg-paper p-5">
          {activeTab === 'overview' && (
            <DealOverviewTab
              localDeal={localDeal}
              setLocalDeal={setLocalDeal}
              updateDeal={updateDeal}
              editingField={editingField}
              handleFieldClick={handleFieldClick}
              renderEditableField={renderEditableField}
              renderEditableTextarea={renderEditableTextarea}
              renderEditableEmployeeDropdown={renderEditableEmployeeDropdown}
              formatCurrency={formatCurrency}
              formatDate={formatDate}
              activityRefreshTrigger={activityRefreshTrigger}
              notes={notes}
              isDeletingNote={isDeletingNote}
              handleEventClick={handleEventClick}
              handleDeleteNote={handleDeleteNote}
              handleCallEventDelete={handleCallEventDelete}
            />
          )}


          {activeTab === 'dealroom' && (
            <DealRoomTab
              localDeal={localDeal}
              setLocalDeal={setLocalDeal}
              isLoadingRoom={isLoadingRoom}
              isCreatingRoom={isCreatingRoom}
              roomData={roomData}
              roomAnalytics={roomAnalytics}
              loadDealRoom={loadDealRoom}
              handleCreateDealRoom={handleCreateDealRoom}
              handleCopyLink={handleCopyLink}
              linkCopied={linkCopied}
              getRoomStatusVariant={getRoomStatusVariant}
              formatRoomStatus={formatRoomStatus}
              editingField={editingField}
              setEditingField={setEditingField}
              isSavingField={isSavingField}
              setIsSavingField={setIsSavingField}
              roomForm={roomForm}
              setRoomForm={setRoomForm}
              isTranslating={isTranslating}
              setIsTranslating={setIsTranslating}
              draftOpen={draftOpen}
              draftZh={draftZh}
              draftEn={draftEn}
              setDraftZh={setDraftZh}
              setDraftEn={setDraftEn}
              sendLanguage={sendLanguage}
              setSendLanguage={setSendLanguage}
              isSendingDraft={isSendingDraft}
              generateDraft={generateDraft}
              openBilingualDraft={openBilingualDraft}
              handleCancelDraft={handleCancelDraft}
              handleSendDraft={handleSendDraft}
              handleCopyDraftColumn={handleCopyDraftColumn}
            />
          )}
        </div>
      </div>

      {/* Note Details Modal */}
      {selectedNote && (
        <NoteDetailsModal
          note={selectedNote}
          customer={localDeal as any} // Pass deal as customer for API compatibility
          isOpen={showNoteModal}
          onClose={handleNoteModalClose}
          onDelete={handleDeleteNote}
          onUpdate={handleNoteUpdate}
          onToggleStar={handleToggleNoteStar}
          isDeletingNote={isDeletingNote || undefined}
        />
      )}

      {/* Meeting Details Modal */}
      <CRMMeetingDetailsModal
        isOpen={showMeetingModal}
        onClose={handleMeetingModalClose}
        meetingId={selectedMeeting?.id}
        meeting={selectedMeeting?.data as any}
        onUpdate={handleMeetingUpdate}
        onDelete={handleMeetingDelete}
      />

      {/* Interaction Details Modal (for calls and emails) */}
      <InteractionDetailsModal
        event={selectedInteraction as any}
        deal={localDeal}
        isOpen={isInteractionModalOpen}
        onClose={handleInteractionModalClose}
        notes={notes}
        customerInteractions={[]}
        onDelete={handleCallEventDelete}
        onUpdate={handleNoteUpdate}
      />
    </Fragment>
  )
}

export default DealDetailPage
