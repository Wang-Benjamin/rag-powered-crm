import React, { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { SafeHtml } from '@/components/ui/safe-html'
import {
  Calendar,
  Clock,
  User,
  Mail,
  Phone,
  Users,
  MessageSquare,
  Building,
  ArrowRight,
  FileText,
  Star,
  Trash2,
  RefreshCw,
  Edit3,
  Save,
  XCircle,
  Send,
  SendHorizontal,
  MailOpen,
  Download,
  Reply,
  CornerDownRight,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { motion, AnimatePresence } from 'framer-motion'
import { ConfirmationToast } from '@/components/ui/confirmation-toast'
import { useConfirmationToast } from '@/hooks/useConfirmationToast'
import { crmApiClient } from '@/lib/api/client'
import { useLocale, useTranslations } from 'next-intl'
import type { Customer, Deal } from '@/types/crm'
import {
  isNoteStarred,
  getStarDisplayText as getStarDisplayTextHelper,
  getEmailDirectionBadge as getEmailDirectionBadgeHelper,
} from '../utils/activity-helpers'

interface Note {
  id: string
  title?: string
  body?: string
  content?: string
  date: string
  updatedAt?: string
  author?: string
  star?: string
  isStarred?: boolean
  interactionId?: string
}

interface EventMetadata {
  interactionId?: string
  theme?: string
  subject?: string
  direction?: string
  sourceName?: string
  sourceType?: string
  fromEmail?: string
}

interface Event {
  id?: string
  originalType: string
  title: string
  description?: string
  date: string
  employeeName?: string
  metadata?: EventMetadata
}

interface QuotedReply {
  content: string
  sender?: {
    name?: string
    email?: string
  }
  type: string
  subject?: string
  date?: string
}

interface ParsedEmailContent {
  newReply: string
  signature: string
  quotedReplies: QuotedReply[]
}

interface InteractionDetailsModalProps {
  event: Event
  customer?: Customer
  deal?: Deal
  open?: boolean
  isOpen?: boolean
  onOpenChange?: (open: boolean) => void
  onClose?: () => void
  notes?: Note[]
  customerInteractions?: any[]
  onDelete?: (id: string) => void
  onUpdate?: (data: any) => Promise<void>
}

/**
 * InteractionDetailsModal - Enhanced with shadcn Dialog primitive
 *
 * Now uses shadcn's Dialog for better accessibility and consistency.
 * Supports both old (isOpen/onClose) and new (open/onOpenChange) prop names for backward compatibility.
 */
const InteractionDetailsModal: React.FC<InteractionDetailsModalProps> = ({
  event,
  customer,
  deal,
  open,
  isOpen,
  onOpenChange,
  onClose,
  notes = [],
  customerInteractions = [],
  onDelete,
  onUpdate,
}) => {
  const locale = useLocale()
  const t = useTranslations('crm')

  // Determine context (customer or deal)
  const contextId = deal ? deal.dealId : customer?.id
  const contextType = deal ? 'deal' : 'customer'
  const contextName = deal ? deal.dealName : customer?.name

  // Support both new (open) and legacy (isOpen) prop names
  const modalOpen = open !== undefined ? open : (isOpen ?? false)

  // Confirmation toast
  const { confirm, toastProps } = useConfirmationToast()

  // Support both new (onOpenChange) and legacy (onClose) callbacks
  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen && !isSaving && !isEditing) {
      if (onOpenChange) {
        onOpenChange(newOpen)
      } else if (onClose) {
        onClose()
      }
    }
  }

  // Edit state
  const [isEditing, setIsEditing] = useState(false)
  const [editedTheme, setEditedTheme] = useState('')
  const [editedContent, setEditedContent] = useState('')
  const [isSaving, setIsSaving] = useState(false)

  // State for expandable previous messages
  const [expandedMessages, setExpandedMessages] = useState<Record<number, boolean>>({})

  // State for expandable main message
  const [isMainMessageExpanded, setIsMainMessageExpanded] = useState(false)

  // State for expandable previous messages section
  const [isPreviousMessagesExpanded, setIsPreviousMessagesExpanded] = useState(false)

  const MAX_THEME_LENGTH = 50
  const MAX_CONTENT_LENGTH = 5000

  // Check if this is a call event
  const isCallEvent = event?.originalType === 'call'

  // Check if this is an email event
  const isEmailEvent = event?.originalType === 'email'

  // Initialize edit fields when event changes
  useEffect(() => {
    if (event && modalOpen && isCallEvent) {
      setEditedTheme(event.metadata?.theme || event.title || '')
      setEditedContent(event.description || '')
      setIsEditing(false)
    }
  }, [event, modalOpen, isCallEvent])

  // Early return AFTER all hooks
  if (!event) return null

  // Get notes linked to this interaction - try multiple possible ID fields
  const interactionId = event.metadata?.interactionId || event.id

  const linkedNotes = notes.filter((note) => note.interactionId === interactionId)

  // Format date and time
  const formatDateTime = (dateString: string) => {
    if (!dateString) return t('interactionDetail.notApplicable')
    const date = new Date(dateString)
    if (isNaN(date.getTime())) return t('interactionDetail.invalidDate')

    return {
      date: date.toLocaleDateString(locale, {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      }),
      time: date.toLocaleTimeString(locale, {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true,
      }),
    }
  }

  const formatNoteDate = (date: string): string => {
    if (!date) return t('interactionDetail.notApplicable')
    const parsedDate = new Date(date)
    if (isNaN(parsedDate.getTime())) {
      return t('interactionDetail.invalidDate')
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

  // Enhanced email content parser with better thread detection
  const parseEmailContent = (content?: string, subject?: string): ParsedEmailContent => {
    if (!content)
      return {
        newReply: '',
        signature: '',
        quotedReplies: [],
      }

    let cleanedContent = content

    // Common patterns for quoted/original emails with more comprehensive detection
    const quotedPatterns = [
      {
        pattern: /\n\s*On .+?wrote:\s*\n/gi,
        type: 'gmail',
        extractSender: (match: string) => {
          const senderMatch = match.match(/On .+?, (.+?) <(.+?)> wrote:/i)
          return senderMatch ? { name: senderMatch[1], email: senderMatch[2] } : null
        },
      },
      {
        pattern: /\n\s*.+?于\d{4}年\d{1,2}月\d{1,2}日.+?写道[：:]\s*\n/g,
        type: 'gmail-chinese',
        extractSender: (match: string) => {
          const senderMatch = match.match(/\n\s*(.+?)\s*于\d{4}年/)
          return senderMatch ? { name: senderMatch[1].trim(), email: undefined } : null
        },
      },
      {
        pattern: /\n\s*\d{4}年\d{1,2}月\d{1,2}日.+?<(.+?)>.+?:\s*\n/g,
        type: 'gmail-japanese',
        extractSender: (match: string) => {
          const emailMatch = match.match(/<(.+?)>/)
          return emailMatch ? { name: undefined, email: emailMatch[1] } : null
        },
      },
      {
        pattern: /\n\s*\d{4}년\s*\d{1,2}월\s*\d{1,2}일.+?작성[：:]\s*\n/g,
        type: 'gmail-korean',
        extractSender: (match: string) => {
          const emailMatch = match.match(/<(.+?)>/)
          return emailMatch ? { name: undefined, email: emailMatch[1] } : null
        },
      },
      {
        pattern: /\n\s*El\s+.+?escribió:\s*\n/gi,
        type: 'gmail-spanish',
        extractSender: (match: string) => {
          const senderMatch = match.match(/,\s*(.+?)\s*<(.+?)>\s*escribió:/i)
          return senderMatch ? { name: senderMatch[1], email: senderMatch[2] } : null
        },
      },
      {
        pattern: /\n\s*Le\s+.+?a écrit\s*:\s*\n/gi,
        type: 'gmail-french',
        extractSender: (match: string) => {
          const senderMatch = match.match(/,\s*(.+?)\s*<(.+?)>\s*a écrit/i)
          return senderMatch ? { name: senderMatch[1], email: senderMatch[2] } : null
        },
      },
      {
        pattern: /\n\s*Am\s+.+?schrieb:\s*\n/gi,
        type: 'gmail-german',
        extractSender: (match: string) => {
          const senderMatch = match.match(/,\s*(.+?)\s*<(.+?)>\s*schrieb:/i)
          return senderMatch ? { name: senderMatch[1], email: senderMatch[2] } : null
        },
      },
      {
        pattern: /\n\s*From:.+?Sent:.+?To:/gis,
        type: 'outlook',
        extractSender: (match: string) => {
          const senderMatch = match.match(/From:\s*(.+?)\s*<(.+?)>/i)
          return senderMatch ? { name: senderMatch[1], email: senderMatch[2] } : null
        },
      },
      {
        pattern: /\n\s*-+\s*Original Message\s*-+/gi,
        type: 'generic',
        extractSender: () => null,
      },
      {
        pattern: /\n\s*_{5,}/g,
        type: 'separator',
        extractSender: () => null,
      },
    ]

    let newReply = cleanedContent
    let quotedReplies: QuotedReply[] = []

    // Find ALL quoted email patterns (not just the first one)
    let allMatches: Array<{
      index: number
      matchText: string
      type: string
      extractSender: (match: string) => { name?: string; email?: string } | null
    }> = []

    for (const { pattern, type, extractSender } of quotedPatterns) {
      pattern.lastIndex = 0
      let match
      while ((match = pattern.exec(cleanedContent)) !== null) {
        allMatches.push({
          index: match.index,
          matchText: match[0],
          type: type,
          extractSender: extractSender,
        })
      }
    }

    // Sort matches by index to process them in order
    allMatches.sort((a, b) => a.index - b.index)

    if (allMatches.length > 0) {
      // The first match separates the new reply from quoted content
      const firstMatch = allMatches[0]
      newReply = cleanedContent.substring(0, firstMatch.index).trim()

      // Process each quoted section
      for (let i = 0; i < allMatches.length; i++) {
        const currentMatch = allMatches[i]
        const nextMatch = allMatches[i + 1]

        const startIndex = currentMatch.index
        const endIndex = nextMatch ? nextMatch.index : cleanedContent.length

        const quotedContent = cleanedContent.substring(startIndex, endIndex).trim()

        // Extract sender info if possible
        const sender = currentMatch.extractSender(currentMatch.matchText)

        // Clean up quoted content by removing ">" quote markers
        const cleanedQuoted = quotedContent
          .split('\n')
          .map((line) => line.replace(/^\s*>\s?/, ''))
          .join('\n')
          .trim()

        // Only add if there's actual content (not just the header)
        if (cleanedQuoted.length > currentMatch.matchText.length) {
          quotedReplies.push({
            content: cleanedQuoted,
            sender: sender || undefined,
            type: currentMatch.type,
          })
        }
      }
    }

    // Try to separate signature from new reply
    let signature = ''
    const signaturePatterns = [
      /\n\s*--\s*\n/,
      /\n\s*Best regards,?\s*\n/i,
      /\n\s*Sincerely,?\s*\n/i,
      /\n\s*Thanks,?\s*\n/i,
      /\n\s*Regards,?\s*\n/i,
      /\n\s*Cheers,?\s*\n/i,
      /\n\s*Thank you,?\s*\n/i,
    ]

    for (const pattern of signaturePatterns) {
      const match = newReply.match(pattern)
      if (match && match.index !== undefined) {
        const splitIndex = match.index
        const potentialSignature = newReply.substring(splitIndex).trim()
        // Only treat as signature if it's reasonably short (< 300 chars)
        if (potentialSignature.length < 300) {
          signature = potentialSignature
          newReply = newReply.substring(0, splitIndex).trim()
          break
        }
      }
    }

    return { newReply, signature, quotedReplies }
  }

  const dateTime = formatDateTime(event.date)

  // Handle save edit for call events
  const handleSaveEdit = async () => {
    if (!editedContent.trim()) {
      toast.error(t('interactionValidation.contentEmpty'))
      return
    }

    if (editedContent.length > MAX_CONTENT_LENGTH) {
      toast.error(t('interactionValidation.contentMax', { max: MAX_CONTENT_LENGTH }))
      return
    }

    if (editedTheme.length > MAX_THEME_LENGTH) {
      toast.error(t('interactionValidation.themeMax', { max: MAX_THEME_LENGTH }))
      return
    }

    setIsSaving(true)

    try {
      // Build API endpoint based on context
      const endpoint =
        contextType === 'deal'
          ? `/deals/${contextId}/call-summaries/${interactionId}`
          : `/customers/${contextId}/call-summaries/${interactionId}`

      const updatedCallSummary = await crmApiClient.put(endpoint, {
        content: editedContent.trim(),
        theme: editedTheme.trim() || null,
      })

      if (onUpdate) {
        await onUpdate(updatedCallSummary)
      }
      setIsEditing(false)
      toast.success(t('interactionToasts.callSummaryUpdated'))
    } catch (err: any) {
      console.error('Error updating call summary:', err)
      toast.error(t('interactionToasts.callSummaryUpdateFailed'))
    } finally {
      setIsSaving(false)
    }
  }

  // Handle cancel edit
  const handleCancelEdit = () => {
    setEditedTheme(event.metadata?.theme || event.title || '')
    setEditedContent(event.description || '')
    setIsEditing(false)
  }

  // Handle delete for call events
  const handleDelete = () => {
    confirm({
      title: t('interactionToasts.deleteConfirmTitle'),
      description: t('interactionToasts.deleteConfirmDescription'),
      confirmLabel: t('interactionToasts.deleteConfirmLabel'),
      variant: 'destructive',
      onConfirm: async () => {
        try {
          // Build API endpoint based on context
          const endpoint =
            contextType === 'deal'
              ? `/deals/${contextId}/call-summaries/${interactionId}`
              : `/customers/${contextId}/call-summaries/${interactionId}`

          await crmApiClient.delete(endpoint)

          if (onDelete && interactionId) {
            await onDelete(interactionId)
          }
          if (onClose) {
            onClose()
          }
          toast.success(t('interactionToasts.callSummaryDeleted'))
        } catch (err: any) {
          console.error('Error deleting call summary:', err)
          toast.error(t('interactionToasts.callSummaryDeleteFailed'))
        }
      },
    })
  }

  // Get type-specific icon and styling (using kit utilities)
  const getTypeConfig = (type: string) => {
    switch (type) {
      case 'email':
        return {
          icon: Mail,
          bgColor: 'bg-cream',
          textColor: 'text-ink',
          borderColor: 'border-rule',
        }
      case 'call':
        return {
          icon: Phone,
          bgColor: 'bg-cream',
          textColor: 'text-ink',
          borderColor: 'border-rule',
        }
      case 'meeting':
        return {
          icon: Users,
          bgColor: 'bg-cream',
          textColor: 'text-ink',
          borderColor: 'border-rule',
        }
      default:
        return {
          icon: MessageSquare,
          bgColor: 'bg-cream',
          textColor: 'text-ink',
          borderColor: 'border-rule',
        }
    }
  }

  const getEmailDirectionBadge = (direction?: string) => getEmailDirectionBadgeHelper(direction, t)

  const typeConfig = getTypeConfig(event.originalType)
  const TypeIcon = typeConfig.icon

  return (
    <>
      <Dialog open={modalOpen} onOpenChange={handleOpenChange}>
        <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
          <DialogHeader>
            {isEmailEvent ? (
              /* Email: clean header — subject + direction + compact metadata */
              <div>
                <div className="flex items-start justify-between gap-3">
                  <DialogTitle className="title-page">{event.title}</DialogTitle>
                  {event.metadata?.direction && (() => {
                    const directionBadge = getEmailDirectionBadge(event.metadata.direction)
                    return directionBadge ? <Badge variant={directionBadge.variant} className="mt-1 flex-shrink-0">{directionBadge.label}</Badge> : null
                  })()}
                </div>
                <div className="mt-2 flex items-center gap-1.5 text-sm text-mute">
                  {event.metadata?.direction === 'sent' ? (
                    <SendHorizontal className="h-3.5 w-3.5" />
                  ) : (
                    <MailOpen className="h-3.5 w-3.5" />
                  )}
                  <span className="font-medium text-mute">{event.employeeName}</span>
                  <ArrowRight className="h-3 w-3" />
                  <span className="font-medium text-mute">{customer?.company}</span>
                  <span className="mx-1 text-rule">·</span>
                  <span className="text-mute">
                    {typeof dateTime === 'object' ? `${dateTime.date} ${dateTime.time}` : dateTime}
                  </span>
                </div>
              </div>
            ) : (
              /* Non-email: compact header — title + metadata line */
              <div>
                <DialogTitle className="title-page">{event.title}</DialogTitle>
                <div className="mt-2 flex items-center gap-1.5 text-sm text-mute">
                  <TypeIcon className="h-3.5 w-3.5" />
                  <span className="font-medium text-mute">{event.employeeName}</span>
                  <ArrowRight className="h-3 w-3" />
                  <span className="font-medium text-mute">{customer?.company}</span>
                  <span className="mx-1 text-rule">·</span>
                  <span className="text-mute">
                    {typeof dateTime === 'object' ? `${dateTime.date} ${dateTime.time}` : dateTime}
                  </span>
                </div>
              </div>
            )}
          </DialogHeader>

          {/* Content */}
          <div className="space-y-6">
            {/* Content section */}
            <div className="space-y-3">
              {isCallEvent && !isEditing && (
                <div className="flex justify-end">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setIsEditing(true)}
                    className="flex items-center gap-2"
                  >
                    <Edit3 className="h-4 w-4" />
                    {t('interactionDetail.editButton')}
                  </Button>
                </div>
              )}
              <div className="border-t border-rule" />

              {/* Email-specific structured display with enhanced UI */}
              {isEmailEvent ? (
                <div className="space-y-4">
                  {(() => {
                    const emailSubject =
                      event.metadata?.subject || event.title || t('interactionDetail.noSubject')
                    const { newReply: rawReply, signature, quotedReplies } = parseEmailContent(
                      event.description,
                      emailSubject
                    )
                    // Strip HTML signature block so plain-text \n\n paragraphs are preserved via whitespace-pre-wrap
                    const newReply = (rawReply || '')
                      .replace(/<div\s+style="margin-top:\s*20px[^"]*"[^>]*>[\s\S]*$/gi, '')
                      .replace(/<[^>]+>/g, '')
                      .trim()

                    return (
                      <AnimatePresence mode="wait">
                        <motion.div
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -10 }}
                          transition={{ duration: 0.2 }}
                          className="space-y-4"
                        >
                          {/* Email Body — content-first, no inner card */}
                          {newReply && (
                            <motion.div
                              initial={{ opacity: 0, scale: 0.98 }}
                              animate={{ opacity: 1, scale: 1 }}
                              transition={{ delay: 0.1 }}
                            >
                              <div className="border-t border-rule pt-4">
                                <div
                                  className={`prose prose-sm max-w-none ${
                                    !isMainMessageExpanded && newReply.length > 500
                                      ? 'line-clamp-6'
                                      : ''
                                  }`}
                                >
                                  {newReply.includes('<') && newReply.includes('>') ? (
                                    <SafeHtml
                                      html={newReply}
                                      className="text-sm leading-relaxed text-ink"
                                    />
                                  ) : (
                                    <p className="text-sm leading-relaxed whitespace-pre-wrap text-ink">
                                      {newReply}
                                    </p>
                                  )}
                                </div>

                                {/* Expand/Collapse Button for Main Message */}
                                {newReply.length > 500 && (
                                  <button
                                    onClick={() => setIsMainMessageExpanded(!isMainMessageExpanded)}
                                    className="mt-3 flex items-center gap-1 text-xs font-medium text-ink transition-colors hover:text-ink"
                                  >
                                    {isMainMessageExpanded ? (
                                      <>
                                        <ChevronUp className="h-3 w-3" />
                                        {t('interactionDetail.showLess')}
                                      </>
                                    ) : (
                                      <>
                                        <ChevronDown className="h-3 w-3" />
                                        {t('interactionDetail.showMore')}
                                      </>
                                    )}
                                  </button>
                                )}
                              </div>
                            </motion.div>
                          )}

                          {/* Email Signature */}
                          {signature && (
                            <motion.div
                              initial={{ opacity: 0 }}
                              animate={{ opacity: 1 }}
                              transition={{ delay: 0.15 }}
                              className="rounded-lg border border-rule bg-paper p-4"
                            >
                              <div className="mb-2 flex items-center gap-2">
                                <User className="h-4 w-4 text-mute" />
                                <span className="text-xs font-semibold tracking-wide text-mute uppercase">
                                  {t('interactionDetail.signature')}
                                </span>
                              </div>
                              {signature.includes('<') && signature.includes('>') ? (
                                <SafeHtml
                                  html={signature}
                                  className="text-xs leading-relaxed text-mute italic"
                                />
                              ) : (
                                <p className="text-xs leading-relaxed whitespace-pre-wrap text-mute italic">
                                  {signature}
                                </p>
                              )}
                            </motion.div>
                          )}

                          {/* Quoted/Previous Messages in Thread - Expandable Section */}
                          {quotedReplies.length > 0 && (
                            <motion.div
                              initial={{ opacity: 0 }}
                              animate={{ opacity: 1 }}
                              transition={{ delay: 0.2 }}
                              className="mt-6 border-t-2 border-rule pt-4"
                            >
                              {/* Expandable Header */}
                              <button
                                onClick={() =>
                                  setIsPreviousMessagesExpanded(!isPreviousMessagesExpanded)
                                }
                                className="mb-3 -ml-2 flex w-full items-center gap-2 rounded p-2 transition-colors hover:bg-cream"
                              >
                                {isPreviousMessagesExpanded ? (
                                  <ChevronUp className="h-4 w-4 text-mute" />
                                ) : (
                                  <ChevronDown className="h-4 w-4 text-mute" />
                                )}
                                <CornerDownRight className="h-4 w-4 text-mute" />
                                <span className="text-xs font-medium tracking-wide text-mute uppercase">
                                  {t('interactionDetail.previousMessages', {
                                    count: quotedReplies.length,
                                  })}
                                </span>
                              </button>

                              {/* Expandable Content */}
                              {isPreviousMessagesExpanded && (
                                <motion.div
                                  initial={{ opacity: 0, height: 0 }}
                                  animate={{ opacity: 1, height: 'auto' }}
                                  exit={{ opacity: 0, height: 0 }}
                                  transition={{ duration: 0.2 }}
                                  className="space-y-4"
                                >
                                  {quotedReplies.map((quoted, index) => {
                                    const isExpanded = expandedMessages[index]

                                    return (
                                      <motion.div
                                        key={index}
                                        initial={{ opacity: 0, x: -10 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        transition={{ delay: 0.05 + index * 0.05 }}
                                        className="overflow-hidden rounded-lg border border-fog bg-bone shadow-sm"
                                      >
                                        {/* Subject with Sender Info and Timestamp - Same Design as Main Email */}
                                        <div className="border-b border-rule px-5 pt-4 pb-3">
                                          <div className="flex items-center gap-2">
                                            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-cream">
                                              <Mail className="h-3.5 w-3.5 text-mute" />
                                            </div>
                                            <div className="flex-1">
                                              <div className="text-sm font-semibold text-ink">
                                                {quoted.subject || emailSubject}
                                              </div>
                                              <div className="text-xs text-mute">
                                                {quoted.sender?.email ||
                                                  t('interactionDetail.unknown')}
                                                {quoted.date && (
                                                  <>
                                                    {' • '}
                                                    {quoted.date}
                                                  </>
                                                )}
                                              </div>
                                            </div>
                                          </div>
                                        </div>

                                        {/* Email Content */}
                                        <div className="px-5 py-4">
                                          <div
                                            className={`prose prose-sm max-w-none ${
                                              !isExpanded && quoted.content.length > 500
                                                ? 'line-clamp-6'
                                                : ''
                                            }`}
                                          >
                                            <p className="text-sm leading-relaxed whitespace-pre-wrap text-ink">
                                              {quoted.content}
                                            </p>
                                          </div>

                                          {/* Expand/Collapse Button for Individual Message */}
                                          {quoted.content.length > 500 && (
                                            <button
                                              onClick={() =>
                                                setExpandedMessages((prev) => ({
                                                  ...prev,
                                                  [index]: !prev[index],
                                                }))
                                              }
                                              className="mt-3 flex items-center gap-1 text-xs font-medium text-ink transition-colors hover:text-ink"
                                            >
                                              {isExpanded ? (
                                                <>
                                                  <ChevronUp className="h-3 w-3" />
                                                  {t('interactionDetail.showLess')}
                                                </>
                                              ) : (
                                                <>
                                                  <ChevronDown className="h-3 w-3" />
                                                  {t('interactionDetail.showMore')}
                                                </>
                                              )}
                                            </button>
                                          )}
                                        </div>
                                      </motion.div>
                                    )
                                  })}
                                </motion.div>
                              )}
                            </motion.div>
                          )}
                        </motion.div>
                      </AnimatePresence>
                    )
                  })()}
                </div>
              ) : isCallEvent && isEditing ? (
                <div className="space-y-4">
                  {/* Theme Input */}
                  <div>
                    <label className="mb-2 block text-sm font-medium text-ink">
                      {t('interactionDetail.themeLabel')}{' '}
                      <span className="text-mute">{t('interactionDetail.themeOptional')}</span>
                    </label>
                    <div className="relative">
                      <input
                        type="text"
                        value={editedTheme}
                        onChange={(e) => setEditedTheme(e.target.value)}
                        placeholder={t('interactionDetail.themePlaceholder')}
                        className="w-full rounded-lg border border-rule px-3 py-2 pr-20 text-sm focus:ring-2 focus:ring-accent focus:outline-none"
                        maxLength={MAX_THEME_LENGTH}
                        disabled={isSaving}
                      />
                      <div className="absolute right-3 bottom-2 text-xs text-mute">
                        {editedTheme.length}/{MAX_THEME_LENGTH}
                      </div>
                    </div>
                  </div>

                  {/* Content Textarea */}
                  <div>
                    <label className="mb-2 block text-sm font-medium text-ink">
                      {t('interactionDetail.summaryLabel')} <span className="text-threat">*</span>
                    </label>
                    <div className="relative">
                      <textarea
                        value={editedContent}
                        onChange={(e) => setEditedContent(e.target.value)}
                        placeholder={t('interactionDetail.summaryPlaceholder')}
                        className="h-48 w-full resize-none rounded-lg border border-rule px-3 py-2 pr-20 text-sm focus:ring-2 focus:ring-accent focus:outline-none"
                        maxLength={MAX_CONTENT_LENGTH}
                        disabled={isSaving}
                      />
                      <div className="absolute right-3 bottom-3 text-xs text-mute">
                        {editedContent.length}/{MAX_CONTENT_LENGTH}
                      </div>
                    </div>
                  </div>

                  {/* Edit Actions */}
                  <div className="flex gap-2">
                    <Button
                      onClick={handleSaveEdit}
                      disabled={!editedContent.trim() || isSaving}
                      className="flex items-center gap-2 bg-deep text-bone hover:bg-deep"
                    >
                      {isSaving ? (
                        <>
                          <RefreshCw className="h-4 w-4 animate-spin" />
                          {t('interactionDetail.saving')}
                        </>
                      ) : (
                        <>
                          <Save className="h-4 w-4" />
                          {t('interactionDetail.saveButton')}
                        </>
                      )}
                    </Button>
                    <Button
                      variant="outline"
                      onClick={handleCancelEdit}
                      disabled={isSaving}
                      className="flex items-center gap-2"
                    >
                      <XCircle className="h-4 w-4" />
                      {t('interactionDetail.cancelButton')}
                    </Button>
                  </div>
                </div>
              ) : (
                /* Default content display for calls and other interactions */
                <div className="rounded-lg bg-paper p-4">
                  <p className="text-sm leading-relaxed whitespace-pre-wrap text-mute">
                    {event.description || t('interactionDetail.noContent')}
                  </p>
                </div>
              )}
            </div>

            {/* Linked Notes Section */}
            {linkedNotes.length > 0 && (
              <div className="space-y-3">
                <h3 className="title-block flex items-center gap-2">
                  <FileText className="h-5 w-5 text-mute" />
                  {t('interactionDetail.notesCount', { count: linkedNotes.length })}
                </h3>
                <div className="space-y-3">
                  {linkedNotes.map((note) => (
                    <div
                      key={note.id}
                      className={`rounded-lg border p-4 ${
                        note.isStarred
                          ? 'border-gold/25 bg-gold-lo'
                          : 'border-rule bg-paper'
                      }`}
                    >
                      <div className="flex gap-3">
                        {/* Avatar */}
                        <div className="flex-shrink-0">
                          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-deep">
                            <User className="h-3 w-3 text-bone" />
                          </div>
                        </div>

                        {/* Note Content */}
                        <div className="min-w-0 flex-1">
                          {/* Header */}
                          <div className="mb-1 flex items-center gap-2">
                            {note.title && (
                              <h5 className="truncate title-block">
                                {note.title}
                              </h5>
                            )}
                            {note.isStarred && (
                              <div className="flex flex-shrink-0 items-center gap-1 rounded-full bg-gold-lo px-1.5 py-0.5 text-xs text-gold">
                                <Star className="h-2.5 w-2.5 fill-gold text-gold" />
                                {getStarDisplayText(note.star)}
                              </div>
                            )}
                          </div>

                          {/* Body */}
                          <div className="mb-2 text-sm leading-relaxed text-mute">
                            {note.body || note.content}
                          </div>

                          {/* Date */}
                          <div className="text-xs text-mute">
                            {formatNoteDate(note.date)}
                            {note.updatedAt &&
                              new Date(note.updatedAt).getTime() !==
                                new Date(note.date).getTime() && (
                                <span>
                                  {' '}
                                  • {t('interactionDetail.edited')} {formatNoteDate(note.updatedAt)}
                                </span>
                              )}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => handleOpenChange(false)} disabled={isSaving}>
              {t('interactionDetail.closeButton')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Confirmation Toast */}
      <ConfirmationToast {...toastProps} />
    </>
  )
}

export default InteractionDetailsModal
