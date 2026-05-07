'use client'

import React, { useState, useEffect, useCallback, useRef } from 'react'
import { useTranslations } from 'next-intl'
import {
  AlertCircle,
  DollarSign,
  Home,
  Loader2,
  Mail,
  MessageSquare,
  Check,
  X,
} from 'lucide-react'
import { PageLoader } from '@/components/ui/page-loader'
import { useConfirmationToast } from '@/hooks/useConfirmationToast'
import { toast } from 'sonner'
import { useCRM } from '@/contexts/CRMContext'
import { useAuth } from '@/hooks/useAuth'
import { crmApiClient } from '@/lib/api/client'
import CustomerEmailComposer from '../email/CustomerEmailComposer'
import { CustomerFeedbackPanel } from '../feedback/CustomerFeedbackPanel'
import type { Customer, Deal, Interaction } from '@/types/crm'
import { isNoteStarred } from '../utils/activity-helpers'
import CustomerOverviewTab from './CustomerOverviewTab'
import CustomerDealsTab from './CustomerDealsTab'
import CustomerManagementDialogs from './CustomerManagementDialogs'

interface Contact {
  id: string
  name: string
  email: string
  phone?: string
  title?: string
  notes?: string
  isPrimary?: boolean
}

function mapPersonnelToContact(p: any): Contact {
  return {
    id: p.personnelId || p.id,
    name: p.fullName || p.name || `${p.firstName || ''} ${p.lastName || ''}`.trim(),
    email: p.email || '',
    phone: p.phone || '',
    title: p.position || p.title || '',
    isPrimary: p.isPrimary ?? p.is_primary ?? false,
    notes: p.notes || '',
  }
}

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
  type?: string
}

type CustomerInteraction = Interaction

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
    parsedMeetingData?: any
    [key: string]: any
  }
}

interface CustomerDetailPageProps {
  customerId: string
  initialTab?: string
}

