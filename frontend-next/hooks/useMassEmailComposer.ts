import { useState, useRef } from 'react'
import { useTranslations } from 'next-intl'

interface ApiHandlers {
  generatePersonalized: (params: {
    selectedIds: string[]
    customMessage: string
    templateId?: string | null
    // Factory data (batch-wide)
    products?: { name: string; fobPrice: string; landedPrice: string }[]
    certifications?: string[]
    moq?: string
    leadTime?: string
    [key: string]: any
  }) => Promise<{
    total: number
    requestedTotal?: number
    generated?: number
    failed?: number
    skipped?: number
    processingTimeSeconds?: number
    emails: any[]
    recipientResults?: RecipientResult[]
    recipient_results?: RecipientResult[]
  }>
  sendPersonalized: (params: {
    emails: any[]
    provider: string | null
    modifiedIndices?: number[]
    campaignContext?: {
      customPrompt?: string
      products?: { name: string; fobPrice: string; landedPrice: string }[]
      certifications?: string[]
      moq?: string
      leadTime?: string
      sampleStatus?: string
      [key: string]: any
    }
  }) => Promise<{
    status?: string
    jobId?: string
    sent?: number
    failed?: number
    campaignId?: string
  }>
  preparePersonalizedEmail: (email: any) => any
  scheduleSend?: (params: {
    scheduledAt: string
    selectedIds: string[]
    emails?: any[]
    provider: string | null
    modifiedIndices?: number[]
  }) => Promise<any>
}

interface RecipientResult {
  recipientId?: string
  recipient_id?: string
  status: 'generated' | 'skipped' | 'failed'
  email?: any
  reason?: string
}

interface Recipient {
  id: string
  name?: string
  email: string
  company?: string
  [key: string]: any
}

interface TradeFieldValues {
  products?: { name: string; fobPrice: string; landedPrice: string }[]
  certifications?: string[]
  moq?: string
  leadTime?: string
  sampleStatus?: string
}

interface UseEmailComposerParams {
  selectedIds: Set<string>
  allRecipients?: Recipient[]
  apiHandlers: ApiHandlers
  tradeFields?: TradeFieldValues
}

/**
 * Shared hook for mass email composer logic (CRM & Lead Gen).
 * All emails are AI-generated (personalized mode only).
 */
