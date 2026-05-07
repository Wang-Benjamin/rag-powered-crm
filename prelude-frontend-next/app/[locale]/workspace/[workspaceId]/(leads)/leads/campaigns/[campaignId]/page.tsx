'use client'

import React, { useEffect, useState } from 'react'
import { useRouter } from '@/i18n/navigation'
import { useParams } from 'next/navigation'
import { useTranslations, useLocale } from 'next-intl'
import { ArrowLeft } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { PageLoader } from '@/components/ui/page-loader'
import { useAuth } from '@/hooks/useAuth'
import { getCachedData, setCachedData } from '@/utils/data-cache'
import { crmService } from '@/lib/api/crm'

const CACHE_TTL_DEFAULT = 30 * 60 * 1000 // 30 minutes
const CACHE_TTL_ACTIVE = 60 * 1000 // 60s when campaign is actively sending
// Stopgap: replace with SSE/polling invalidation when available

interface CampaignData {
  id: string
  name: string
  emailType: string | null
  offer: string | null
  ask: string | null
  detail: string | null
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
  status: string
  sentAt: string | null
  openedAt: string | null
  hasReply: boolean
  repliedAt: string | null
  errorMessage: string | null
}

export default function CampaignDetailPage() {
  const params = useParams()
  const router = useRouter()
  const t = useTranslations('leads')
  const locale = useLocale()
  const campaignId = params?.campaignId as string
  const workspaceId = params?.workspaceId as string

  const { user } = useAuth()
  const userEmail = user?.email || (user as any)?.userEmail
  const [campaign, setCampaign] = useState<CampaignData | null>(null)
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [recipients, setRecipients] = useState<Recipient[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<string>('all')

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
    fetchDetail()
  }, [campaignId])

  const handleBack = () => {
    router.push(`/workspace/${workspaceId}/leads?tab=campaigns`)
  }

  const formatDate = (iso: string | null) => {
    if (!iso) return '—'
    const d = new Date(iso)
    return d.toLocaleDateString(locale, { month: 'short', day: 'numeric' })
  }

  const getDisplayStatus = (r: Recipient): string => {
    if (r.status === 'failed') return 'failed'
    if (r.status === 'queued') return 'queued'
    if (r.hasReply) return 'replied'
    if (r.openedAt) return 'opened'
    if (r.status === 'sent') return 'sent'
    return r.status
  }

  const statusBadgeVariant = (status: string) => {
    switch (status) {
      case 'replied': return 'default'
      case 'opened': return 'secondary'
      case 'sending': return 'secondary'
      case 'scheduled': return 'secondary'
      case 'queued': return 'outline'
      case 'sent': return 'outline'
      case 'failed': return 'destructive'
      case 'partially_failed': return 'destructive'
      default: return 'outline'
    }
  }

  const translateStatus = (status: string) => {
    const key = status.toLowerCase().replace(' ', '_') as string
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
    return statusMap[key] || status
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <PageLoader label={t('campaigns.loading')} />
      </div>
    )
  }

  if (!campaign) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4">
        <p className="text-mute">{t('campaigns.notFound')}</p>
        <Button variant="outline" onClick={handleBack}>
          {t('campaigns.backToCampaigns')}
        </Button>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-6xl p-6">
      {/* Header */}
      <div className="mb-6">
        <button
          onClick={handleBack}
          className="mb-3 flex items-center gap-1 text-sm text-mute transition-colors hover:text-deep"
        >
          <ArrowLeft className="h-4 w-4" />
          {t('campaigns.backToCampaigns')}
        </button>
        <div className="flex items-center gap-3">
          <h1 className="title-page">{campaign.name}</h1>
          <Badge
            variant={
              campaign.status === 'sent'
                ? 'default'
                : campaign.status === 'sending'
                  ? 'secondary'
                  : 'destructive'
            }
          >
            {campaign.status
              ? translateStatus(campaign.status.charAt(0).toUpperCase() + campaign.status.slice(1))
              : t('campaigns.unknown')}
          </Badge>
        </div>
        <p className="mt-1 text-sm text-mute">
          {formatDate(campaign.sentAt || campaign.createdAt)} ·{' '}
          {t('campaigns.recipients', { count: campaign.recipientCount })}
        </p>
      </div>

      {/* Metrics Cards */}
      {metrics && (
        <div className="mb-6 grid grid-cols-4 gap-3">
          <MetricCard
            label={t('campaigns.sent')}
            value={metrics.sent}
          />
          <MetricCard
            label={t('campaigns.opened')}
            value={metrics.opened}
            pct={metrics.openedPct}
          />
          <MetricCard
            label={t('campaigns.replied')}
            value={metrics.replied}
            pct={metrics.repliedPct}
          />
          <MetricCard
            label={t('campaigns.undeliverable')}
            value={metrics.failed}
            pct={metrics.failedPct}
          />
        </div>
      )}

      {/* Filter Bar */}
      <div className="mb-4 flex items-center gap-2">
        {['all', 'not_opened', 'not_replied', 'opened', 'replied', 'failed'].map((filter) => {
          const labelKey = filter === 'all' ? 'all' : filter === 'not_opened' ? 'notOpened' : filter === 'not_replied' ? 'notReplied' : filter
          return (
            <button
              key={filter}
              onClick={() => setStatusFilter(filter)}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                statusFilter === filter
                  ? 'bg-deep text-bone'
                  : 'bg-cream text-mute hover:bg-cream'
              }`}
            >
              {t(`campaigns.filter.${labelKey}` as any)}
            </button>
          )
        })}
      </div>

      {/* Recipient Table */}
      <div className="overflow-hidden rounded-lg border border-rule">
        <table className="w-full">
          <thead>
            <tr className="border-b border-rule bg-paper">
              <th className="px-4 py-3 text-left text-xs font-medium tracking-wider text-mute uppercase">
                {t('campaigns.columns.lead')}
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium tracking-wider text-mute uppercase">
                {t('campaigns.columns.email')}
              </th>
              <th className="px-4 py-3 text-center text-xs font-medium tracking-wider text-mute uppercase">
                {t('campaigns.columns.status')}
              </th>
              <th className="px-4 py-3 text-center text-xs font-medium tracking-wider text-mute uppercase">
                {t('campaigns.columns.sent')}
              </th>
              <th className="px-4 py-3 text-center text-xs font-medium tracking-wider text-mute uppercase">
                {t('campaigns.columns.opened')}
              </th>
              <th className="px-4 py-3 text-center text-xs font-medium tracking-wider text-mute uppercase">
                {t('campaigns.columns.replied')}
              </th>
            </tr>
          </thead>
          <tbody>
            {recipients.filter((r) => {
              if (statusFilter === 'all') return true
              if (statusFilter === 'not_opened') return !r.openedAt && r.status === 'sent'
              if (statusFilter === 'not_replied') return !r.hasReply && r.status === 'sent'
              if (statusFilter === 'failed') return r.status === 'failed'
              if (statusFilter === 'opened') return !!r.openedAt
              if (statusFilter === 'replied') return r.hasReply
              return true
            }).map((r, i) => (
              <tr key={i} className="border-b border-rule transition-colors hover:bg-paper">
                <td className="px-4 py-3 text-sm font-medium text-deep">{r.company || '—'}</td>
                <td className="px-4 py-3 text-sm text-mute">{r.email}</td>
                <td className="px-4 py-3 text-center">
                  <Badge variant={statusBadgeVariant(getDisplayStatus(r))}>{translateStatus(getDisplayStatus(r))}</Badge>
                </td>
                <td className="px-4 py-3 text-center text-sm text-mute">
                  {formatDate(r.sentAt)}
                </td>
                <td className="px-4 py-3 text-center text-sm text-mute">
                  {formatDate(r.openedAt)}
                </td>
                <td className="px-4 py-3 text-center text-sm text-mute">
                  {formatDate(r.repliedAt)}
                </td>
              </tr>
            ))}
            {recipients.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-sm text-mute">
                  {t('campaigns.noRecipientData')}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function MetricCard({
  label,
  value,
  pct,
}: {
  label: string
  value: number
  pct?: number
}) {
  return (
    <Card>
      <CardContent className="px-3 py-2.5">
        <p className="text-[10px] font-semibold tracking-wide text-mute uppercase">{label}</p>
        <div className="flex items-baseline gap-2">
          <span className="text-xl font-bold leading-tight tabular-nums">{value}</span>
          {pct !== undefined && pct > 0 && <span className="text-sm text-mute">{pct}%</span>}
        </div>
      </CardContent>
    </Card>
  )
}
