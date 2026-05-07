'use client'

import React from 'react'
import { useTranslations } from 'next-intl'
import {
  Loader2,
  DoorOpen,
  Copy,
  ExternalLink,
  Eye,
  Users,
  Check,
  Clock,
  Edit3,
  X,
  AlertCircle,
  RefreshCw,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { toast } from 'sonner'
import { crmApiClient } from '@/lib/api/client'
import type { Deal } from '@/types/crm'

// Hide the legacy 报价 / 交易室 / 买家兴趣 / 访问记录 four-card dashboard.
// The dashboard JSX, share-link copy logic, and view-tracking polling all stay
// behind this flag so they can be revived without rewriting.
const SHOW_LEGACY_ROOM_DASHBOARD = false

export interface DraftColumnState {
  subject: string
  body: string
  loading: boolean
  error: string | null
}

export interface DealRoomTabProps {
  localDeal: Deal
  setLocalDeal: React.Dispatch<React.SetStateAction<Deal | null>>
  isLoadingRoom: boolean
  isCreatingRoom: boolean
  roomData: any
  roomAnalytics: any
  loadDealRoom: () => Promise<void>
  handleCreateDealRoom: () => Promise<void>
  handleCopyLink: (shareToken: string) => void
  linkCopied: boolean
  getRoomStatusVariant: (
    status: string
  ) => 'neutral' | 'info' | 'progress' | 'warning' | 'success' | 'danger'
  formatRoomStatus: (status: string) => string
  editingField: string | null
  setEditingField: (field: string | null) => void
  isSavingField: boolean
  setIsSavingField: (saving: boolean) => void
  roomForm: {
    fobPrice: string
    landedPrice: string
    currency: string
    moq: string
    leadTimeDays: string
    productName: string
    customMessageZh: string
    customMessageEn: string
  }
  setRoomForm: React.Dispatch<
    React.SetStateAction<{
      fobPrice: string
      landedPrice: string
      currency: string
      moq: string
      leadTimeDays: string
      productName: string
      customMessageZh: string
      customMessageEn: string
    }>
  >
  isTranslating: boolean
  setIsTranslating: (value: boolean) => void
  draftOpen: boolean
  draftZh: DraftColumnState
  draftEn: DraftColumnState
  setDraftZh: React.Dispatch<React.SetStateAction<DraftColumnState>>
  setDraftEn: React.Dispatch<React.SetStateAction<DraftColumnState>>
  sendLanguage: 'zh' | 'en'
  setSendLanguage: React.Dispatch<React.SetStateAction<'zh' | 'en'>>
  isSendingDraft: boolean
  generateDraft: (language: 'zh' | 'en') => Promise<void>
  openBilingualDraft: () => void
  handleCancelDraft: () => void
  handleSendDraft: () => Promise<void>
  handleCopyDraftColumn: (language: 'zh' | 'en') => Promise<void>
}

const DealRoomTab: React.FC<DealRoomTabProps> = ({
  localDeal,
  setLocalDeal,
  isLoadingRoom,
  isCreatingRoom,
  roomData,
  roomAnalytics,
  loadDealRoom,
  handleCreateDealRoom,
  handleCopyLink,
  linkCopied,
  getRoomStatusVariant,
  formatRoomStatus,
  editingField,
  setEditingField,
  isSavingField,
  setIsSavingField,
  roomForm,
  setRoomForm,
  isTranslating,
  setIsTranslating,
  draftOpen,
  draftZh,
  draftEn,
  setDraftZh,
  setDraftEn,
  sendLanguage,
  setSendLanguage,
  isSendingDraft,
  generateDraft,
  openBilingualDraft,
  handleCancelDraft,
  handleSendDraft,
  handleCopyDraftColumn,
}) => {
  const t = useTranslations('crm')
  return (
    <div className="w-full p-5">
      {isLoadingRoom ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-mute" />
        </div>
      ) : (localDeal.shareToken || roomData) && localDeal.fobPrice ? (
        SHOW_LEGACY_ROOM_DASHBOARD ? (
        /* Deal room exists with pricing -- management view */
        <div className="space-y-4">
          {/* Top row: Deal Room (70%) + Quote (30%) */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-10">
            <div className="lg:order-2 lg:col-span-7">
              {/* Room URL & Status */}
              <div className="h-full rounded-lg border border-rule bg-bone p-6">
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="title-panel">
                    {t('dealRoom.title')}
                  </h3>
                  <Badge
                    variant={getRoomStatusVariant(
                      roomData?.roomStatus || localDeal.roomStatus || 'draft'
                    )}
                  >
                    {formatRoomStatus(
                      roomData?.roomStatus || localDeal.roomStatus || 'draft'
                    )}
                  </Badge>
                </div>

                {/* Shareable URL */}
                <div className="mb-4">
                  <label className="mb-2 block text-sm font-medium text-mute">
                    {t('dealRoom.shareableLink')}
                  </label>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 truncate rounded-md border border-rule bg-paper px-3 py-2 font-mono text-sm text-ink">
                      {typeof window !== 'undefined'
                        ? `${window.location.origin}/deal/${roomData?.shareToken || localDeal.shareToken}`
                        : `/deal/${roomData?.shareToken || localDeal.shareToken}`}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        handleCopyLink(roomData?.shareToken || localDeal.shareToken || '')
                      }
                      className="flex-shrink-0"
                    >
                      {linkCopied ? (
                        <Check className="h-4 w-4" />
                      ) : (
                        <Copy className="h-4 w-4" />
                      )}
                      <span className="ml-1.5">
                        {linkCopied ? t('dealRoom.copied') : t('dealRoom.copy')}
                      </span>
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        const token = roomData?.shareToken || localDeal.shareToken
                        window.open(`${window.location.origin}/deal/${token}`, '_blank')
                      }}
                      className="flex-shrink-0"
                    >
                      <ExternalLink className="h-4 w-4" />
                      <span className="ml-1.5">{t('dealRoom.open')}</span>
                    </Button>
                  </div>
                </div>

                {/* Quick Stats */}
                <div className="grid grid-cols-3 gap-4">
                  <div className="rounded-lg bg-paper p-4 text-center">
                    <div className="mb-1 flex items-center justify-center gap-1.5">
                      <Eye className="h-4 w-4 text-mute" />
                      <span className="text-sm font-medium text-mute">
                        {t('dealRoom.totalViews')}
                      </span>
                    </div>
                    <p className="text-2xl tabular-nums text-deep">
                      {localDeal.viewCount ?? roomAnalytics?.totalViews ?? 0}
                    </p>
                  </div>
                  <div className="rounded-lg bg-paper p-4 text-center">
                    <div className="mb-1 flex items-center justify-center gap-1.5">
                      <Users className="h-4 w-4 text-mute" />
                      <span className="text-sm font-medium text-mute">
                        {t('dealRoom.uniqueVisitors')}
                      </span>
                    </div>
                    <p className="text-2xl tabular-nums text-deep">
                      {roomAnalytics?.uniqueVisitors ?? 0}
                    </p>
                  </div>
                  <div className="rounded-lg bg-paper p-4 text-center">
                    <div className="mb-1 flex items-center justify-center gap-1.5">
                      <Clock className="h-4 w-4 text-mute" />
                      <span className="text-sm font-medium text-mute">
                        {t('dealRoom.lastViewed')}
                      </span>
                    </div>
                    <p className="text-sm font-semibold text-deep">
                      {roomData?.lastViewedAt || localDeal.lastViewedAt
                        ? new Date(
                            roomData?.lastViewedAt || localDeal.lastViewedAt!
                          ).toLocaleDateString()
                        : t('dealRoom.never')}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Left column: Quote / Pricing (30%) */}
            <div className="lg:order-1 lg:col-span-3">
              {(() => {
                const qd = roomData?.quoteData
                const isEditing = editingField === 'quote'

                // Save quote edit handler
                const handleSaveQuote = async (formData: {
                  fobPrice: string
                  landedPrice: string
                  moq: string
                  fobCurrency: string
                }) => {
                  if (!localDeal?.dealId) return
                  setIsSavingField(true)
                  try {
                    const update: Record<string, any> = {}
                    const fob = parseFloat(formData.fobPrice)
                    const landed = parseFloat(formData.landedPrice)
                    const moq = parseInt(formData.moq)
                    if (!isNaN(fob)) update.fobPrice = fob
                    if (!isNaN(landed)) update.landedPrice = landed
                    if (!isNaN(moq)) update.moq = moq
                    if (formData.fobCurrency) update.fobCurrency = formData.fobCurrency

                    await crmApiClient.put(`/deals/${localDeal.dealId}`, update)
                    setLocalDeal({ ...localDeal, ...update })
                    // Reload deal room to get fresh quoteData
                    await loadDealRoom()
                    setEditingField(null)
                    toast(t('toasts.success'))
                  } catch (err: any) {
                    toast.error(t('toasts.error'), { description: err.message })
                  } finally {
                    setIsSavingField(false)
                  }
                }

                if (!qd?.options?.length && !isEditing)
                  return (
                    <div
                      className="h-full cursor-pointer rounded-lg border border-rule bg-bone p-6 transition-colors hover:border-rule"
                      onClick={() => setEditingField('quote')}
                    >
                      <h3 className="mb-1 title-block">
                        {t('dealRoom.pricing') || 'Pricing'}
                      </h3>
                      <p className="text-xs text-mute">{t('dealModal.clickToAdd')}</p>
                    </div>
                  )

                if (isEditing) {
                  const opt = qd?.options?.[0]
                  return (
                    <div className="h-full rounded-lg border border-rule bg-bone p-6">
                      <div className="mb-4 flex items-center justify-between">
                        <h3 className="title-block">
                          {t('dealRoom.pricing') || 'Pricing'}
                        </h3>
                        <button
                          onClick={() => setEditingField(null)}
                          className="text-mute hover:text-ink"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                      <form
                        onSubmit={(e) => {
                          e.preventDefault()
                          const fd = new FormData(e.currentTarget)
                          handleSaveQuote({
                            fobPrice: fd.get('fobPrice') as string,
                            landedPrice: fd.get('landedPrice') as string,
                            moq: fd.get('moq') as string,
                            fobCurrency: fd.get('fobCurrency') as string,
                          })
                        }}
                        className="space-y-3"
                      >
                        <div>
                          <label className="mb-1 block text-xs font-medium text-mute">
                            {t('dealColumns.fobPrice')}
                          </label>
                          <div className="flex">
                            <span className="rounded-l-md border border-r-0 border-rule bg-paper px-3 py-2 text-sm text-mute">
                              $
                            </span>
                            <input
                              name="fobPrice"
                              type="number"
                              step="0.01"
                              defaultValue={opt?.fobPrice ?? localDeal.fobPrice ?? ''}
                              className="flex-1 rounded-r-md border border-rule px-3 py-2 text-sm focus:ring-2 focus:ring-accent focus:outline-none"
                            />
                          </div>
                        </div>
                        <div>
                          <label className="mb-1 block text-xs font-medium text-mute">
                            {t('dealColumns.landedPrice')}
                          </label>
                          <div className="flex">
                            <span className="rounded-l-md border border-r-0 border-rule bg-paper px-3 py-2 text-sm text-mute">
                              $
                            </span>
                            <input
                              name="landedPrice"
                              type="number"
                              step="0.01"
                              defaultValue={opt?.landedPrice ?? localDeal.landedPrice ?? ''}
                              className="flex-1 rounded-r-md border border-rule px-3 py-2 text-sm focus:ring-2 focus:ring-accent focus:outline-none"
                            />
                          </div>
                        </div>
                        <div>
                          <label className="mb-1 block text-xs font-medium text-mute">
                            MOQ
                          </label>
                          <input
                            name="moq"
                            type="number"
                            defaultValue={qd?.moq ?? localDeal.moq ?? ''}
                            className="w-full rounded-md border border-rule px-3 py-2 text-sm focus:ring-2 focus:ring-accent focus:outline-none"
                          />
                        </div>
                        <div className="flex gap-2 pt-1">
                          <Button type="submit" size="sm" disabled={isSavingField}>
                            {isSavingField && (
                              <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                            )}
                            {t('dealRoom.save')}
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => setEditingField(null)}
                          >
                            {t('dealRoom.cancel')}
                          </Button>
                        </div>
                      </form>
                    </div>
                  )
                }

                return (
                  <div
                    className="group h-full cursor-pointer rounded-lg border border-rule bg-bone p-6 transition-colors hover:border-rule"
                    onClick={() => setEditingField('quote')}
                  >
                    <div className="mb-1 flex items-center justify-between">
                      <h3 className="title-block">
                        {t('dealRoom.pricing') || 'Pricing'}
                      </h3>
                      <Edit3 className="h-3.5 w-3.5 text-mute transition-colors group-hover:text-ink" />
                    </div>
                    <div className="mb-4 flex items-baseline justify-between">
                      <p className="text-xs text-mute">
                        {qd.productName || localDeal.dealName}
                      </p>
                      {qd.hsCode && (
                        <span className="text-xs text-mute">HS {qd.hsCode}</span>
                      )}
                    </div>
                    <div className="grid gap-4">
                      {qd.options.map((opt: any, i: number) => {
                        const currency = opt.currency || 'USD'
                        return (
                          <div
                            key={i}
                            className="overflow-hidden rounded-lg border border-rule"
                          >
                            <div className="border-b border-rule bg-paper px-4 py-3">
                              <span className="text-xs font-medium tracking-wider text-mute uppercase">
                                {opt.label}
                              </span>
                            </div>
                            <div className="px-4 py-4">
                              <div className="mb-1 flex items-baseline justify-between">
                                <span className="text-xs tracking-wider text-mute uppercase">
                                  Landed Price
                                </span>
                                <span className="text-xl font-semibold text-deep tabular-nums">
                                  {currency} {(opt.landedPrice ?? 0).toFixed(2)}
                                </span>
                              </div>
                              <div className="flex items-baseline justify-between">
                                <span className="text-xs tracking-wider text-mute uppercase">
                                  FOB
                                </span>
                                <span className="text-sm text-mute tabular-nums">
                                  {currency} {(opt.fobPrice ?? 0).toFixed(2)}
                                </span>
                              </div>
                              {qd.moq > 0 && (
                                <div className="mt-3 border-t border-rule pt-3 text-xs text-mute">
                                  MOQ: {(qd.moq ?? 0).toLocaleString()} units
                                </div>
                              )}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )
              })()}
            </div>
          </div>

          {/* Quote Requests */}
          {roomAnalytics?.quoteRequests?.length > 0 && (
            <div className="rounded-lg border border-rule bg-bone p-6">
              <h3 className="mb-4 title-block">
                {t('dealRoom.quoteRequests')}
              </h3>
              <div className="divide-y divide-rule">
                {roomAnalytics.quoteRequests.map((qr: any, idx: number) => (
                  <div key={idx} className="py-3 first:pt-0 last:pb-0">
                    <div className="mb-1 flex items-center justify-between">
                      <div>
                        <span className="text-sm font-medium text-ink">
                          {qr.buyerName || t('dealRoom.anonymous')}
                        </span>
                        {qr.buyerCompany && (
                          <span className="ml-2 text-xs text-mute">
                            {qr.buyerCompany}
                          </span>
                        )}
                      </div>
                      {qr.createdAt && (
                        <span className="text-xs text-mute">
                          {new Date(qr.createdAt).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                    {qr.buyerEmail && (
                      <p className="mb-1 text-xs text-mute">{qr.buyerEmail}</p>
                    )}
                    {qr.message && (
                      <p className="mb-1 text-sm text-mute">{qr.message}</p>
                    )}
                    {qr.preferredQuantity && (
                      <p className="text-xs text-mute">
                        {t('dealRoom.requestedQty')}: {qr.preferredQuantity}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Buyer Interest & Activity Timeline — full width, 50/50 */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {/* Buyer Interest — top sections by avg time per session */}
            {(() => {
              const views: any[] = roomAnalytics?.views || []
              if (views.length === 0) return null

              const sectionMap: Record<
                string,
                { totalSeconds: number; sessionCount: number }
              > = {}
              views.forEach((view: any) => {
                try {
                  const sections =
                    typeof view.sectionsViewed === 'string'
                      ? JSON.parse(view.sectionsViewed)
                      : view.sectionsViewed || []
                  sections.forEach((s: any) => {
                    const key = s.section
                    if (!sectionMap[key])
                      sectionMap[key] = { totalSeconds: 0, sessionCount: 0 }
                    sectionMap[key].totalSeconds += s.total_seconds || s.totalSeconds || 0
                    sectionMap[key].sessionCount += 1
                  })
                } catch {
                  /* ignore */
                }
              })

              const sorted = Object.entries(sectionMap)
                .map(([section, d]) => ({
                  section,
                  avg: Math.round(d.totalSeconds / d.sessionCount),
                }))
                .sort((a, b) => b.avg - a.avg)
                .slice(0, 3)

              if (sorted.length === 0) return null
              const maxAvg = sorted[0].avg || 1

              const sectionLabels: Record<string, string> = {
                header: t('dealRoom.sectionLabels.header'),
                quote: t('dealRoom.sectionLabels.quote'),
                landed_cost: t('dealRoom.sectionLabels.landedCost'),
                compliance: t('dealRoom.sectionLabels.compliance'),
                factory: t('dealRoom.sectionLabels.factory'),
                sample_timeline: t('dealRoom.sectionLabels.sampleTimeline'),
                message: t('dealRoom.sectionLabels.message'),
              }

              return (
                <div className="rounded-lg border border-rule bg-bone p-6">
                  <h3 className="mb-1 title-block">
                    {t('dealRoom.buyerInterest')}
                  </h3>
                  <p className="mb-4 text-xs text-mute">
                    {t('dealRoom.buyerInterestHint')}
                  </p>
                  <div className="space-y-3">
                    {sorted.map(({ section, avg }, idx) => {
                      const pct = Math.round((avg / maxAvg) * 100)
                      return (
                        <div key={section}>
                          <div className="mb-1 flex items-center justify-between">
                            <span className="text-sm text-ink">
                              {idx === 0 && (
                                <span className="mr-1.5 text-gold">●</span>
                              )}
                              {sectionLabels[section] || section}
                            </span>
                            <span className="text-xs text-mute">
                              {avg >= 60
                                ? t('dealRoom.timeMinutes', {
                                    min: Math.floor(avg / 60),
                                    sec: avg % 60,
                                  })
                                : t('dealRoom.timeSeconds', { sec: avg })}
                              <span className="ml-1 text-mute">
                                {t('dealRoom.perVisit')}
                              </span>
                            </span>
                          </div>
                          <div className="h-2 w-full rounded-full bg-cream">
                            <div
                              className={`h-2 rounded-full ${idx === 0 ? 'bg-gold' : 'bg-mute'}`}
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )
            })()}

            {/* Activity Timeline — grouped by visitor */}
            {(() => {
              const views: any[] = roomAnalytics?.views || []
              if (views.length === 0) return null

              const visitorMap: Record<
                string,
                {
                  email: string | null
                  visits: number
                  firstSeen: string
                  lastSeen: string
                  topSection: string
                }
              > = {}

              const sectionLabels: Record<string, string> = {
                header: t('dealRoom.sectionLabels.header'),
                quote: t('dealRoom.sectionLabels.quote'),
                landed_cost: t('dealRoom.sectionLabels.landedCost'),
                compliance: t('dealRoom.sectionLabels.compliance'),
                factory: t('dealRoom.sectionLabels.factory'),
                sample_timeline: t('dealRoom.sectionLabels.sampleTimeline'),
                message: t('dealRoom.sectionLabels.message'),
              }

              views.forEach((view: any) => {

                const vid = view.visitorId || 'unknown'
                if (!visitorMap[vid]) {
                  visitorMap[vid] = {
                    email: null,
                    visits: 0,
                    firstSeen: view.startedAt,
                    lastSeen: view.startedAt,
                    topSection: '',
                  }
                }
                const v = visitorMap[vid]
                v.visits += 1
                if (view.viewerEmail) v.email = view.viewerEmail
                if (view.startedAt < v.firstSeen) v.firstSeen = view.startedAt
                if (view.startedAt > v.lastSeen) v.lastSeen = view.startedAt
                try {
                  const sections =
                    typeof view.sectionsViewed === 'string'
                      ? JSON.parse(view.sectionsViewed)
                      : view.sectionsViewed || []
                  const longest = sections.reduce(
                    (max: any, s: any) => {
                      const sec = s.total_seconds || s.totalSeconds || 0
                      return sec > (max?.sec || 0) ? { section: s.section, sec } : max
                    },
                    { section: '', sec: 0 }
                  )
                  if (longest.sec > 0) v.topSection = longest.section
                } catch {
                  /* ignore */
                }
              })

              const visitors = Object.entries(visitorMap)
                .sort(
                  ([, a], [, b]) =>
                    new Date(b.lastSeen).getTime() - new Date(a.lastSeen).getTime()
                )
                .slice(0, 10)

              return (
                <div className="rounded-lg border border-rule bg-bone p-6">
                  <h3 className="mb-4 title-block">
                    {t('dealRoom.activityTimeline')}
                  </h3>
                  <div className="divide-y divide-rule">
                    {visitors.map(([vid, v]) => (
                      <div key={vid} className="py-3 first:pt-0 last:pb-0">
                        <div className="mb-1 flex items-center justify-between">
                          <span className="text-sm font-medium text-ink">
                            {v.email ||
                              (roomAnalytics?.targetBuyerName ? (
                                <>
                                  <span className="text-mute italic">
                                    {t('dealRoom.likelyVisitor')}:
                                  </span>{' '}
                                  {roomAnalytics.targetBuyerName}
                                </>
                              ) : (
                                t('dealRoom.anonymous')
                              ))}
                          </span>
                          <span className="text-xs font-medium text-mute">
                            {v.visits === 1
                              ? t('dealRoom.visitCount', { count: 1 })
                              : t('dealRoom.visitCount', { count: v.visits })}
                          </span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-mute">
                            {new Date(v.lastSeen).toLocaleDateString()}
                          </span>
                          {v.topSection && (
                            <span className="rounded bg-cream px-1.5 py-0.5 text-[10px] text-mute">
                              {t('dealRoom.mostViewed')}:{' '}
                              {sectionLabels[v.topSection] || v.topSection}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )
            })()}
          </div>
        </div>
        ) : draftOpen ? (
          /* Bilingual quote-confirmation email draft (post-create) */
          <div className="space-y-4">
            <div className="rounded-lg border border-rule bg-bone p-6">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="title-panel">
                  {t('dealRoom.draftEmailHeading')}
                </h3>
                {localDeal.clientEmail && (
                  <p className="text-sm text-mute">
                    {t('dealRoom.draftRecipientLabel')}:{' '}
                    <span className="font-mono text-ink">{localDeal.clientEmail}</span>
                  </p>
                )}
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                {(['zh', 'en'] as const).map((language) => {
                  const column = language === 'zh' ? draftZh : draftEn
                  const setColumn = language === 'zh' ? setDraftZh : setDraftEn
                  const heading =
                    language === 'zh'
                      ? t('dealRoom.columnHeadingZh')
                      : t('dealRoom.columnHeadingEn')
                  const copyLabel =
                    language === 'zh' ? t('dealRoom.copyZh') : t('dealRoom.copyEn')
                  return (
                    <div
                      key={language}
                      className="flex flex-col gap-3 rounded-md border border-rule bg-paper p-4"
                    >
                      <div className="flex items-center justify-between">
                        <h4 className="title-block">{heading}</h4>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          disabled={column.loading || (!column.subject && !column.body)}
                          onClick={() => handleCopyDraftColumn(language)}
                        >
                          <Copy className="h-3.5 w-3.5" />
                          <span className="ml-1.5">{copyLabel}</span>
                        </Button>
                      </div>

                      {column.loading ? (
                        <div className="flex items-center gap-2 py-8 text-sm text-mute">
                          <Loader2 className="h-4 w-4 animate-spin" />
                          {t('dealRoom.draftLoading')}
                        </div>
                      ) : column.error ? (
                        <div className="flex flex-col items-start gap-2 py-4 text-sm">
                          <div className="flex items-center gap-1.5 text-mute">
                            <AlertCircle className="h-4 w-4" />
                            {column.error}
                          </div>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() => generateDraft(language)}
                          >
                            <RefreshCw className="h-3.5 w-3.5" />
                            <span className="ml-1.5">{t('dealRoom.draftRetry')}</span>
                          </Button>
                        </div>
                      ) : (
                        <>
                          <div>
                            <label className="mb-1 block text-xs font-medium text-mute">
                              {t('dealRoom.draftSubject')}
                            </label>
                            <input
                              type="text"
                              value={column.subject}
                              onChange={(e) =>
                                setColumn((prev) => ({ ...prev, subject: e.target.value }))
                              }
                              className="w-full rounded-md border border-rule px-3 py-2 text-sm focus:border-accent focus:ring-2 focus:ring-accent focus:outline-none"
                            />
                          </div>
                          <div>
                            <label className="mb-1 block text-xs font-medium text-mute">
                              {t('dealRoom.draftBody')}
                            </label>
                            <textarea
                              value={column.body}
                              onChange={(e) =>
                                setColumn((prev) => ({ ...prev, body: e.target.value }))
                              }
                              rows={10}
                              className="w-full resize-y rounded-md border border-rule px-3 py-2 text-sm focus:border-accent focus:ring-2 focus:ring-accent focus:outline-none"
                            />
                          </div>
                        </>
                      )}
                    </div>
                  )
                })}
              </div>

              <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-4 text-sm">
                  <span className="text-mute">{t('dealRoom.draftLanguageLabel')}:</span>
                  <label className="inline-flex cursor-pointer items-center gap-1.5 text-deep">
                    <input
                      type="radio"
                      name="draft-send-language"
                      value="zh"
                      checked={sendLanguage === 'zh'}
                      onChange={() => setSendLanguage('zh')}
                      className="h-3.5 w-3.5 accent-accent"
                    />
                    {t('dealRoom.columnHeadingZh')}
                  </label>
                  <label className="inline-flex cursor-pointer items-center gap-1.5 text-deep">
                    <input
                      type="radio"
                      name="draft-send-language"
                      value="en"
                      checked={sendLanguage === 'en'}
                      onChange={() => setSendLanguage('en')}
                      className="h-3.5 w-3.5 accent-accent"
                    />
                    {t('dealRoom.columnHeadingEn')}
                  </label>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleCancelDraft}
                    disabled={isSendingDraft}
                  >
                    {t('dealRoom.cancelDraft')}
                  </Button>
                  <Button
                    type="button"
                    onClick={handleSendDraft}
                    disabled={
                      isSendingDraft ||
                      (sendLanguage === 'zh' ? draftZh : draftEn).loading ||
                      !!(sendLanguage === 'zh' ? draftZh : draftEn).error ||
                      !(sendLanguage === 'zh' ? draftZh : draftEn).subject.trim() ||
                      !(sendLanguage === 'zh' ? draftZh : draftEn).body.trim()
                    }
                  >
                    {isSendingDraft && (
                      <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                    )}
                    {isSendingDraft
                      ? t('dealRoom.draftSending')
                      : t('dealRoom.sendEmail')}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        ) : (
          /* Room exists, draft closed — minimal placeholder */
          <div className="rounded-lg border border-rule bg-bone p-6">
            <div className="flex flex-col items-center gap-4 py-8 text-center">
              <h3 className="title-panel">
                {t('dealRoom.roomCreatedPlaceholder')}
              </h3>
              <Button type="button" onClick={openBilingualDraft}>
                <RefreshCw className="mr-1.5 h-4 w-4" />
                {t('dealRoom.regenerateDraft')}
              </Button>
            </div>
          </div>
        )
      ) : (
        /* Deal room exists but missing pricing — show quote form */
        <div className="space-y-6">
          <div className="rounded-lg border border-rule bg-bone p-6">
            <div className="py-6 text-center">
              <DoorOpen className="mx-auto mb-3 h-10 w-10 text-mute" />
              <h3 className="mb-6 title-panel">
                {t('dealRoom.noDealRoomYet')}
              </h3>

              <div className="mx-auto max-w-md space-y-6 text-left">
                {/* Pricing form */}
                <div className="space-y-3">
                  <h4 className="title-block">
                    {t('dealRoom.pricingDetails')}
                  </h4>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-mute">
                      {t('dealRoom.productName')}
                    </label>
                    <input
                      type="text"
                      value={roomForm.productName}
                      onChange={(e) =>
                        setRoomForm({ ...roomForm, productName: e.target.value })
                      }
                      placeholder={localDeal.dealName || ''}
                      className="w-full rounded-md border border-rule px-3 py-2 text-sm focus:border-accent focus:ring-2 focus:ring-accent focus:outline-none"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="mb-1 block text-xs font-medium text-mute">
                        {t('dealRoom.fobPrice')} *
                      </label>
                      <div className="flex">
                        <select
                          value={roomForm.currency}
                          onChange={(e) =>
                            setRoomForm({ ...roomForm, currency: e.target.value })
                          }
                          className="rounded-l-md border border-r-0 border-rule bg-paper px-2 py-2 text-sm text-mute focus:outline-none"
                        >
                          <option value="USD">$</option>
                          <option value="EUR">€</option>
                          <option value="CNY">¥</option>
                        </select>
                        <input
                          type="number"
                          step="0.01"
                          value={roomForm.fobPrice}
                          onChange={(e) =>
                            setRoomForm({ ...roomForm, fobPrice: e.target.value })
                          }
                          placeholder="4.85"
                          className="flex-1 rounded-r-md border border-rule px-3 py-2 text-sm focus:border-accent focus:ring-2 focus:ring-accent focus:outline-none"
                        />
                      </div>
                    </div>
                    <div>
                      <label className="mb-1 block text-xs font-medium text-mute">
                        {t('dealColumns.landedPrice')}
                      </label>
                      <div className="flex">
                        <span className="rounded-l-md border border-r-0 border-rule bg-paper px-2 py-2 text-sm text-mute">
                          {roomForm.currency === 'USD'
                            ? '$'
                            : roomForm.currency === 'EUR'
                              ? '€'
                              : '¥'}
                        </span>
                        <input
                          type="number"
                          step="0.01"
                          value={roomForm.landedPrice}
                          onChange={(e) =>
                            setRoomForm({ ...roomForm, landedPrice: e.target.value })
                          }
                          placeholder="6.50"
                          className="flex-1 rounded-r-md border border-rule px-3 py-2 text-sm focus:border-accent focus:ring-2 focus:ring-accent focus:outline-none"
                        />
                      </div>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="mb-1 block text-xs font-medium text-mute">
                        {t('dealRoom.moqLabel')}
                      </label>
                      <input
                        type="number"
                        value={roomForm.moq}
                        onChange={(e) => setRoomForm({ ...roomForm, moq: e.target.value })}
                        placeholder="5000"
                        className="w-full rounded-md border border-rule px-3 py-2 text-sm focus:border-accent focus:ring-2 focus:ring-accent focus:outline-none"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-mute">
                      {t('dealRoom.leadTime')}
                    </label>
                    <input
                      type="text"
                      value={roomForm.leadTimeDays}
                      onChange={(e) =>
                        setRoomForm({ ...roomForm, leadTimeDays: e.target.value })
                      }
                      placeholder="30-45"
                      className="w-full rounded-md border border-rule px-3 py-2 text-sm focus:border-accent focus:ring-2 focus:ring-accent focus:outline-none"
                    />
                  </div>
                </div>

                {/* Custom Message */}
                <div className="space-y-3">
                  <h4 className="title-block">
                    {t('dealRoom.customMessage')}
                  </h4>
                  <div>
                    <textarea
                      value={roomForm.customMessageZh}
                      onChange={(e) =>
                        setRoomForm({ ...roomForm, customMessageZh: e.target.value })
                      }
                      placeholder={t('dealRoom.customMessage')}
                      rows={3}
                      className="w-full resize-none rounded-md border border-rule px-3 py-2 text-sm focus:border-accent focus:ring-2 focus:ring-accent focus:outline-none"
                    />
                  </div>
                  {roomForm.customMessageZh && (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={isTranslating}
                      onClick={async () => {
                        if (!localDeal?.dealId) return
                        setIsTranslating(true)
                        try {
                          const resp = await crmApiClient.post<{
                            success: boolean
                            messageEn: string
                          }>(`/deals/${localDeal.dealId}/room/translate-message`, {
                            messageZh: roomForm.customMessageZh,
                          })
                          setRoomForm((prev) => ({
                            ...prev,
                            customMessageEn: resp.messageEn,
                          }))
                        } catch {
                          toast.error(t('toasts.error'))
                        } finally {
                          setIsTranslating(false)
                        }
                      }}
                    >
                      {isTranslating ? (
                        <>
                          <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                          {t('dealRoom.translating')}
                        </>
                      ) : (
                        t('dealRoom.translateToEnglish')
                      )}
                    </Button>
                  )}
                  {roomForm.customMessageEn && (
                    <div>
                      <label className="mb-1 block text-xs font-medium text-mute">
                        {t('dealRoom.englishPreview')}
                      </label>
                      <div className="w-full rounded-md border border-rule bg-paper px-3 py-2 text-sm whitespace-pre-wrap text-mute">
                        {roomForm.customMessageEn}
                      </div>
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-3">
                  <Button
                    onClick={handleCreateDealRoom}
                    disabled={isCreatingRoom || !roomForm.fobPrice}
                  >
                    {isCreatingRoom && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
                    {isCreatingRoom ? t('dealRoom.creating') : t('dealRoom.createDealRoom')}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default DealRoomTab