export const useMassEmailComposer = ({
  selectedIds,
  allRecipients = [],
  apiHandlers,
  tradeFields,
}: UseEmailComposerParams) => {
  const tMass = useTranslations('email.massEmail')

  const recipients = allRecipients.filter((recipient) => selectedIds.has(recipient.id))

  // --- Card selection state ---
  // User template ID — null when a purpose card or custom is selected
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null)

  // Email context textarea
  const [customMessage, setCustomMessage] = useState('')

  // Generation / sending state
  const [isGenerating, setIsGenerating] = useState(false)
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [insertTarget, setInsertTarget] = useState<'subject' | 'body'>('body')

  // AI-generated emails state
  const [personalizedEmails, setPersonalizedEmails] = useState<any[]>([])
  const [recipientResults, setRecipientResults] = useState<RecipientResult[]>([])
  const [activeEmailIndex, setActiveEmailIndex] = useState(0)
  const [editedEmails, setEditedEmails] = useState<Record<number, any>>({})
  const [modifiedEmailIndices, setModifiedEmailIndices] = useState<Set<number>>(new Set())
  const [generationProgress, setGenerationProgress] = useState('')

  // Approval state (mass email approval flow)
  const [approvedEmailIndices, setApprovedEmailIndices] = useState<Set<number>>(new Set())

  // Bilingual translation cache (zh-CN: Chinese back-translation of generated English emails)
  const [translatedEmails, setTranslatedEmails] = useState<
    Record<number, { subject: string; body: string }>
  >({})
  const [isTranslating, setIsTranslating] = useState(false)
  const translationVersionRef = useRef(0)

  const bodyTextareaRef = useRef<HTMLDivElement>(null)

  const canUseAi = recipients.length <= 25

  const selectTemplate = (templateId: string | null) => {
    if (templateId === selectedTemplateId) return
    setSelectedTemplateId(templateId)
    resetGeneratedContent()
  }

  // Translate a single email and cache the result (version check discards stale responses)
  const translateEmail = async (index: number, subject: string, body: string) => {
    if (translatedEmails[index]) return // Already cached
    const version = ++translationVersionRef.current
    try {
      setIsTranslating(true)
      const { translateEmailContent } = await import('@/lib/i18n/translate-email')
      const { subjectZh, bodyZh } = await translateEmailContent(subject, body)
      if (translationVersionRef.current === version) {
        setTranslatedEmails((prev) => ({ ...prev, [index]: { subject: subjectZh, body: bodyZh } }))
      }
    } catch (err) {
      console.warn('Translation failed:', err)
    } finally {
      if (translationVersionRef.current === version) {
        setIsTranslating(false)
      }
    }
  }

  const resetGeneratedContent = () => {
    setPersonalizedEmails([])
    setRecipientResults([])
    setEditedEmails({})
    setModifiedEmailIndices(new Set())
    setApprovedEmailIndices(new Set())
    setTranslatedEmails({})
    translationVersionRef.current++
    setActiveEmailIndex(0)
    setError('')
    setSuccess('')
  }

  // --- Approval actions ---
  const toggleApproveEmail = (index: number) => {
    if (!editedEmails[index]) return
    setApprovedEmailIndices((prev) => {
      const next = new Set(prev)
      if (next.has(index)) {
        next.delete(index)
      } else {
        next.add(index)
      }
      return next
    })
  }

  const approveAll = () => {
    setApprovedEmailIndices(
      new Set(personalizedEmails.map((_, i) => i).filter((i) => !!editedEmails[i]))
    )
  }

  const approvedCount = approvedEmailIndices.size

  const emailRecipientId = (email: any): string | null => {
    const id =
      email?.recipientId ??
      email?.recipient_id ??
      email?.clientId ??
      email?.client_id ??
      email?.customerId ??
      email?.customer_id ??
      email?.leadId ??
      email?.lead_id ??
      email?.recipient?.id
    return id == null ? null : String(id)
  }

  const normalizeRecipientResults = (data: any): RecipientResult[] => {
    const rawResults = data.recipientResults ?? data.recipient_results
    if (Array.isArray(rawResults) && rawResults.length > 0) {
      return rawResults.map((result: any) => ({
        recipientId: String(result.recipientId ?? result.recipient_id ?? emailRecipientId(result.email) ?? ''),
        status: result.status,
        email: result.email,
        reason: result.reason,
      }))
    }

    return (data.emails || []).map((email: any, idx: number) => ({
      recipientId: emailRecipientId(email) ?? recipients[idx]?.id ?? String(idx),
      status: 'generated',
      email,
    }))
  }

  const buildDisplayEmail = (result: RecipientResult) => {
    const recipientId = String(result.recipientId ?? result.recipient_id ?? '')
    if (result.status === 'generated' && result.email) {
      return {
        ...result.email,
        recipientId,
        generationStatus: 'generated',
      }
    }

    const recipient = recipients.find((r) => String(r.id) === recipientId)
    return {
      recipientId,
      generationStatus: result.status,
      generationError: result.reason || result.status,
      recipient,
      // Provide both CRM and lead-shaped fields so shared UI adapters can
      // still display failed/skipped rows without knowing the source surface.
      clientId: recipientId,
      clientName: recipient?.name || recipient?.company || '',
      clientEmail: recipient?.email || '',
      leadId: recipientId,
      leadCompany: recipient?.company || recipient?.name || '',
      toEmail: recipient?.email || '',
      subject: '',
      body: '',
    }
  }

  const buildApprovedEmailPayloads = (action: 'send' | 'schedule') => {
    const sortedApproved = Array.from(approvedEmailIndices).sort((a, b) => a - b)
    if (sortedApproved.length === 0) {
      setError(action === 'send' ? tMass('noApprovedForSending') : tMass('noApprovedForScheduling'))
      return null
    }

    const emailsToSend = []
    for (const index of sortedApproved) {
      const generated = personalizedEmails[index]
      if (generated?.generationError) {
        setError(`Cannot ${action}: recipient ${index + 1} did not generate (${generated.generationError}).`)
        return null
      }

      const edited = editedEmails[index]
      if (!edited) {
        setError(`Cannot ${action}: recipient ${index + 1} has no generated email payload.`)
        return null
      }
      emailsToSend.push(edited)
    }

    return { sortedApproved, emailsToSend }
  }

  // --- Generation ---
  const handleGenerateEmail = async () => {
    try {
      setIsGenerating(true)
      setError('')
      setGenerationProgress(tMass('generationStarting'))

      const data = await apiHandlers.generatePersonalized({
        selectedIds: recipients.map((r) => r.id),
        customMessage,
        templateId: selectedTemplateId,
        ...(tradeFields && {
          products: tradeFields.products?.filter((p) => p.name || p.fobPrice || p.landedPrice)
            .length
            ? tradeFields.products
            : undefined,
          certifications: tradeFields.certifications?.length
            ? tradeFields.certifications
            : undefined,
        }),
      })

      const processingTime = data.processingTimeSeconds
        ? typeof data.processingTimeSeconds === 'number'
          ? data.processingTimeSeconds.toFixed(1)
          : data.processingTimeSeconds
        : '0'

      const normalizedResults = normalizeRecipientResults(data)
      const generatedCount =
        data.generated ?? normalizedResults.filter((result) => result.status === 'generated').length
      const failedOrSkipped = normalizedResults.filter((result) => result.status !== 'generated').length

      setGenerationProgress(
        failedOrSkipped > 0
          ? `Generated ${generatedCount}/${normalizedResults.length || data.total} emails (${failedOrSkipped} need attention) in ${processingTime}s`
          : tMass('generationComplete', { total: data.total, time: processingTime })
      )
      setRecipientResults(normalizedResults)
      const displayEmails = normalizedResults.map(buildDisplayEmail)
      setPersonalizedEmails(displayEmails)

      const edited: Record<number, any> = {}
      normalizedResults.forEach((result, idx) => {
        if (result.status === 'generated' && result.email) {
          edited[idx] = apiHandlers.preparePersonalizedEmail(result.email)
        }
      })
      setEditedEmails(edited)
      setModifiedEmailIndices(new Set())
      setApprovedEmailIndices(new Set())

      setTimeout(() => setGenerationProgress(''), 3000)
    } catch (err: any) {
      setError(err.message || tMass('generateFailed'))
      setGenerationProgress('')
    } finally {
      setIsGenerating(false)
    }
  }

  // --- Sending ---
  const handleSendEmails = async () => {
    // Only send approved emails
    const payloads = buildApprovedEmailPayloads('send')
    if (!payloads) return

    const { sortedApproved, emailsToSend } = payloads

    const hasEmpty = emailsToSend.some(
      (email) => !email.subject?.trim() || !email.body?.trim() || !email.to_email?.trim()
    )

    if (hasEmpty) {
      setError(tMass('approvedMustHaveContent'))
      return
    }

    // Build modified indices relative to the emailsToSend array (not original indices)
    const approvedModifiedIndices = sortedApproved
      .map((origIdx, posIdx) => (modifiedEmailIndices.has(origIdx) ? posIdx : -1))
      .filter((i) => i !== -1)

    // Build campaign context for 5+ recipients (persisted as trade_context on campaign row)
    const campaignContext =
      emailsToSend.length >= 5
        ? {
            customPrompt: customMessage || undefined,
            ...(tradeFields && {
              products: tradeFields.products?.filter((p) => p.name || p.fobPrice || p.landedPrice)
                .length
                ? tradeFields.products
                : undefined,
              certifications: tradeFields.certifications?.length
                ? tradeFields.certifications
                : undefined,
              moq: tradeFields.moq || undefined,
              leadTime: tradeFields.leadTime || undefined,
              sampleStatus: tradeFields.sampleStatus || undefined,
            }),
          }
        : undefined

    try {
      setIsSending(true)
      setError('')

      const authProvider = localStorage.getItem('auth_provider')
      const provider =
        authProvider === 'google' ? 'gmail' : authProvider === 'microsoft' ? 'outlook' : null

      const result = await apiHandlers.sendPersonalized({
        emails: emailsToSend,
        provider,
        modifiedIndices: approvedModifiedIndices,
        campaignContext,
      })

      // Two queued shapes ship today:
      //   CRM (email_mass_router):     { status: 'queued', jobId, ... }
      //   Leadgen (outreach_router):   { jobId, campaignId, totalRecipients, ... } (no status)
      // Either one means "Temporal accepted the workflow"; treat both as queued
      // so leadgen mass-send doesn't render "Sent 0 emails".
      const isQueued = result.status === 'queued' || (!!(result as any).jobId && result.sent === undefined)
      if (isQueued) {
        setSuccess(
          tMass('personalizedQueued', {
            jobId: result.jobId ?? (result as any).jobId ?? '',
            edits: approvedModifiedIndices.length,
          })
        )
      } else {
        setSuccess(
          result.failed && result.failed > 0
            ? tMass('personalizedSentWithFailed', {
                sent: result.sent ?? 0,
                failed: result.failed,
                edits: approvedModifiedIndices.length,
              })
            : tMass('personalizedSent', {
                sent: result.sent ?? 0,
                edits: approvedModifiedIndices.length,
              })
        )
      }

      return result
    } catch (err: any) {
      setError(err.message || tMass('sendPersonalizedFailed'))
      throw err
    } finally {
      setIsSending(false)
    }
  }

  // --- Schedule Send ---
  const [isScheduling, setIsScheduling] = useState(false)

  const handleScheduleSend = async (scheduledAt: string) => {
    if (!apiHandlers.scheduleSend) return

    try {
      setIsScheduling(true)
      setError('')

      const authProvider = localStorage.getItem('auth_provider')
      const provider =
        authProvider === 'google' ? 'gmail' : authProvider === 'microsoft' ? 'outlook' : null

      const payloads = buildApprovedEmailPayloads('schedule')
      if (!payloads) return

      const { sortedApproved, emailsToSend } = payloads
      if (emailsToSend.some((email) => !email.subject?.trim() || !email.body?.trim())) {
        setError(tMass('approvedMustHaveContent'))
        return
      }
      const approvedModifiedIndices = sortedApproved
        .map((origIdx, posIdx) => (modifiedEmailIndices.has(origIdx) ? posIdx : -1))
        .filter((i) => i !== -1)
      await apiHandlers.scheduleSend({
        scheduledAt,
        selectedIds: recipients.map((r) => r.id),
        emails: emailsToSend,
        provider,
        modifiedIndices: approvedModifiedIndices,
      })

      setSuccess(tMass('scheduled'))
    } catch (err: any) {
      setError(err.message || tMass('scheduleFailed'))
    } finally {
      setIsScheduling(false)
    }
  }

  // --- Subject/body editing ---
  const currentSubject = editedEmails[activeEmailIndex]?.subject ?? ''
  const currentBody = editedEmails[activeEmailIndex]?.body ?? ''

  const handleSubjectChange = (newSubject: string) => {
    if (personalizedEmails.length === 0 || !editedEmails[activeEmailIndex]) return
    setEditedEmails((prev) => ({
      ...prev,
      [activeEmailIndex]: { ...prev[activeEmailIndex], subject: newSubject },
    }))
    setModifiedEmailIndices((prev) => new Set([...prev, activeEmailIndex]))
    setTranslatedEmails((prev) => {
      const next = { ...prev }
      delete next[activeEmailIndex]
      return next
    })
  }

  const handleBodyChange = (newBody: string) => {
    if (personalizedEmails.length === 0 || !editedEmails[activeEmailIndex]) return
    setEditedEmails((prev) => ({
      ...prev,
      [activeEmailIndex]: { ...prev[activeEmailIndex], body: newBody },
    }))
    setModifiedEmailIndices((prev) => new Set([...prev, activeEmailIndex]))
    setTranslatedEmails((prev) => {
      const next = { ...prev }
      delete next[activeEmailIndex]
      return next
    })
  }

  const truncateCompanyName = (name: string, maxLength = 12): string => {
    if (!name) return tMass('unknown')
    return name.length <= maxLength ? name : name.substring(0, maxLength) + '...'
  }

  const hasGeneratedContent = personalizedEmails.length > 0

  return {
    // Selection state
    selectedTemplateId,
    selectTemplate,
    customMessage,
    setCustomMessage,

    // Derived
    canUseAi,
    hasGeneratedContent,
    currentSubject,
    currentBody,

    // Generation / sending / scheduling
    isGenerating,
    isSending,
    isScheduling,
    error,
    success,
    generationProgress,
    handleGenerateEmail,
    handleSendEmails,
    onScheduleSend: apiHandlers.scheduleSend ? handleScheduleSend : undefined,

    // Email editing
    insertTarget,
    setInsertTarget,
    personalizedEmails,
    recipientResults,
    activeEmailIndex,
    setActiveEmailIndex,
    handleSubjectChange,
    handleBodyChange,
    truncateCompanyName,

    // Recipients
    recipients,

    // Approval
    approvedEmailIndices,
    approvedCount,
    modifiedEmailIndices,
    toggleApproveEmail,
    approveAll,

    // Bilingual translation
    translatedEmails,
    isTranslating,
    translateEmail,

    // Refs
    bodyTextareaRef,
  }
}
