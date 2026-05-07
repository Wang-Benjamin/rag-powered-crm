'use client'

import React, { useEffect, useState } from 'react'
import { useTranslations, useLocale } from 'next-intl'
import { ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { PageLoader } from '@/components/ui/page-loader'
import { cn } from '@/utils/cn'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useAuth } from '@/hooks/useAuth'
import { getCachedData, setCachedData } from '@/utils/data-cache'
import { crmService } from '@/lib/api/crm'

const CACHE_TTL_DEFAULT = 30 * 60 * 1000
const CACHE_TTL_ACTIVE = 60 * 1000 // 60s when campaign is actively sending
// Stopgap: replace with SSE/polling invalidation when available

interface CampaignData {
  id: string
  name: string
  emailType: string | null
  offer: string | null
  ask: string | null
  detail: string | null
  customPrompt: string | null
  tradeContext: Record<string, any> | null
  recipientCount: number
  status: string
  createdAt: string
  sentAt: string | null
}

interface Metrics {
  sent: number
  opened: number
  openedPct: number
  replied: number
  repliedPct: number
  failed: number
  failedPct: number
}

interface Recipient {
  customerId: number
  company: string
  email: string
  subject: string | null
  status: string
  sentAt: string | null
  openedAt: string | null
  hasReply: boolean
  repliedAt: string | null
  errorMessage: string | null
}

interface CampaignDetailModalProps {
  campaignId: string
  open: boolean
  onClose: () => void
}

const FILTERS = ['all', 'unopened', 'opened', 'replied', 'bounced'] as const
type FilterKey = (typeof FILTERS)[number]

// Render a trade-context value. Backend ships scalars (moq, lead_time),
// arrays of strings (certifications), and arrays of objects (products with
// {name, fobPrice, landedPrice}). String(val) on the object case yielded
// "[object Object]" — render those fields explicitly instead.
const formatTradeValue = (val: unknown): string => {
  if (val == null || val === '') return '—'
  if (Array.isArray(val)) {
    if (val.length === 0) return '—'
    if (typeof val[0] === 'object' && val[0] !== null) {
      return val
        .map((item) =>
          Object.entries(item as Record<string, unknown>)
            .filter(([, v]) => v != null && v !== '')
            .map(([k, v]) => `${k}: ${v}`)
            .join(', ')
        )
        .join(' • ')
    }
    return val.join(', ')
  }
  if (typeof val === 'object') {
    return Object.entries(val as Record<string, unknown>)
      .filter(([, v]) => v != null && v !== '')
      .map(([k, v]) => `${k}: ${v}`)
      .join(', ')
  }
  return String(val)
}

// snake_case / camelCase -> Title Case for trade-context keys
// (no i18n keys for these yet — backend supplies arbitrary fields)
const formatTradeKey = (key: string): string =>
  key
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\b\w/g, (c) => c.toUpperCase())

// "2h ago" / "2小时前" — uses Intl.RelativeTimeFormat for i18n
const formatRelative = (locale: string, iso: string | null): string => {
  if (!iso) return '—'
  const ts = new Date(iso).getTime()
  if (Number.isNaN(ts)) return '—'
  const ms = ts - Date.now() // negative for past
  const abs = Math.abs(ms)
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto', style: 'short' })
  if (abs < 60_000) return rtf.format(Math.round(ms / 1000), 'second')
  if (abs < 3_600_000) return rtf.format(Math.round(ms / 60_000), 'minute')
  if (abs < 86_400_000) return rtf.format(Math.round(ms / 3_600_000), 'hour')
  if (abs < 30 * 86_400_000) return rtf.format(Math.round(ms / 86_400_000), 'day')
  return new Date(iso).toLocaleDateString(locale, { month: 'short', day: 'numeric', year: 'numeric' })
}

// Filled if achieved; red if delivery failed.
function ProgressDot({ filled, danger }: { filled: boolean; danger?: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        'inline-block h-2 w-2 rounded-full',
        filled
          ? danger
            ? 'bg-threat'
            : 'bg-foreground'
          : 'border border-rule'
      )}
    />
  )
}