const CustomerDetailPage: React.FC<CustomerDetailPageProps> = ({
  customerId,
  initialTab = 'overview',
}) => {
  const { user } = useAuth()
  const { employees, loadEmployees, cachedSummaries, loadCachedSummaries, refreshCustomers } =
    useCRM()
  const { confirm, toastProps } = useConfirmationToast()
  const t = useTranslations('crm')

  // Loading and error state
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Local customer state for instant UI updates
  const [localCustomer, setLocalCustomer] = useState<Customer | null>(null)

  // Callback for when customer is updated
  const onCustomerUpdated = (updatedCustomer: Customer) => {
    setLocalCustomer(updatedCustomer)
  }

  // Fetch customer data on mount
  useEffect(() => {
    const fetchCustomer = async () => {
      if (!customerId) {
        setError(t('customerModal.noIdProvided'))
        setIsLoading(false)
        return
      }

      try {
        setIsLoading(true)
        setError(null)
        const customerData = await crmApiClient.get<Customer>(`/customers/${customerId}`)
        if (customerData) {
          setLocalCustomer(customerData)
        } else {
          setError(t('customerModal.notFound'))
        }
      } catch (err) {
        console.error('Error fetching customer:', err)
        setError(t('customerModal.loadFailed'))
      } finally {
        setIsLoading(false)
      }
    }

    fetchCustomer()
  }, [customerId])

  // Tab state
  const [modalActiveTab, setModalActiveTab] = useState(initialTab)

  // Sync tab state when initialTab prop changes (e.g., from notification navigation)
  useEffect(() => {
    setModalActiveTab(initialTab)
  }, [initialTab])

  // Panel expansion state
  const [expandedPanel, setExpandedPanel] = useState<string | null>(null)

  // Timeline state
  const [customerInteractions, setCustomerInteractions] = useState<CustomerInteraction[]>([])
  const [loadingInteractions, setLoadingInteractions] = useState(false)
  const [timelineFilter, setTimelineFilter] = useState('all')
  const [timelineSearch, setTimelineSearch] = useState('')
  const [isTimelineExpanded, setIsTimelineExpanded] = useState(false)

  // Notes state
  const [notes, setNotes] = useState<Note[]>([])
  const [isLoadingNotes, setIsLoadingNotes] = useState(false)
  const [isRefreshingNotes, setIsRefreshingNotes] = useState(false)
  const [isDeletingNote, setIsDeletingNote] = useState<string | null>(null)

  // Summary state
  const [isGeneratingSummary, setIsGeneratingSummary] = useState(false)
  const [summaryError, setSummaryError] = useState('')
  const summaryPeriod = 30

  // Editable fields state
  const [editingField, setEditingField] = useState<string | null>(null)
  const [editingValue, setEditingValue] = useState('')
  const [isSavingField, setIsSavingField] = useState(false)

  // Deals state
  const [deals, setDeals] = useState<Deal[]>([])
  const [isLoadingDeals, setIsLoadingDeals] = useState(false)
  const [dealsError, setDealsError] = useState('')

  // Contacts state
  const [showContactsModal, setShowContactsModal] = useState(false)
  const [contacts, setContacts] = useState<Contact[]>([])
  const [showContactForm, setShowContactForm] = useState(false)
  const [editingContact, setEditingContact] = useState<Contact | null>(null)
  const [contactFormData, setContactFormData] = useState({
    name: '',
    email: '',
    phone: '',
    title: '',
    notes: '',
  })
  const [isSavingContact, setIsSavingContact] = useState(false)

  // Employee filter state
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<number | null>(null)
  const [customerEmployees, setCustomerEmployees] = useState<
    Array<{ employeeId: number; name: string; email: string; role: string; department: string }>
  >([])

  // Employees modal state
  const [showEmployeesModal, setShowEmployeesModal] = useState(false)
  const [isSavingEmployee, setIsSavingEmployee] = useState(false)
  const [selectedNewEmployeeId, setSelectedNewEmployeeId] = useState<string>('')

  // Interaction details modal state
  const [selectedInteraction, setSelectedInteraction] = useState<TimelineEvent | null>(null)
  const [isInteractionModalOpen, setIsInteractionModalOpen] = useState(false)

  // Note details modal state
  const [selectedNote, setSelectedNote] = useState<Note | null>(null)
  const [showNoteModal, setShowNoteModal] = useState(false)

  // Meeting details modal state
  const [selectedMeeting, setSelectedMeeting] = useState<{ id: string; data: any } | null>(null)
  const [showMeetingModal, setShowMeetingModal] = useState(false)

  // Get current cached summary for the customer
  const getCurrentCachedSummary = useCallback(() => {
    if (!localCustomer?.id) return null
    return cachedSummaries[localCustomer.id] || null
  }, [localCustomer?.id, cachedSummaries])

  // Get current user's employee ID
  const getCurrentUserEmployeeId = useCallback((): number | undefined => {
    if (!user?.email || !employees || employees.length === 0) return undefined
    const currentEmployee = employees.find((emp) => emp.email === user.email)
    return currentEmployee?.employeeId
  }, [user?.email, employees])

  // Load employees on mount
  useEffect(() => {
    loadEmployees()
  }, [loadEmployees])

  // Load contacts from customer data
  useEffect(() => {
    const personnelAsContacts = (localCustomer?.personnel || []).map(mapPersonnelToContact)
    if (personnelAsContacts.length > 0) {
      setContacts(personnelAsContacts)
    } else if (localCustomer?.contacts) {
      setContacts(localCustomer.contacts)
    }
  }, [localCustomer])

  // Fetch customer employees
  const fetchCustomerEmployees = async () => {
    if (!localCustomer?.id) return
    try {
      const emps = await crmApiClient.get<
        Array<{ employeeId: number; name: string; email: string; role: string; department: string }>
      >(`/customers/${localCustomer.id}/employees`)
      setCustomerEmployees(emps || [])
    } catch (err) {
      console.error('Error fetching customer employees:', err)
      setCustomerEmployees([])
    }
  }

  // Load customer employees when customer changes
  useEffect(() => {
    if (localCustomer?.id) {
      fetchCustomerEmployees()
    }
  }, [localCustomer?.id])

  // Load interactions and notes on mount (uses customerId prop directly to avoid waiting for customer fetch)
  useEffect(() => {
    if (!customerId) return
    setSummaryError('')

    const loadInitialData = async () => {
      setLoadingInteractions(true)
      setIsLoadingNotes(true)
      try {
        const [interactions, notesData] = await Promise.all([
          crmApiClient.get(`/customers/${customerId}/interactions`),
          crmApiClient.get(`/customers/${customerId}/notes`),
        ])
        setCustomerInteractions(interactions)
        const transformedNotes: Note[] = notesData.map((note: any) => ({
          id: note.noteId,
          content: note.title ? `${note.title}: ${note.body}` : note.body,
          date: new Date(note.createdAt).toISOString(),
          author: t('noteDetail.defaultAuthor'),
          type: 'user',
          title: note.title,
          body: note.body,
          star: note.star,
          updatedAt: new Date(note.updatedAt).toISOString(),
          isStarred: isNoteStarred(note.star),
          interactionId: note.interactionId,
        }))
        setNotes(transformedNotes)
      } catch (err) {
        console.error('Error loading customer data:', err)
      } finally {
        setLoadingInteractions(false)
        setIsLoadingNotes(false)
      }
    }

    loadInitialData()
  }, [customerId])

  // Fetch deals when deals tab is selected
  useEffect(() => {
    if (localCustomer?.id && modalActiveTab === 'deals') {
      fetchDeals()
    }
  }, [localCustomer?.id, modalActiveTab])

  // Fetch customer interactions
  const fetchCustomerInteractions = async () => {
    if (!localCustomer?.id) return

    setLoadingInteractions(true)
    try {
      const params: Record<string, any> = {}
      if (selectedEmployeeId !== null) {
        params.employeeId = selectedEmployeeId
      }
      const interactions = await crmApiClient.get(
        `/customers/${localCustomer.id}/interactions`,
        params
      )
      setCustomerInteractions(interactions)
    } catch (err) {
      console.error('Error fetching interactions:', err)
    } finally {
      setLoadingInteractions(false)
    }
  }

  // Load customer notes
  const loadCustomerNotes = async (forceRefresh = false) => {
    if (!localCustomer?.id) return

    if (forceRefresh) {
      setIsRefreshingNotes(true)
    } else {
      setIsLoadingNotes(true)
    }

    try {
      const params: Record<string, any> = {}
      if (selectedEmployeeId !== null) {
        params.employeeId = selectedEmployeeId
      }
      const notesData = await crmApiClient.get(`/customers/${localCustomer.id}/notes`, params)
      const transformedNotes: Note[] = notesData.map((note: any) => ({
        id: note.noteId,
        content: note.title ? `${note.title}: ${note.body}` : note.body,
        date: new Date(note.createdAt).toISOString(),
        author: note.employeeName || t('noteDetail.defaultAuthor'),
        type: 'user',
        title: note.title,
        body: note.body,
        star: note.star,
        updatedAt: new Date(note.updatedAt).toISOString(),
        isStarred: isNoteStarred(note.star),
        interactionId: note.interactionId,
      }))
      setNotes(transformedNotes)
    } catch (error) {
      console.error('Error loading customer notes:', error)
      setNotes([])
    } finally {
      setIsLoadingNotes(false)
      setIsRefreshingNotes(false)
    }
  }

  // Fetch deals for this customer
  const fetchDeals = async () => {
    if (!localCustomer?.id) return

    setIsLoadingDeals(true)
    setDealsError('')

    try {
      const customerDeals = await crmApiClient.get(`/customers/${localCustomer.id}/deals`)
      setDeals(customerDeals)
    } catch (error) {
      console.error('Error fetching deals:', error)
      setDealsError(t('customerModal.loadDealsFailed'))
    } finally {
      setIsLoadingDeals(false)
    }
  }

  // Handle field editing
  const handleFieldClick = (
    fieldName: string,
    currentValue: string | number | null | undefined
  ) => {
    setEditingField(fieldName)
    setEditingValue(currentValue?.toString() || '')
  }

  const handleFieldCancel = () => {
    setEditingField(null)
    setEditingValue('')
  }

  const handleFieldSave = async (fieldName: string) => {
    if (!localCustomer?.id) return

    setIsSavingField(true)
    try {
      const fieldMapping: Record<string, string> = {
        company: 'company',
        location: 'location',
        assignedEmployee: 'assignedEmployeeId',
      }

      const backendField = fieldMapping[fieldName]
      if (!backendField) {
        console.error('Unknown field:', fieldName)
        return
      }

      let processedValue: string | number | null = editingValue
      if (fieldName === 'assignedEmployee') {
        processedValue = parseInt(editingValue) || null
      }

      const payload = { [backendField]: processedValue }

      const updatedCustomer = await crmApiClient.put(`/customers/${localCustomer.id}`, payload)

      // Update local state for instant UI update
      setLocalCustomer(updatedCustomer)

      // Notify parent
      onCustomerUpdated?.(updatedCustomer)

      setEditingField(null)
      setEditingValue('')

      if (fieldName === 'assignedEmployee') {
        const employeeName =
          (employees as any[])?.find((emp) => emp.employeeId === parseInt(editingValue))?.name ||
          'employee'
        toast(t('toasts.success'), {
          description: t('customerModalToasts.employeeUpdated', { name: employeeName }),
        })
      } else {
        toast(t('toasts.success'), { description: t('customerModalToasts.fieldUpdated') })
      }
    } catch (error) {
      console.error('Error updating field:', error)
      toast.error(t('toasts.error'), {
        description: t('customerModalToasts.fieldUpdateFailed'),
      })
    } finally {
      setIsSavingField(false)
    }
  }

  // Render editable field
  const renderEditableField = (
    fieldName: string,
    displayValue: string | null | undefined,
    placeholder = '',
    isSelect = false,
    options: Array<{ value: string; label: string }> = [],
    actualValue: string | number | null = null
  ) => {
    const isEditing = editingField === fieldName
    const valueForEditing = actualValue !== null ? actualValue : displayValue

    if (isEditing) {
      return (
        <div>
          <div className="relative">
            {isSelect ? (
              <select
                value={editingValue}
                onChange={(e) => setEditingValue(e.target.value)}
                onBlur={() => !isSavingField && handleFieldSave(fieldName)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleFieldSave(fieldName)
                  else if (e.key === 'Escape') handleFieldCancel()
                }}
                className="w-full rounded border border-rule bg-bone px-2 py-1 pr-20 text-sm focus:ring-2 focus:border-accent focus:outline-none"
                autoFocus
                disabled={isSavingField}
              >
                {options.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                value={editingValue}
                onChange={(e) => setEditingValue(e.target.value)}
                onBlur={() => !isSavingField && handleFieldSave(fieldName)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleFieldSave(fieldName)
                  else if (e.key === 'Escape') handleFieldCancel()
                }}
                className="w-full rounded border border-rule bg-bone px-2 py-1 pr-20 text-sm focus:ring-2 focus:border-accent focus:outline-none"
                autoFocus
                disabled={isSavingField}
              />
            )}
            <div className="absolute top-1/2 right-2 flex -translate-y-1/2 transform items-center gap-1">
              {isSavingField ? (
                <Loader2 className="h-4 w-4 animate-spin text-deep" />
              ) : (
                <>
                  <button
                    onMouseDown={(e) => {
                      e.preventDefault()
                      handleFieldSave(fieldName)
                    }}
                    className="rounded p-1 text-accent transition-colors hover:bg-accent-lo hover:text-accent"
                    title={t('customerModal.saveEnter')}
                    disabled={isSavingField}
                  >
                    <Check className="h-4 w-4" />
                  </button>
                  <button
                    onMouseDown={(e) => {
                      e.preventDefault()
                      handleFieldCancel()
                    }}
                    className="rounded p-1 text-mute transition-colors hover:bg-cream hover:text-ink"
                    title={t('customerModal.cancelEsc')}
                    disabled={isSavingField}
                  >
                    <X className="h-4 w-4" />
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )
    }

    return (
      <div
        onClick={() => handleFieldClick(fieldName, valueForEditing)}
        className="cursor-pointer rounded border border-transparent px-2 py-1 transition-colors hover:border-rule hover:bg-cream"
        title={t('customerModal.clickToEdit')}
      >
        <p className="text-ink">
          <span className={displayValue ? '' : 'text-mute italic'}>
            {displayValue || placeholder}
          </span>
        </p>
      </div>
    )
  }

  // Handle note added
  const handleNoteAdded = async () => {
    await loadCustomerNotes(true)
  }

  // Handle interaction added
  const handleInteractionAdded = async () => {
    await fetchCustomerInteractions()
  }

  // Handle employee filter change
  const handleEmployeeFilterChange = (empId: number | null) => {
    setSelectedEmployeeId(empId)
  }

  // Re-fetch interactions and notes when employee filter changes (skip initial mount)
  const isEmployeeFilterInitial = useRef(true)
  useEffect(() => {
    if (isEmployeeFilterInitial.current) {
      isEmployeeFilterInitial.current = false
      return
    }
    if (localCustomer?.id) {
      fetchCustomerInteractions()
      loadCustomerNotes()
    }
  }, [selectedEmployeeId])

  // Delete note
  const handleDeleteNote = async (noteId: string) => {
    if (!noteId) return

    setIsDeletingNote(noteId)
    try {
      await crmApiClient.delete(`/notes/${noteId}`)
      setNotes((prevNotes) => prevNotes.filter((note) => note.id !== noteId))
      toast(t('toasts.success'), { description: t('customerModalToasts.noteDeleted') })
    } catch (error) {
      console.error('Error deleting note:', error)
      toast.error(t('toasts.error'), {
        description: t('customerModalToasts.noteDeleteFailed'),
      })
    } finally {
      setIsDeletingNote(null)
    }
  }

  // Toggle note star
  const handleToggleNoteStar = async (noteId: string, currentStarStatus?: string) => {
    if (!noteId) return

    const newStarStatus = isNoteStarred(currentStarStatus) ? null : 'important'
    const originalNotes = [...notes]

    setNotes((prevNotes) =>
      prevNotes.map((note) =>
        note.id === noteId
          ? {
              ...note,
              star: newStarStatus || undefined,
              isStarred: isNoteStarred(newStarStatus || undefined),
            }
          : note
      )
    )

    try {
      await crmApiClient.put(`/notes/${noteId}`, { star: newStarStatus })
    } catch (error) {
      setNotes(originalNotes)
      toast.error(t('toasts.error'), {
        description: t('customerModalToasts.importanceUpdateFailed'),
      })
    }
  }

  // Generate summary
  const handleGenerateSummary = async () => {
    if (!localCustomer?.id) return

    setIsGeneratingSummary(true)
    setSummaryError('')

    try {
      await crmApiClient.get(`/customers/${localCustomer.id}/interaction-summary`, {
        daysBack: summaryPeriod,
        forceRefresh: true,
      })
      await loadCachedSummaries(true)
    } catch (err) {
      console.error('Error:', err)
      setSummaryError(t('customerModalToasts.summaryGenerateFailed'))
    } finally {
      setIsGeneratingSummary(false)
    }
  }

  // Get timeline events
  const getTimelineEvents = useCallback((): TimelineEvent[] => {
    const events: TimelineEvent[] = []

    // Add interactions from API
    customerInteractions.forEach((interaction) => {
      if (interaction.createdAt && !isNaN(new Date(interaction.createdAt).getTime())) {
        let normalizedType = interaction.type ? interaction.type.toLowerCase().trim() : 'activity'
        const typeMapping: Record<string, string> = {
          meet: 'meeting',
          call: 'call',
          email: 'email',
        }
        const mappedType = typeMapping[normalizedType] || normalizedType

        const typeLabels: Record<string, string> = {
          call: t('interactions.call'),
          meeting: t('interactions.meeting'),
          email: t('interactions.email'),
          note: t('interactions.note'),
        }
        let title =
          interaction.theme ||
          `${typeLabels[mappedType] || mappedType}: ${interaction.employeeName}`
        let description = interaction.content

        if (mappedType === 'email') {
          title = interaction.theme || interaction.subject || t('customerModal.noSubject')
          description = interaction.content || ''
        }

        events.push({
          type: mappedType,
          originalType: mappedType,
          title,
          description,
          date: interaction.createdAt,
          employeeName: interaction.employeeName,
          metadata: {
            interactionId: interaction.id,
            theme: interaction.theme,
            subject: interaction.subject,
            direction: interaction.direction,
            fromEmail: interaction.fromEmail,
            emailId: interaction.emailId,
            threadId: interaction.threadId,
          },
        })
      }
    })

    // Filter events
    let filteredEvents = events.filter(
      (event) => event.date && !isNaN(new Date(event.date).getTime())
    )

    if (timelineFilter !== 'all') {
      filteredEvents = filteredEvents.filter((event) => event.originalType === timelineFilter)
    }

    if (timelineSearch.trim()) {
      const searchLower = timelineSearch.toLowerCase()
      filteredEvents = filteredEvents.filter(
        (event) =>
          event.title.toLowerCase().includes(searchLower) ||
          event.description?.toLowerCase().includes(searchLower) ||
          event.employeeName?.toLowerCase().includes(searchLower)
      )
    }

    return filteredEvents.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
  }, [customerInteractions, timelineFilter, timelineSearch])

  // Timeline toggle handler
  const handleTimelineToggle = () => {
    setIsTimelineExpanded(!isTimelineExpanded)
  }

  // Event click handler
  const handleEventClick = (event: TimelineEvent) => {
    if (event.originalType === 'note') {
      // Handle note click - open NoteDetailsModal
      const noteData = notes.find((n) => n.id === event.metadata?.noteId)
      if (noteData) {
        setSelectedNote(noteData)
        setShowNoteModal(true)
      } else {
        console.error('Note not found:', event.metadata?.noteId)
      }
    } else if (event.originalType === 'meeting') {
      // Get the interaction ID for CRM meeting
      const interactionId = event.metadata?.interactionId || event.metadata?.interactionId

      if (!interactionId) {
        console.error('No interaction ID found for meeting event:', event)
        return
      }

      // Prepare meeting data from parsed content if available
      const parsedData = event.metadata?.parsedMeetingData
      let meetingData = null

      if (parsedData) {
        // Use pre-loaded data for immediate display
        meetingData = {
          interactionId: interactionId,
          customerId: localCustomer?.id,
          title: parsedData.title || event.metadata?.theme || event.title,
          description: parsedData.description,
          startTime: parsedData.startTime,
          endTime: parsedData.endTime,
          attendees: parsedData.attendees || [],
          location: parsedData.location,
          meetingLink: parsedData.meetingLink,
          timezone: parsedData.timezone || 'UTC',
          createdAt: event.date,
          updatedAt: event.metadata?.updatedAt,
        }
      }

      setSelectedMeeting({
        id: interactionId,
        data: meetingData,
      })
      setShowMeetingModal(true)
    } else {
      // For all other events (email, call, etc.), use the interaction details modal
      handleInteractionClick(event)
    }
  }

  // Interaction modal handlers
  const handleInteractionClick = (event: TimelineEvent) => {
    setSelectedInteraction(event)
    setIsInteractionModalOpen(true)
  }

  const handleInteractionModalClose = () => {
    setIsInteractionModalOpen(false)
    setSelectedInteraction(null)
  }

  // Note modal handlers
  const handleNoteModalClose = () => {
    setShowNoteModal(false)
    setSelectedNote(null)
  }

  // Meeting modal handlers
  const handleMeetingModalClose = () => {
    setShowMeetingModal(false)
    setSelectedMeeting(null)
  }

  const handleMeetingUpdate = async () => {
    await fetchCustomerInteractions()
  }

  const handleMeetingDelete = async () => {
    setShowMeetingModal(false)
    setSelectedMeeting(null)
    await fetchCustomerInteractions()
  }

  // Note update handler - refreshes data and updates selected note
  const handleNoteUpdate = async (updatedNote: any) => {
    // Refresh notes from backend
    await loadCustomerNotes(true)
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

  // Interaction update handler - refreshes data and updates selected interaction
  const handleInteractionUpdate = async (updatedData: any) => {
    // Refresh interactions from backend
    await fetchCustomerInteractions()
    // Update selectedInteraction with new data so modal shows updated content immediately
    if (updatedData && selectedInteraction) {
      setSelectedInteraction({
        ...selectedInteraction,
        description: updatedData.content || selectedInteraction.description,
        title: updatedData.theme || selectedInteraction.title,
        metadata: {
          ...selectedInteraction.metadata,
          theme: updatedData.theme || selectedInteraction.metadata?.theme,
          content: updatedData.content || selectedInteraction.metadata?.content,
          updatedAt: updatedData.updatedAt,
        },
      })
    }
  }

  // Contacts modal handlers
  const handleOpenContactsModal = () => {
    setShowContactsModal(true)
  }

  const handleCloseContactsModal = () => {
    setShowContactsModal(false)
    setShowContactForm(false)
    setEditingContact(null)
    setContactFormData({ name: '', email: '', phone: '', title: '', notes: '' })
  }

  const handleAddContactClick = () => {
    setEditingContact(null)
    setContactFormData({ name: '', email: '', phone: '', title: '', notes: '' })
    setShowContactForm(true)
  }

  const handleEditContactClick = (contact: Contact) => {
    setEditingContact(contact)
    setContactFormData({
      name: contact.name || '',
      email: contact.email || '',
      phone: contact.phone || '',
      title: contact.title || '',
      notes: contact.notes || '',
    })
    setShowContactForm(true)
  }

  const handleCancelContactForm = () => {
    setShowContactForm(false)
    setEditingContact(null)
    setContactFormData({ name: '', email: '', phone: '', title: '', notes: '' })
  }

  const handleSaveContact = async () => {
    if (!localCustomer?.id) return

    try {
      setIsSavingContact(true)

      if (!contactFormData.name.trim()) {
        toast.error(t('toasts.error'), {
          description: t('customerModalValidation.contactNameRequired'),
        })
        setIsSavingContact(false)
        return
      }
      if (!contactFormData.email.trim()) {
        toast.error(t('toasts.error'), {
          description: t('customerModalValidation.contactEmailRequired'),
        })
        setIsSavingContact(false)
        return
      }

      const payload = {
        name: contactFormData.name.trim(),
        email: contactFormData.email.trim(),
        phone: contactFormData.phone.trim(),
        title: contactFormData.title.trim(),
        notes: contactFormData.notes.trim(),
        isPrimary: false,
      }

      let result
      if (editingContact) {
        result = await crmApiClient.put(
          `/customers/${localCustomer.id}/contacts/${editingContact.id}`,
          payload
        )
      } else {
        result = await crmApiClient.post(`/customers/${localCustomer.id}/contacts`, payload)
      }

      if (editingContact) {
        setContacts(
          contacts.map((c) =>
            c.id === editingContact.id ? mapPersonnelToContact(result.contact) : c
          )
        )
        toast(t('toasts.success'), { description: t('customerModalToasts.contactUpdated') })
      } else {
        setContacts([...contacts, mapPersonnelToContact(result.contact)])
        toast(t('toasts.success'), { description: t('customerModalToasts.contactAdded') })
      }

      handleCancelContactForm()
    } catch (error) {
      console.error('Error saving contact:', error)
      toast.error(t('toasts.error'), {
        description: t('customerModalToasts.contactSaveFailed'),
      })
    } finally {
      setIsSavingContact(false)
    }
  }

  const handleDeleteContact = async (contact: Contact) => {
    if (!localCustomer?.id) return

    confirm({
      title: t('customerModal.deleteContact'),
      description: t('customerModal.deleteContactDescription'),
      confirmLabel: t('interactions.delete'),
      cancelLabel: t('interactions.cancel'),
      variant: 'destructive',
      itemName: contact.name,
      onConfirm: async () => {
        try {
          await crmApiClient.delete(`/customers/${localCustomer.id}/contacts/${contact.id}`)
          setContacts(contacts.filter((c) => c.id !== contact.id))
          toast(t('toasts.success'), { description: t('customerModalToasts.contactDeleted') })
        } catch (error) {
          console.error('Error deleting contact:', error)
          toast.error(t('toasts.error'), {
            description: t('customerModalToasts.contactDeleteFailed'),
          })
        }
      },
    })
  }

  const handleSetPrimaryContact = async (contact: Contact) => {
    if (!localCustomer?.id) return

    try {
      await crmApiClient.put(
        `/customers/${localCustomer.id}/contacts/${contact.id}/set-primary`,
        {}
      )
      setContacts(contacts.map((c) => ({ ...c, isPrimary: c.id === contact.id })))
      toast(t('toasts.success'), {
        description: t('customerModalToasts.contactSetPrimary', { name: contact.name }),
      })
    } catch (error) {
      console.error('Error setting primary contact:', error)
      toast.error(t('toasts.error'), {
        description: t('customerModalToasts.contactSetPrimaryFailed'),
      })
    }
  }

  // Employee management handlers
  const handleAddEmployee = async () => {
    if (!localCustomer?.id || !selectedNewEmployeeId) return
    setIsSavingEmployee(true)
    try {
      await crmApiClient.post(`/customers/${localCustomer.id}/employees`, {
        employeeId: parseInt(selectedNewEmployeeId),
      })
      await fetchCustomerEmployees()
      setSelectedNewEmployeeId('')
      toast(t('toasts.success'), { description: t('customerModalToasts.employeeAssigned') })
    } catch (error) {
      console.error('Error adding employee:', error)
      toast.error(t('toasts.error'), {
        description: t('customerModalToasts.employeeAssignFailed'),
      })
    } finally {
      setIsSavingEmployee(false)
    }
  }

  const handleRemoveEmployee = async (employee: { employeeId: number; name: string }) => {
    if (!localCustomer?.id) return

    confirm({
      title: t('customerModal.removeEmployee'),
      description: t('customerModal.removeEmployeeDescription'),
      confirmLabel: t('customerModal.remove'),
      cancelLabel: t('interactions.cancel'),
      variant: 'destructive',
      itemName: employee.name,
      onConfirm: async () => {
        try {
          await crmApiClient.delete(
            `/customers/${localCustomer.id}/employees/${employee.employeeId}`
          )
          await fetchCustomerEmployees()
          // Reset filter if the removed employee was the active filter
          if (selectedEmployeeId === employee.employeeId) {
            setSelectedEmployeeId(null)
          }
          toast(t('toasts.success'), { description: t('customerModalToasts.employeeRemoved') })
        } catch (error) {
          console.error('Error removing employee:', error)
          toast.error(t('toasts.error'), {
            description: t('customerModalToasts.employeeRemoveFailed'),
          })
        }
      },
    })
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="flex h-full min-h-[400px] items-center justify-center">
        <PageLoader label={t('customerModal.loading')} />
      </div>
    )
  }

  // Error state
  if (error || !localCustomer) {
    return (
      <div className="flex h-full min-h-[400px] items-center justify-center">
        <div className="text-center">
          <AlertCircle className="mx-auto mb-3 h-8 w-8 text-threat" />
          <p className="font-medium text-ink">{error || t('customerModal.notFound')}</p>
        </div>
      </div>
    )
  }

  const cachedSummary = getCurrentCachedSummary()

  return (
    <>
      <div className="flex h-full flex-col">
        {/* Header */}
        <div className="flex-shrink-0 px-6 pt-5">
          <h2 className="title-page" lang="en" translate="no">
            {localCustomer.company}
          </h2>
        </div>

        {/* Navigation Tabs */}
        <div className="flex-shrink-0 border-b border-rule px-6">
          <div className="flex gap-4">
            <button
              onClick={() => setModalActiveTab('overview')}
              className={`flex items-center gap-2 border-b-2 pb-3 text-sm font-medium transition-colors ${
                modalActiveTab === 'overview'
                  ? 'border-deep text-deep'
                  : 'border-transparent text-mute hover:text-ink'
              }`}
            >
              <Home className="h-4 w-4" />
              {t('customerModal.overview')}
            </button>
            <button
              onClick={() => setModalActiveTab('email')}
              className={`flex items-center gap-2 border-b-2 pb-3 text-sm font-medium transition-colors ${
                modalActiveTab === 'email'
                  ? 'border-deep text-deep'
                  : 'border-transparent text-mute hover:text-ink'
              }`}
            >
              <Mail className="h-4 w-4" />
              {t('customerModal.sendEmail')}
            </button>
            <button
              onClick={() => setModalActiveTab('deals')}
              className={`flex items-center gap-2 border-b-2 pb-3 text-sm font-medium transition-colors ${
                modalActiveTab === 'deals'
                  ? 'border-deep text-deep'
                  : 'border-transparent text-mute hover:text-ink'
              }`}
            >
              <DollarSign className="h-4 w-4" />
              {t('customerModal.deals')}
            </button>
            <button
              onClick={() => setModalActiveTab('feedback')}
              className={`flex items-center gap-2 border-b-2 pb-3 text-sm font-medium transition-colors ${
                modalActiveTab === 'feedback'
                  ? 'border-deep text-deep'
                  : 'border-transparent text-mute hover:text-ink'
              }`}
            >
              <MessageSquare className="h-4 w-4" />
              {t('customerModal.feedback')}
            </button>
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto bg-paper p-5">
          {modalActiveTab === 'overview' && (
            <CustomerOverviewTab
              localCustomer={localCustomer}
              contacts={contacts}
              customerEmployees={customerEmployees}
              renderEditableField={renderEditableField}
              handleOpenContactsModal={handleOpenContactsModal}
              setShowEmployeesModal={setShowEmployeesModal}
              customerInteractions={customerInteractions}
              loadingInteractions={loadingInteractions}
              timelineFilter={timelineFilter}
              setTimelineFilter={setTimelineFilter}
              timelineSearch={timelineSearch}
              setTimelineSearch={setTimelineSearch}
              isTimelineExpanded={isTimelineExpanded}
              handleTimelineToggle={handleTimelineToggle}
              expandedPanel={expandedPanel}
              setExpandedPanel={setExpandedPanel}
              handleEventClick={handleEventClick}
              getTimelineEvents={getTimelineEvents}
              handleNoteAdded={handleNoteAdded}
              handleInteractionAdded={handleInteractionAdded}
              notes={notes}
              isLoadingNotes={isLoadingNotes}
              isRefreshingNotes={isRefreshingNotes}
              handleDeleteNote={handleDeleteNote}
              handleToggleNoteStar={handleToggleNoteStar}
              isDeletingNote={isDeletingNote}
              selectedEmployeeId={selectedEmployeeId}
              handleEmployeeFilterChange={handleEmployeeFilterChange}
              currentUserEmployeeId={getCurrentUserEmployeeId()}
              isGeneratingSummary={isGeneratingSummary}
              handleGenerateSummary={handleGenerateSummary}
              cachedSummary={cachedSummary}
              summaryError={summaryError}
            />
          )}

          {modalActiveTab === 'email' && (
            <div className="h-full">
              <CustomerEmailComposer
                customer={localCustomer}
                onClose={() => setModalActiveTab('overview')}
                onEmailSent={async () => {
                  await new Promise((resolve) => setTimeout(resolve, 300))
                  await fetchCustomerInteractions()
                  // Re-fetch customer to pick up stage auto-progression
                  const updated = await crmApiClient.get<Customer>(`/customers/${customerId}`)
                  if (updated) setLocalCustomer(updated)
                  refreshCustomers()
                  setModalActiveTab('overview')
                }}
                embedded={true}
              />
            </div>
          )}

          {modalActiveTab === 'deals' && (
            <CustomerDealsTab
              localCustomer={localCustomer}
              deals={deals}
              isLoadingDeals={isLoadingDeals}
              dealsError={dealsError}
              fetchDeals={fetchDeals}
            />
          )}

          {modalActiveTab === 'feedback' && (
            <div className="w-full px-6 py-4">
              <CustomerFeedbackPanel
                customerId={parseInt(String(localCustomer.id))}
                currentUserId={getCurrentUserEmployeeId()}
              />
            </div>
          )}
        </div>
      </div>

      <CustomerManagementDialogs
        localCustomer={localCustomer}
        showContactsModal={showContactsModal}
        handleCloseContactsModal={handleCloseContactsModal}
        contacts={contacts}
        showContactForm={showContactForm}
        editingContact={editingContact}
        contactFormData={contactFormData}
        setContactFormData={setContactFormData}
        isSavingContact={isSavingContact}
        handleAddContactClick={handleAddContactClick}
        handleEditContactClick={handleEditContactClick}
        handleCancelContactForm={handleCancelContactForm}
        handleSaveContact={handleSaveContact}
        handleDeleteContact={handleDeleteContact}
        handleSetPrimaryContact={handleSetPrimaryContact}
        showEmployeesModal={showEmployeesModal}
        setShowEmployeesModal={setShowEmployeesModal}
        customerEmployees={customerEmployees}
        employees={employees as any[]}
        selectedNewEmployeeId={selectedNewEmployeeId}
        setSelectedNewEmployeeId={setSelectedNewEmployeeId}
        isSavingEmployee={isSavingEmployee}
        handleAddEmployee={handleAddEmployee}
        handleRemoveEmployee={handleRemoveEmployee}
        selectedInteraction={selectedInteraction}
        isInteractionModalOpen={isInteractionModalOpen}
        handleInteractionModalClose={handleInteractionModalClose}
        customerInteractions={customerInteractions}
        notes={notes}
        handleInteractionUpdate={handleInteractionUpdate}
        selectedNote={selectedNote}
        showNoteModal={showNoteModal}
        handleNoteModalClose={handleNoteModalClose}
        handleDeleteNote={handleDeleteNote}
        handleNoteUpdate={handleNoteUpdate}
        handleToggleNoteStar={handleToggleNoteStar}
        isDeletingNote={isDeletingNote}
        selectedMeeting={selectedMeeting}
        showMeetingModal={showMeetingModal}
        handleMeetingModalClose={handleMeetingModalClose}
        handleMeetingUpdate={handleMeetingUpdate}
        handleMeetingDelete={handleMeetingDelete}
        toastProps={toastProps}
      />
    </>
  )
}

export default CustomerDetailPage
