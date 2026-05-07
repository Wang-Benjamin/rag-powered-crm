'use client'

import { useState, useEffect, useCallback } from 'react'
import { useTranslations } from 'next-intl'
import { Clock, X, Loader2, ChevronDown, ChevronUp, Mail, Users, FileText } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { toast } from 'sonner'
import { crmApiClient } from '@/lib/api/client'
import leadsApiService from '@/lib/api/leads'
import type { ScheduledMassEmail } from '@/types/email/scheduled'

interface ScheduledEmailsModalProps {
  open: boolean
  onClose: () => void
  service: 'crm' | 'leads'
}

const statusVariant = (status: string) => {
  switch (status) {
    case 'scheduled':
      return 'outline'
    case 'in_progress':
      return 'default'
    case 'completed':
      return 'secondary'
    case 'cancelled':
      return 'secondary'
    case 'failed':
      return 'destructive'
    default:
      return 'outline'
  }
}

const STATUS_KEY_MAP: Record<string, string> = {
  scheduled: 'scheduled',
  in_progress: 'inProgress',
  completed: 'completed',
  cancelled: 'cancelled',
  failed: 'failed',
}

const ScheduledEmailsModal: React.FC<ScheduledEmailsModalProps> = ({ open, onClose, service }) => {
  const t = useTranslations('email')
  const tc = useTranslations('common')
  const [items, setItems] = useState<ScheduledMassEmail[]>([])
  const [loading, setLoading] = useState(true)
  const [cancellingId, setCancellingId] = useState<number | null>(null)
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const fetchScheduledEmails = useCallback(async () => {
    try {
      let data: any
      if (service === 'crm') {
        data = await crmApiClient.get('/scheduled-mass-emails')
      } else {
        data = await leadsApiService.getScheduledMassEmails()
      }
      setItems(data.scheduledEmails || [])
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [service])

  useEffect(() => {
    if (!open) return
    setLoading(true)
    setExpandedId(null)
    fetchScheduledEmails()

    const interval = setInterval(fetchScheduledEmails, 30000)
    return () => clearInterval(interval)
  }, [open, fetchScheduledEmails])

  const handleCancel = async (scheduleId: number) => {
    setCancellingId(scheduleId)
    try {
      if (service === 'crm') {
        await crmApiClient.delete(`/scheduled-mass-emails/${scheduleId}`)
      } else {
        await leadsApiService.cancelScheduledMassEmail(scheduleId)
      }
      toast(t('scheduledEmails.cancelledToast'))
      fetchScheduledEmails()
    } catch {
      toast.error(t('scheduledEmails.cancelFailedToast'))
    } finally {
      setCancellingId(null)
    }
  }

  const formatDateTime = (iso: string) => {
    try {
      return new Date(iso).toLocaleString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    } catch {
      return iso
    }
  }

  const getRecipientsFromPayload = (item: ScheduledMassEmail): string[] => {
    const p = item.payload
    if (!p) return []

    if (item.emailType === 'personalized' && p.emails) {
      return p.emails
        .map((e: any) => e.toEmail || e.clientEmail || e.leadEmail || 'Unknown')
        .filter(Boolean)
    }

    if (p.recipients) {
      return p.recipients.map((r: any) => r.email || r.clientEmail || 'Unknown')
    }
    if (p.leads) {
      return p.leads.map((l: any) => l.email || l.leadEmail || 'Unknown')
    }

    return []
  }

  const getSubjectFromPayload = (item: ScheduledMassEmail): string => {
    const p = item.payload
    if (!p) return '—'

    if (item.emailType === 'template') {
      return p.templateSubject || p.subjectTemplate || p.subject || '—'
    }

    if (p.emails && p.emails.length > 0) {
      return p.emails[0].subject || '—'
    }
    return '—'
  }

  const getBodyPreview = (item: ScheduledMassEmail): string => {
    const p = item.payload
    if (!p) return ''

    if (item.emailType === 'template') {
      return p.templateBody || p.bodyTemplate || p.body || ''
    }

    if (p.emails && p.emails.length > 0) {
      return p.emails[0].body || ''
    }
    return ''
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="title-page flex items-center gap-2">
            <Clock className="h-5 w-5" />
            {t('scheduledEmails.title')}
          </DialogTitle>
        </DialogHeader>

        <div className="max-h-[60vh] overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-zinc-400" />
            </div>
          ) : items.length === 0 ? (
            <div className="py-12 text-center">
              <Clock className="mx-auto mb-3 h-10 w-10 text-zinc-300" />
              <p className="text-sm text-zinc-500">{t('scheduledEmails.noScheduledYet')}</p>
              <p className="mt-1 text-xs text-zinc-400">{t('scheduledEmails.scheduleSendHint')}</p>
            </div>
          ) : (
            <div className="space-y-2">
              {items.map((item) => {
                const isExpanded = expandedId === item.scheduleId
                const recipients = getRecipientsFromPayload(item)
                const subject = getSubjectFromPayload(item)
                const bodyPreview = getBodyPreview(item)

                return (
                  <div
                    key={item.scheduleId}
                    className="rounded-lg border border-zinc-200 transition-colors"
                  >
                    {/* Header row */}
                    <div
                      className="flex cursor-pointer items-center justify-between p-3 hover:bg-zinc-50"
                      onClick={() => setExpandedId(isExpanded ? null : item.scheduleId)}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="mb-1 flex items-center gap-2">
                          <Badge
                            variant={statusVariant(item.status)}
                            className="text-xs capitalize"
                          >
                            {t(
                              `scheduledEmails.status.${STATUS_KEY_MAP[item.status] || item.status}` as any
                            )}
                          </Badge>
                          <span className="text-xs text-zinc-500 capitalize">{item.emailType}</span>
                        </div>
                        <div className="truncate text-sm font-medium text-zinc-900">
                          {item.templateName || subject !== '—'
                            ? subject
                            : t('scheduledEmails.untitled')}
                        </div>
                        <div className="mt-1 flex items-center gap-3 text-xs text-zinc-500">
                          <span>
                            {t('scheduledEmails.recipientCount', { count: item.totalRecipients })}
                          </span>
                          <span>
                            {t('scheduledEmails.scheduledFor')}: {formatDateTime(item.scheduledAt)}
                          </span>
                          {(item.status === 'completed' || item.status === 'in_progress') && (
                            <span>
                              {t('scheduledEmails.sent', { count: item.sent })}
                              {item.failed > 0
                                ? `, ${t('scheduledEmails.failed', { count: item.failed })}`
                                : ''}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="ml-3 flex items-center gap-2">
                        {item.status === 'scheduled' && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation()
                              handleCancel(item.scheduleId)
                            }}
                            disabled={cancellingId === item.scheduleId}
                            className="border-red-200 text-red-600 hover:bg-red-50 hover:text-red-700"
                          >
                            {cancellingId === item.scheduleId ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              <X className="mr-1 h-3 w-3" />
                            )}
                            {t('scheduledEmails.cancelSend')}
                          </Button>
                        )}
                        {isExpanded ? (
                          <ChevronUp className="h-4 w-4 text-zinc-400" />
                        ) : (
                          <ChevronDown className="h-4 w-4 text-zinc-400" />
                        )}
                      </div>
                    </div>

                    {/* Expanded detail */}
                    {isExpanded && (
                      <div className="space-y-3 border-t border-zinc-100 bg-zinc-50/50 px-4 py-3 text-sm">
                        {/* Scheduled time */}
                        <div className="flex items-start gap-2">
                          <Clock className="mt-0.5 h-4 w-4 shrink-0 text-zinc-400" />
                          <div>
                            <span className="text-xs text-zinc-500">
                              {t('scheduledEmails.scheduledFor')}
                            </span>
                            <p className="text-zinc-900">{formatDateTime(item.scheduledAt)}</p>
                          </div>
                        </div>

                        {/* Subject */}
                        <div className="flex items-start gap-2">
                          <Mail className="mt-0.5 h-4 w-4 shrink-0 text-zinc-400" />
                          <div className="min-w-0">
                            <span className="text-xs text-zinc-500">
                              {t('scheduledEmails.subject')}
                            </span>
                            <p className="break-words text-zinc-900">{subject}</p>
                          </div>
                        </div>

                        {/* Body preview */}
                        {bodyPreview && (
                          <div className="flex items-start gap-2">
                            <FileText className="mt-0.5 h-4 w-4 shrink-0 text-zinc-400" />
                            <div className="min-w-0 flex-1">
                              <span className="text-xs text-zinc-500">
                                {t('scheduledEmails.content')}
                              </span>
                              <div className="mt-1 max-h-32 overflow-y-auto rounded border border-zinc-200 bg-white p-2 text-xs leading-relaxed break-words whitespace-pre-wrap text-zinc-700">
                                {bodyPreview}
                              </div>
                            </div>
                          </div>
                        )}

                        {/* Recipients */}
                        {recipients.length > 0 && (
                          <div className="flex items-start gap-2">
                            <Users className="mt-0.5 h-4 w-4 shrink-0 text-zinc-400" />
                            <div className="min-w-0 flex-1">
                              <span className="text-xs text-zinc-500">
                                {t('scheduledEmails.recipients')} ({recipients.length})
                              </span>
                              <div className="mt-1 flex flex-wrap gap-1">
                                {recipients.slice(0, 10).map((email, i) => (
                                  <span
                                    key={i}
                                    className="inline-block rounded border border-zinc-200 bg-white px-1.5 py-0.5 text-xs text-zinc-700"
                                  >
                                    {email}
                                  </span>
                                ))}
                                {recipients.length > 10 && (
                                  <span className="text-xs text-zinc-400">
                                    {t('scheduledEmails.moreRecipients', {
                                      count: recipients.length - 10,
                                    })}
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>
                        )}

                        {/* Created at */}
                        <div className="text-xs text-zinc-400">
                          {t('scheduledEmails.created')} {formatDateTime(item.createdAt)}
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default ScheduledEmailsModal