export default function CampaignDetailModal({ campaignId, open, onClose }: CampaignDetailModalProps) {
  const locale = useLocale()
  const t = useTranslations('leads')
  const { user } = useAuth()
  const userEmail = user?.email || (user as any)?.userEmail

  const [campaign, setCampaign] = useState<CampaignData | null>(null)
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [recipients, setRecipients] = useState<Recipient[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<FilterKey>('all')
  const [contextExpanded, setContextExpanded] = useState(false)
  const [promptExpanded, setPromptExpanded] = useState(false)

  const cacheKey = `campaign_detail_${campaignId}`

  const fetchDetail = async (bypassCache = false) => {
    if (!campaignId) return

    if (!bypassCache) {
      // Peek at cached data (with default TTL) to check status, then apply correct TTL.
      // Stopgap: replace with SSE/polling invalidation when available.
      type CachedDetail = { campaign: CampaignData; metrics: Metrics; recipients: Recipient[] }
      const peek = getCachedData<CachedDetail>(cacheKey, CACHE_TTL_DEFAULT, userEmail)
      if (peek) {
        const ttl = peek.campaign?.status === 'sending' ? CACHE_TTL_ACTIVE : CACHE_TTL_DEFAULT
        const fresh = getCachedData<CachedDetail>(cacheKey, ttl, userEmail)
        if (fresh) {
          setCampaign(fresh.campaign)
          setMetrics(fresh.metrics)
          setRecipients(fresh.recipients || [])
          setLoading(false)
          return
        }
      }
    }

    try {
      setLoading(true)
      const data = await crmService.getCampaignDetail(campaignId)
      setCampaign(data.campaign)
      setMetrics(data.metrics)
      setRecipients(data.recipients || [])
      setCachedData(
        cacheKey,
        { campaign: data.campaign, metrics: data.metrics, recipients: data.recipients || [] },
        userEmail
      )
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (open && campaignId) {
      fetchDetail()
      setStatusFilter('all')
      setContextExpanded(false)
      setPromptExpanded(false)
    }
  }, [open, campaignId])

  const translateStatus = (status: string) => {
    const statusMap: Record<string, string> = {
      sent: t('campaigns.status.sent'),
      replied: t('campaigns.status.replied'),
      queued: t('campaigns.status.queued'),
      opened: t('campaigns.status.opened'),
      bounced: t('campaigns.status.bounced'),
      failed: t('campaigns.status.failed'),
      sending: t('campaigns.status.sending'),
      scheduled: t('campaigns.status.scheduled'),
      partially_failed: t('campaigns.status.partiallyFailed'),
    }
    return statusMap[status] ?? status
  }

  const filterLabel = (f: FilterKey): string => {
    switch (f) {
      case 'all': return t('campaigns.filter.all')
      case 'unopened': return t('campaigns.filter.notOpened')
      case 'opened': return t('campaigns.filter.opened')
      case 'replied': return t('campaigns.filter.replied')
      case 'bounced': return t('campaigns.status.bounced')
    }
  }

  const matchFilter = (r: Recipient, f: FilterKey): boolean => {
    if (f === 'all') return true
    if (f === 'unopened') return !r.openedAt && r.status === 'sent'
    if (f === 'opened') return !!r.openedAt
    if (f === 'replied') return r.hasReply
    if (f === 'bounced') return r.status === 'failed'
    return true
  }

  const filteredRecipients = recipients.filter((r) => matchFilter(r, statusFilter))

  const hasContext = campaign && (
    campaign.offer || campaign.ask || campaign.detail || campaign.customPrompt
  )

  const hasTradeContext = campaign?.tradeContext &&
    Object.keys(campaign.tradeContext).length > 0

  // Backend semantics (campaign_router.py):
  //   metrics.sent   = COUNT(DISTINCT customer_id WHERE ce.status = 'sent')   — delivered
  //   metrics.failed = COUNT(DISTINCT customer_id WHERE ce.status = 'failed') — bounced
  // So `attempted = sent + failed` and `delivered = sent` (no further math).
  const attempted = metrics ? metrics.sent + metrics.failed : 0
  const delivered = metrics?.sent ?? 0
  const deliveredPct = attempted > 0 ? Math.round((delivered / attempted) * 100) : 0

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] w-full max-w-4xl overflow-y-auto p-0">
        {loading ? (
          <div className="h-64">
            <PageLoader label={t('campaigns.loading')} className="min-h-full" />
          </div>
        ) : !campaign ? (
          <div className="flex h-64 flex-col items-center justify-center gap-3">
            <p className="text-sm text-muted-foreground">{t('campaigns.notFound')}</p>
            <Button variant="outline" size="sm" onClick={onClose}>
              {t('campaigns.close')}
            </Button>
          </div>
        ) : (
          <>
            {/* Header — title, then status · recipients · relative time */}
            <div className="px-8 pt-7 pb-5">
              <DialogHeader className="p-0">
                <DialogTitle className="title-page">
                  {campaign.name}
                </DialogTitle>
              </DialogHeader>
              <div className="mt-1.5 text-sm text-muted-foreground">
                <span>{translateStatus(campaign.status)}</span>
                <span className="mx-1.5 text-rule">·</span>
                <span>{t('campaigns.recipients', { count: campaign.recipientCount })}</span>
                <span className="mx-1.5 text-rule">·</span>
                <span>{formatRelative(locale, campaign.sentAt || campaign.createdAt)}</span>
              </div>
            </div>

            {/* Metrics — borderless 4-column grid, big numerals.
                Sent (attempted) → Delivered → Opened → Replied funnel. */}
            {metrics && (
              <div className="grid grid-cols-4 gap-6 px-8 pb-7">
                <div>
                  <div className="text-sm text-muted-foreground">{t('campaigns.sent')}</div>
                  <div className="mt-2 text-3xl font-semibold leading-none tabular-nums text-foreground">
                    {attempted.toLocaleString()}
                  </div>
                  <div className="mt-2 h-4">&nbsp;</div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground">{t('campaigns.delivered')}</div>
                  <div className="mt-2 text-3xl font-semibold leading-none tabular-nums text-foreground">
                    {delivered.toLocaleString()}
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground tabular-nums">
                    {attempted > 0 ? `${deliveredPct}%` : '—'}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground">{t('campaigns.opened')}</div>
                  <div
                    className={cn(
                      'mt-2 text-3xl font-semibold leading-none tabular-nums',
                      metrics.opened === 0 ? 'text-rule' : 'text-foreground'
                    )}
                  >
                    {metrics.opened.toLocaleString()}
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground tabular-nums">
                    {metrics.opened > 0 ? `${metrics.openedPct}%` : '—'}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground">{t('campaigns.replied')}</div>
                  <div
                    className={cn(
                      'mt-2 text-3xl font-semibold leading-none tabular-nums',
                      metrics.replied === 0 ? 'text-rule' : 'text-foreground'
                    )}
                  >
                    {metrics.replied.toLocaleString()}
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground tabular-nums">
                    {metrics.replied > 0 ? `${metrics.repliedPct}%` : '—'}
                  </div>
                </div>
              </div>
            )}

            {/* Hairline divider */}
            <div className="border-t border-border" />

            {/* Filter — text-only tabs (active = bold foreground) */}
            <div className="flex items-center gap-7 px-8 pt-5">
              {FILTERS.map((f) => (
                <button
                  key={f}
                  type="button"
                  onClick={() => setStatusFilter(f)}
                  className={cn(
                    'text-sm transition-colors',
                    statusFilter === f
                      ? 'font-semibold text-foreground'
                      : 'text-mute hover:text-foreground'
                  )}
                >
                  {filterLabel(f)}
                </button>
              ))}
            </div>

            {/* Recipient rows — no table chrome, hairline separators only.
                Status as 4-dot funnel: Sent · Delivered · Opened · Replied */}
            <div className="px-8 pt-3 pb-6">
              {filteredRecipients.length === 0 ? (
                <div className="py-10 text-center text-sm text-muted-foreground">
                  {t('campaigns.noRecipientData')}
                </div>
              ) : (
                filteredRecipients.map((r, i) => {
                  const isFailed = r.status === 'failed'
                  const wasSent = r.status === 'sent' || r.status === 'failed'
                  const wasDelivered = r.status === 'sent'
                  return (
                    <div
                      key={i}
                      className="grid grid-cols-12 items-center gap-4 border-b border-border py-4 last:border-0"
                    >
                      <div className="col-span-3 min-w-0">
                        <div className="truncate text-sm font-semibold text-foreground">
                          {r.company || '—'}
                        </div>
                        <div className="truncate text-xs text-muted-foreground">
                          {r.email}
                        </div>
                      </div>
                      <div className="col-span-5 min-w-0">
                        <div
                          className="truncate text-sm text-muted-foreground"
                          title={r.subject ?? undefined}
                        >
                          {r.subject || '—'}
                        </div>
                        {isFailed && r.errorMessage && (
                          <div
                            className="mt-0.5 truncate text-[11px] text-threat"
                            title={r.errorMessage}
                          >
                            {r.errorMessage}
                          </div>
                        )}
                      </div>
                      <div className="col-span-2 flex items-center gap-1.5">
                        <ProgressDot filled={wasSent} />
                        <ProgressDot filled={wasDelivered} danger={isFailed} />
                        <ProgressDot filled={!!r.openedAt} />
                        <ProgressDot filled={r.hasReply} />
                      </div>
                      <div className="col-span-2 text-right text-xs text-muted-foreground">
                        {formatRelative(locale, r.repliedAt || r.openedAt || r.sentAt)}
                      </div>
                    </div>
                  )
                })
              )}
            </div>

            {/* Campaign Context — collapsed by default, lives below the rows
                so the metric/funnel area stays uncluttered. */}
            {hasContext && (
              <div className="border-t border-border px-8 py-4">
                <button
                  type="button"
                  onClick={() => setContextExpanded(!contextExpanded)}
                  className="flex items-center gap-1 text-xs text-mute transition-colors hover:text-foreground"
                >
                  <ChevronRight
                    className={cn(
                      'h-3.5 w-3.5 transition-transform',
                      contextExpanded && 'rotate-90'
                    )}
                  />
                  {t('campaigns.context')}
                </button>

                {contextExpanded && (
                  <div className="mt-3 rounded-lg border border-border bg-muted/30 p-4">
                    <div className="grid grid-cols-2 gap-x-6 gap-y-3">
                      {campaign.offer && (
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                            {t('campaigns.offerLabel')}
                          </p>
                          <p className="mt-0.5 text-sm text-foreground">{campaign.offer}</p>
                        </div>
                      )}
                      {campaign.ask && (
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                            {t('campaigns.askLabel')}
                          </p>
                          <p className="mt-0.5 text-sm text-foreground">{campaign.ask}</p>
                        </div>
                      )}
                      {campaign.detail && (
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                            {t('campaigns.detailLabel')}
                          </p>
                          <p className="mt-0.5 text-sm text-foreground">{campaign.detail}</p>
                        </div>
                      )}
                      {campaign.customPrompt && (
                        <div className={campaign.offer || campaign.ask || campaign.detail ? 'col-span-2' : ''}>
                          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                            {t('campaigns.promptLabel')}
                          </p>
                          <p className="mt-0.5 text-sm text-foreground">
                            {promptExpanded || campaign.customPrompt.length <= 200
                              ? campaign.customPrompt
                              : campaign.customPrompt.slice(0, 200) + '…'}
                          </p>
                          {campaign.customPrompt.length > 200 && (
                            <button
                              type="button"
                              onClick={() => setPromptExpanded(!promptExpanded)}
                              className="mt-1 text-xs text-muted-foreground underline-offset-2 hover:underline"
                            >
                              {promptExpanded ? t('campaigns.showLess') : t('campaigns.showMore')}
                            </button>
                          )}
                        </div>
                      )}
                    </div>

                    {hasTradeContext && (
                      <div className="mt-4 border-t border-border pt-4">
                        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          {t('campaigns.tradeLabel')}
                        </p>
                        <div className="grid grid-cols-2 gap-x-6 gap-y-2">
                          {Object.entries(campaign.tradeContext!).map(([key, val]) => (
                            <div key={key}>
                              <p className="text-xs text-muted-foreground">{formatTradeKey(key)}</p>
                              <p className="text-sm text-foreground">{formatTradeValue(val)}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
