'use client'

import React, { useEffect, useState, useMemo } from 'react'
import { BarChart3, ChevronRight } from 'lucide-react'
import { PageLoader } from '@/components/ui/page-loader'
import { useAuth } from '@/hooks/useAuth'
import { getCachedData, setCachedData } from '@/utils/data-cache'
import { useLocale, useTranslations } from 'next-intl'
import { crmService } from '@/lib/api/crm'
import { cn } from '@/utils/cn'
import { KpiValue } from '@/components/ui/KpiValue'
import CampaignDetailModal from './CampaignDetailModal'

const CACHE_KEY = 'campaigns_list'
const CACHE_TTL_DEFAULT = 30 * 60 * 1000 // 30 minutes
const CACHE_TTL_ACTIVE = 60 * 1000 // 60s when any campaign is actively sending
// Stopgap: replace with SSE/polling invalidation when available

interface Campaign {
  id: string
  name: string
  recipientCount: number
  status: string
  createdAt: string
  sentAt: string | null
  sent: number
  opened: number
  openedPct: number
  replied: number
  repliedPct: number
  failed: number
}

export default function CampaignList() {
  const { user } = useAuth()
  const locale = useLocale()
  const t = useTranslations('leads')
  const userEmail = user?.email || (user as any)?.userEmail
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedCampaignId, setSelectedCampaignId] = useState<string | null>(null)
  const [weekly, setWeekly] = useState<{ outreachWeek: number; repliesWeek: number }>({
    outreachWeek: 0,
    repliesWeek: 0,
  })

  const fetchCampaigns = async (bypassCache = false) => {
    if (!bypassCache) {
      // Use short TTL when any campaign is actively sending, 30-min otherwise
      // Stopgap: replace with SSE/polling invalidation when available
      const cached = getCachedData<Campaign[]>(CACHE_KEY, CACHE_TTL_DEFAULT, userEmail)
      if (cached) {
        const ttl = cached.some((c) => c.status === 'sending') ? CACHE_TTL_ACTIVE : CACHE_TTL_DEFAULT
        const fresh = getCachedData<Campaign[]>(CACHE_KEY, ttl, userEmail)
        if (fresh) {
          setCampaigns(fresh)
          setLoading(false)
          return
        }
      }
    }

    try {
      setLoading(true)
      const data = await crmService.getCampaigns()
      const list = data.campaigns || []
      setCampaigns(list)
      setCachedData(CACHE_KEY, list, userEmail)
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCampaigns()
    crmService
      .getOutreachWeekly()
      .then((res) => setWeekly(res))
      .catch(() => {})
  }, [])

  // Aggregate stats
  const stats = useMemo(() => {
    if (campaigns.length === 0) return null
    const totalSent = campaigns.reduce((sum, c) => sum + c.sent, 0)
    const totalRecipients = campaigns.reduce((sum, c) => sum + c.recipientCount, 0)
    const totalOpened = campaigns.reduce((sum, c) => sum + c.opened, 0)
    const totalReplied = campaigns.reduce((sum, c) => sum + c.replied, 0)
    return {
      count: campaigns.length,
      totalSent,
      totalRecipients,
      totalOpened,
      totalReplied,
      avgOpenPct: totalSent > 0 ? Math.round((totalOpened / totalSent) * 100) : 0,
      avgReplyPct: totalSent > 0 ? Math.round((totalReplied / totalSent) * 100) : 0,
    }
  }, [campaigns])

  const handleRowClick = (campaignId: string) => {
    setSelectedCampaignId(campaignId)
  }

  const formatDate = (iso: string) => {
    const d = new Date(iso)
    return d.toLocaleDateString(locale, { month: 'short', day: 'numeric', year: 'numeric' })
  }

  const statusLabels: Record<string, string> = {
    sent: t('campaigns.status.sent'),
    sending: t('campaigns.status.sending'),
    partially_failed: t('campaigns.status.partiallyFailed'),
    replied: t('campaigns.status.replied'),
    queued: t('campaigns.status.queued'),
    opened: t('campaigns.status.opened'),
    bounced: t('campaigns.status.bounced'),
    failed: t('campaigns.status.failed'),
    scheduled: t('campaigns.status.scheduled'),
  }
  const translateStatus = (status: string) => statusLabels[status] ?? status

  // Status accent — colored dot at the row's left edge.
  // Pulses for `sending` so live activity is the only motion on the page.
  const statusDotColor = (status: string) => {
    switch (status) {
      case 'sent': return 'bg-accent'
      case 'sending': return 'bg-accent'
      case 'scheduled': return 'bg-gold'
      case 'partially_failed': return 'bg-gold'
      case 'failed': return 'bg-threat'
      default: return 'bg-fog'
    }
  }

  const pctColor = (pct: number) =>
    pct >= 50
      ? 'text-accent'
      : pct >= 20
        ? 'text-gold'
        : 'text-mute'

  return (
    <div className="mx-auto max-w-7xl px-6 py-6">
      {loading && campaigns.length === 0 ? (
        <div className="py-10">
          <PageLoader label={t('campaigns.loading')} />
        </div>
      ) : campaigns.length === 0 ? (
        <div className="py-20 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-muted">
            <BarChart3 className="h-6 w-6 text-mute" />
          </div>
          <div className="mb-1.5 text-base font-semibold leading-tight text-foreground">
            {t('campaigns.noCampaigns')}
          </div>
          <p className="mx-auto max-w-sm text-xs text-mute">
            {t('campaigns.noCampaignsDescription')}
          </p>
        </div>
      ) : (
        <>
          {/* KPI strip — matches the Deals page pattern (font-display value,
              font-mono eyebrow). The two right cards show all-outreach in the
              last 7 days; the left two are per-campaign aggregates. They can
              diverge — outreach counts ad-hoc emails too. */}
          {stats && (
            <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="flex min-h-[96px] flex-col justify-between rounded-xl border border-rule bg-bone p-5">
                <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-mute">
                  {t('campaigns.title')}
                </span>
                <KpiValue>{stats.count.toLocaleString()}</KpiValue>
                <span className="text-[12px] leading-[1.35] text-mute">
                  {t('campaigns.recipients', { count: stats.totalRecipients })}
                </span>
              </div>
              <div className="flex min-h-[96px] flex-col justify-between rounded-xl border border-rule bg-bone p-5">
                <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-mute">
                  {t('campaigns.sent')}
                </span>
                <KpiValue>{stats.totalSent.toLocaleString()}</KpiValue>
                <span className="text-[12px] leading-[1.35] text-mute">&nbsp;</span>
              </div>
              <div className="flex min-h-[96px] flex-col justify-between rounded-xl border border-rule bg-bone p-5">
                <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-mute">
                  {t('campaigns.outreachWeek')}
                </span>
                <KpiValue accent={weekly.outreachWeek > 0 ? 'accent' : 'deep'}>
                  {weekly.outreachWeek.toLocaleString()}
                </KpiValue>
                <span className="text-[12px] leading-[1.35] text-mute">
                  {t('campaigns.outreachWeekSub')}
                </span>
              </div>
              <div className="flex min-h-[96px] flex-col justify-between rounded-xl border border-rule bg-bone p-5">
                <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-mute">
                  {t('campaigns.repliesWeek')}
                </span>
                <KpiValue accent={weekly.repliesWeek > 0 ? 'gold' : 'deep'}>
                  {weekly.repliesWeek.toLocaleString()}
                </KpiValue>
                <span className="text-[12px] leading-[1.35] text-mute">
                  {t('campaigns.repliesWeekSub')}
                </span>
              </div>
            </div>
          )}

          {/* Column header — labels rendered once, then stripped from rows */}
          <div className="mb-2 flex items-center gap-4 px-4 text-[10px] font-semibold uppercase tracking-wider text-mute">
            <div className="w-2 shrink-0" />
            <div className="min-w-0 flex-1">{t('campaigns.name')}</div>
            <div className="flex shrink-0 items-center gap-5">
              <div className="w-14 text-right">{t('campaigns.sent')}</div>
              <div className="w-24 text-right">{t('campaigns.opened')}</div>
              <div className="w-24 text-right">{t('campaigns.replied')}</div>
              <div className="w-14 text-right">{t('campaigns.status.failed')}</div>
            </div>
            <div className="h-4 w-4 shrink-0" />
          </div>

          <div className="space-y-1.5">
            {campaigns.map((c) => (
              <div
                key={c.id}
                onClick={() => handleRowClick(c.id)}
                className="group flex cursor-pointer items-center gap-4 rounded-lg border border-border bg-background px-4 py-3 transition-all hover:border-rule hover:shadow-sm"
              >
                {/* Status dot — color encodes status, pulses for active sends */}
                <span className="relative flex h-2 w-2 shrink-0" title={translateStatus(c.status)}>
                  {c.status === 'sending' && (
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-75" />
                  )}
                  <span className={cn('relative inline-flex h-2 w-2 rounded-full', statusDotColor(c.status))} />
                </span>

                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-semibold leading-tight text-foreground">
                    {c.name}
                  </div>
                  <div className="mt-1 text-[11px] leading-tight text-mute">
                    <span>{translateStatus(c.status)}</span>
                    <span className="mx-1.5 text-rule">·</span>
                    <span>{formatDate(c.createdAt)}</span>
                    {c.recipientCount > 0 && (
                      <>
                        <span className="mx-1.5 text-rule">·</span>
                        <span>{t('campaigns.recipients', { count: c.recipientCount })}</span>
                      </>
                    )}
                  </div>
                </div>

                {/* Metrics — column widths match the header strip exactly */}
                <div className="flex shrink-0 items-center gap-5">
                  <div className="w-14 text-right">
                    <p className="text-sm font-semibold tabular-nums text-foreground">
                      {c.sent}
                    </p>
                  </div>
                  <div className="w-24">
                    {c.sent > 0 ? (
                      <div className="flex items-center gap-1.5">
                        <div className="h-1 flex-1 overflow-hidden rounded-full bg-cream">
                          <div className="h-full rounded-full bg-accent" style={{ width: `${c.openedPct}%` }} />
                        </div>
                        <span className={cn('w-9 text-right text-sm font-semibold tabular-nums', pctColor(c.openedPct))}>
                          {c.openedPct}%
                        </span>
                      </div>
                    ) : (
                      <p className="text-right text-sm font-semibold text-mute">—</p>
                    )}
                  </div>
                  <div className="w-24">
                    {c.sent > 0 ? (
                      <div className="flex items-center gap-1.5">
                        <div className="h-1 flex-1 overflow-hidden rounded-full bg-cream">
                          <div className="h-full rounded-full bg-gold" style={{ width: `${c.repliedPct}%` }} />
                        </div>
                        <span className={cn('w-9 text-right text-sm font-semibold tabular-nums', pctColor(c.repliedPct))}>
                          {c.repliedPct}%
                        </span>
                      </div>
                    ) : (
                      <p className="text-right text-sm font-semibold text-mute">—</p>
                    )}
                  </div>
                  {/* Always render Failed slot so columns stay aligned across rows */}
                  <div className="w-14 text-right">
                    {c.failed > 0 ? (
                      <p className="text-sm font-semibold tabular-nums text-threat">{c.failed}</p>
                    ) : (
                      <p className="text-sm font-semibold tabular-nums text-mute">—</p>
                    )}
                  </div>
                </div>

                <ChevronRight className="h-4 w-4 shrink-0 text-rule transition-colors group-hover:text-mute" />
              </div>
            ))}
          </div>
        </>
      )}

      {selectedCampaignId && (
        <CampaignDetailModal
          campaignId={selectedCampaignId}
          open={!!selectedCampaignId}
          onClose={() => setSelectedCampaignId(null)}
        />
      )}
    </div>
  )
}
