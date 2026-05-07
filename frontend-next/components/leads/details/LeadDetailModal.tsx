'use client'

import React, { useState, useEffect } from 'react'
import {
  User,
  Mail,
  Loader2,
  AlertCircle,
  Check as CheckIcon,
  X as XIcon,
  Phone,
  Linkedin,
  Ship,
  MapPin,
  ArrowUp,
  ArrowDown,
  Lightbulb,
} from 'lucide-react'
import { PageLoader } from '@/components/ui/page-loader'
import LeadEmailComposer from '../email/LeadEmailComposer'
import BuyerSupplierInfo from './BuyerSupplierInfo'
import BuyerImportProfile from './BuyerImportProfile'
import BuyerOrderTiming from './BuyerOrderTiming'
import BuyerCompetitorExposure from './BuyerCompetitorExposure'
import BuyerScoreCard from './BuyerScoreCard'
import BuyerKpiStrip from './BuyerKpiStrip'
import ShipmentsPanel from './ShipmentsPanel'
import leadsApiService from '@/lib/api/leads'
import { useSubscription } from '@/stores/subscriptionStore'
import { toast } from 'sonner'
import { useTranslations } from 'next-intl'

import type { Lead, Personnel } from '@/types/leads'

interface LeadDetailPageProps {
  leadId: string
  initialTab?: string
}

const LeadDetailPage: React.FC<LeadDetailPageProps> = ({
  leadId,
  initialTab = 'overview',
}) => {
  const { entitlements } = useSubscription()
  const showBuyerEmails = entitlements.showBuyerEmails
  const t = useTranslations('leads')

  // Loading and error state
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Local lead state
  const [localLead, setLocalLead] = useState<Lead | null>(null)

  // Tab state
  const [modalActiveTab, setModalActiveTab] = useState(initialTab)

  // BoL timing data
  const [timingData, setTimingData] = useState<{
    daysSinceLastShipment?: number
    avgOrderCycleDays?: number
    cyclePct?: number
    reorderWindow?: 'now' | 'approaching' | 'early'
  } | null>(null)

  // Inline editing state
  const [editingField, setEditingField] = useState<string | null>(null)
  const [editingValue, setEditingValue] = useState('')
  const [isSavingField, setIsSavingField] = useState(false)

  const [personnelExpanded, setPersonnelExpanded] = useState(false)

  // Sync tab state when initialTab prop changes
  useEffect(() => {
    setModalActiveTab(initialTab)
  }, [initialTab])

  // Fetch lead data on mount
  useEffect(() => {
    const fetchLead = async () => {
      if (!leadId) {
        setError(t('leadModal.noIdProvided'))
        setIsLoading(false)
        return
      }
      try {
        setIsLoading(true)
        setError(null)
        const lead = await leadsApiService.getLeadById(leadId)
        if (lead) {
          setLocalLead(lead)
        } else {
          setError(t('leadModal.notFound'))
        }
      } catch (err) {
        console.error('Error fetching lead:', err)
        setError(t('leadModal.loadFailed'))
      } finally {
        setIsLoading(false)
      }
    }
    fetchLead()
  }, [leadId])

  // Fetch BoL timing data
  useEffect(() => {
    if (!leadId) return
    let cancelled = false
    const fetchTiming = async () => {
      try {
        const data = await leadsApiService.getBolIntelligence(leadId)
        if (!cancelled && data?.intelligence?.timing) {
          setTimingData(data.intelligence.timing)
        }
      } catch {
        // Silently fail — timing data is optional
      }
    }
    fetchTiming()
    return () => {
      cancelled = true
    }
  }, [leadId])

  // Handle email sent
  const handleEmailSent = async () => {
    if (leadId) {
      const updatedLead = await leadsApiService.getLeadById(leadId)
      if (updatedLead) {
        setLocalLead(updatedLead)
      }
    }
  }

  // Inline editing handlers
  const handleFieldClick = (fieldName: string, currentValue: string | null | undefined) => {
    setEditingField(fieldName)
    setEditingValue(currentValue || '')
  }

  const handleFieldCancel = () => {
    setEditingField(null)
    setEditingValue('')
  }

  const handleFieldSave = async (fieldName: string) => {
    const leadIdValue = localLead?.leadId || localLead?.id
    if (!leadIdValue) return

    setIsSavingField(true)
    try {
      const fieldMapping: Record<string, string> = {
        company: 'company',
        industry: 'industry',
        location: 'location',
        website: 'website',
      }
      const backendField = fieldMapping[fieldName]
      if (!backendField) return

      const payload = { [backendField]: editingValue || null }
      const updatedLead: Lead = await leadsApiService.updateLead(String(leadIdValue), payload)
      setLocalLead(updatedLead)
      setEditingField(null)
      setEditingValue('')
      toast(t('toasts.success'), { description: t('leadModal.fieldUpdated') })
    } catch (error) {
      console.error('Error updating field:', error)
      toast.error(t('toasts.error'), { description: t('leadModal.fieldUpdateFailed') })
    } finally {
      setIsSavingField(false)
    }
  }

  // Render editable field
  const renderEditableField = (
    fieldName: string,
    displayValue: string | null | undefined,
    placeholder = ''
  ) => {
    const isEditing = editingField === fieldName

    if (isEditing) {
      return (
        <div className="relative">
          <input
            type="text"
            value={editingValue}
            onChange={(e) => setEditingValue(e.target.value)}
            onBlur={() => !isSavingField && handleFieldSave(fieldName)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleFieldSave(fieldName)
              else if (e.key === 'Escape') handleFieldCancel()
            }}
            className="w-full rounded border border-rule px-2 py-1 pr-16 text-sm focus:ring-2 focus:border-accent focus:outline-none"
            autoFocus
            disabled={isSavingField}
            placeholder={placeholder}
          />
          <div className="absolute top-1/2 right-2 flex -translate-y-1/2 items-center gap-1">
            {isSavingField ? (
              <Loader2 className="h-4 w-4 animate-spin text-mute" />
            ) : (
              <>
                <button
                  onMouseDown={(e) => {
                    e.preventDefault()
                    handleFieldSave(fieldName)
                  }}
                  className="rounded p-1 text-accent transition-colors hover:bg-accent-lo hover:text-accent"
                >
                  <CheckIcon className="h-3.5 w-3.5" />
                </button>
                <button
                  onMouseDown={(e) => {
                    e.preventDefault()
                    handleFieldCancel()
                  }}
                  className="rounded p-1 text-mute transition-colors hover:bg-cream hover:text-ink"
                >
                  <XIcon className="h-3.5 w-3.5" />
                </button>
              </>
            )}
          </div>
        </div>
      )
    }

    return (
      <div
        onClick={() => handleFieldClick(fieldName, displayValue || '')}
        className="cursor-pointer rounded border border-transparent px-2 py-1 text-sm text-ink transition-all hover:border-rule hover:bg-cream"
      >
        {displayValue || <span className="text-mute italic">{placeholder}</span>}
      </div>
    )
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="flex h-full min-h-[400px] items-center justify-center">
        <PageLoader label={t('leadModal.loading')} />
      </div>
    )
  }

  // Error state
  if (error || !localLead) {
    return (
      <div className="flex h-full min-h-[400px] items-center justify-center">
        <div className="text-center">
          <AlertCircle className="mx-auto mb-3 h-8 w-8 text-threat" />
          <p className="font-medium text-ink">{error || t('leadModal.notFound')}</p>
        </div>
      </div>
    )
  }

  const isBoLLead = localLead.source === 'importyeti'
  const aiActionBrief = localLead.bolDetailContext?.aiActionBrief
  const growth12mPct = localLead.bolDetailContext?.growth12mPct ?? null
  const chinaConcentration = localLead.bolDetailContext?.chinaConcentration ?? null
  const totalShipmentsCount = localLead.importContext?.totalShipments ?? 0
  const supplierCount =
    localLead.importContext?.totalSuppliers ??
    (localLead.supplierContext?.suppliers?.length ?? null)

  // First shipment date — derive from earliest timeSeries key (dd/mm/yyyy).
  const firstShipmentLabel = (() => {
    const ts = localLead.bolDetailContext?.timeSeries
    if (!ts) return null
    const keys = Object.keys(ts).sort((a, b) => {
      const pa = a.split('/').map(Number)
      const pb = b.split('/').map(Number)
      return (
        new Date(pa[2], pa[1] - 1, pa[0]).getTime() -
        new Date(pb[2], pb[1] - 1, pb[0]).getTime()
      )
    })
    const first = keys[0]
    if (!first) return null
    const [dd, mm, yyyy] = first.split('/').map(Number)
    return new Date(yyyy, mm - 1, dd).toLocaleDateString('en-US', {
      month: 'short',
      year: 'numeric',
    })
  })()

  const lastShipmentLabel = (() => {
    const raw = localLead.importContext?.mostRecentShipment
    if (!raw) return null
    const [dd, mm, yyyy] = raw.split('/').map(Number)
    if (!dd || !mm || !yyyy) return null
    return new Date(yyyy, mm - 1, dd).toLocaleDateString('en-US', {
      month: 'short',
      day: '2-digit',
      year: 'numeric',
    })
  })()

  return (
    <>
      <div className="flex h-full flex-col">
        {/* Header — company name + sub-meta strip */}
        <div className="flex-shrink-0 px-6 pt-5 pb-3">
          <h2 className="title-page">{localLead.company}</h2>
          <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-mute">
            {localLead.location && (
              <span className="inline-flex items-center gap-1">
                <MapPin className="h-3.5 w-3.5" />
                {localLead.location}
              </span>
            )}
            {localLead.score != null && (
              <span className="inline-flex items-center gap-1">
                <span className="font-medium text-ink">{t('buyerDetail.scoreLabel')}</span>
                <span className="font-mono tabular-nums">{localLead.score}</span>
              </span>
            )}
            {growth12mPct != null && (
              <span className="inline-flex items-center gap-1">
                <span className="font-medium text-ink">{t('buyerDetail.trendLabel')}</span>
                <span
                  className={`inline-flex items-center gap-0.5 tabular-nums ${
                    growth12mPct > 0
                      ? 'text-accent'
                      : growth12mPct < 0
                        ? 'text-mute'
                        : 'text-mute'
                  }`}
                >
                  {growth12mPct > 0 ? (
                    <ArrowUp className="h-3 w-3" />
                  ) : growth12mPct < 0 ? (
                    <ArrowDown className="h-3 w-3" />
                  ) : null}
                  {growth12mPct > 0 ? '+' : ''}
                  {growth12mPct.toFixed(1)}%
                </span>
              </span>
            )}
          </div>
        </div>

        {/* Navigation Tabs — underline style */}
        <div className="flex-shrink-0 border-b border-rule px-6">
          <div className="flex gap-4">
            {[
              { key: 'overview', icon: User, label: t('leadModal.overview') },
              { key: 'shipments', icon: Ship, label: t('buyerDetail.shipmentsTab') },
              { key: 'email', icon: Mail, label: t('leadModal.outreach') },
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setModalActiveTab(tab.key)}
                className={`flex items-center gap-2 border-b-2 pb-3 text-sm font-medium transition-colors ${
                  modalActiveTab === tab.key
                    ? 'border-deep text-deep'
                    : 'border-transparent text-mute hover:text-ink'
                }`}
              >
                <tab.icon className="h-4 w-4" />
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto bg-paper">
          {/* Overview Tab */}
          {modalActiveTab === 'overview' && (
            <div className="grid grid-cols-1 gap-4 p-5 lg:grid-cols-10">
              {/* Left Column — Stacked cards */}
              <div className="space-y-4 lg:col-span-7">
                {/* AI Insight Banner — design's banner-ai: lede + derived evidence line */}
                {isBoLLead && aiActionBrief && (
                  <div className="rounded-lg border border-gold/30 bg-gold-lo/40 px-4 py-3">
                    <div className="flex items-start gap-3">
                      <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-gold" />
                      <div>
                        <p className="font-display text-base leading-snug text-ink">
                          {aiActionBrief}
                        </p>
                        {(growth12mPct != null ||
                          chinaConcentration != null ||
                          supplierCount != null) && (
                          <p className="mt-1 text-[11px] tabular-nums text-mute">
                            {t('buyerDetail.aiEvidenceLine', {
                              growth:
                                growth12mPct != null
                                  ? `${growth12mPct > 0 ? '+' : ''}${growth12mPct.toFixed(0)}`
                                  : '—',
                              china:
                                chinaConcentration != null
                                  ? chinaConcentration.toFixed(1)
                                  : '—',
                              suppliers: supplierCount ?? '—',
                            })}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {/* Order Timing — bare editorial section (no card) */}
                {timingData?.avgOrderCycleDays != null && (
                  <section>
                    <h3 className="mb-3 title-panel">
                      {t('leadModal.orderTiming')}
                    </h3>
                    <BuyerOrderTiming
                      importContext={localLead.importContext ?? null}
                      timingData={timingData}
                    />
                  </section>
                )}

                {/* KPI strip — hoisted from BuyerSupplierInfo */}
                <BuyerKpiStrip
                  supplierCount={supplierCount}
                  chinaConcentration={chinaConcentration}
                  growth12mPct={growth12mPct}
                  totalShipments={totalShipmentsCount > 0 ? totalShipmentsCount : null}
                />

                {/* Split-2: Supplier share + Import trend — boxed panels per design */}
                <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                  <section className="rounded-lg border border-rule bg-paper p-5">
                    <span className="mb-4 inline-block font-mono text-[11px] uppercase tracking-[0.1em] text-mute">
                      {t('leadModal.supplierInfo')}
                    </span>
                    <BuyerSupplierInfo
                      importContext={localLead.importContext ?? null}
                      supplierContext={localLead.supplierContext ?? null}
                    />
                  </section>
                  <section className="rounded-lg border border-rule bg-paper p-5">
                    <span className="mb-4 inline-block font-mono text-[11px] uppercase tracking-[0.1em] text-mute">
                      {t('leadModal.importProfile')}
                    </span>
                    <BuyerImportProfile
                      importContext={localLead.importContext ?? null}
                      bolDetailContext={localLead.bolDetailContext ?? null}
                    />
                  </section>
                </div>

                {/* Competitor Overlap — bare section, no card wrapper (design's overlap-section) */}
                <BuyerCompetitorExposure leadId={String(localLead.leadId || localLead.id)} />

                {/* View shipments link */}
                {totalShipmentsCount > 0 && (
                  <div className="flex justify-end">
                    <button
                      type="button"
                      onClick={() => setModalActiveTab('shipments')}
                      className="inline-flex items-center gap-1 text-xs text-mute transition-colors hover:text-ink"
                    >
                      {t('buyerDetail.viewShipmentsLink', {
                        count: totalShipmentsCount.toLocaleString(),
                      })}
                    </button>
                  </div>
                )}
              </div>

              {/* Right Rail — combined panel per design `.ov-rail` (single card, divided sections) */}
              <div className="lg:col-span-3">
                <div className="divide-y divide-rule rounded-lg border border-rule bg-bone px-5">
                  {/* Score */}
                  <section className="flex flex-col gap-2 py-5">
                    <h4 className="font-mono text-[11px] tracking-[0.1em] text-mute uppercase">
                      {t('buyerDetail.score')}
                    </h4>
                    <BuyerScoreCard
                      score={localLead.score}
                      bolDetailContext={localLead.bolDetailContext ?? null}
                    />
                  </section>

                  {/* Buyer Info */}
                  <section className="flex flex-col gap-3 py-5">
                    <h4 className="font-mono text-[11px] tracking-[0.1em] text-mute uppercase">
                      {t('leadModal.leadInfo')}
                    </h4>
                    <dl className="divide-y divide-rule">
                      <RailMetaRow label={t('leadForm.company')}>
                        {renderEditableField(
                          'company',
                          localLead.company,
                          t('leadForm.companyPlaceholder'),
                        )}
                      </RailMetaRow>
                      <RailMetaRow label={t('buyerDetail.buyerMetaAddress')}>
                        {renderEditableField(
                          'location',
                          localLead.location,
                          t('leadForm.locationPlaceholder'),
                        )}
                      </RailMetaRow>
                      {totalShipmentsCount > 0 && (
                        <RailMetaRow label={t('buyerDetail.buyerMetaTotal')}>
                          <span className="text-sm tabular-nums text-ink">
                            {totalShipmentsCount.toLocaleString()}
                          </span>
                        </RailMetaRow>
                      )}
                      {firstShipmentLabel && (
                        <RailMetaRow label={t('buyerDetail.firstShipment')}>
                          <span className="text-sm text-ink">{firstShipmentLabel}</span>
                        </RailMetaRow>
                      )}
                      {lastShipmentLabel && (
                        <RailMetaRow label={t('buyerDetail.mostRecentShipment')}>
                          <span className="text-sm text-ink">{lastShipmentLabel}</span>
                        </RailMetaRow>
                      )}
                      {localLead.website && (
                        <RailMetaRow label={t('leadForm.website')}>
                          <a
                            href={
                              localLead.website.startsWith('http')
                                ? localLead.website
                                : `https://${localLead.website}`
                            }
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm text-ink hover:underline"
                          >
                            {localLead.website}
                          </a>
                        </RailMetaRow>
                      )}
                    </dl>
                  </section>

                  {/* Context chips — products + ports */}
                  {((localLead.importContext?.topProducts?.length ?? 0) > 0 ||
                    (localLead.importContext?.topPorts?.length ?? 0) > 0) && (
                    <section className="flex flex-col gap-2.5 py-5">
                      {(localLead.importContext?.topProducts?.length ?? 0) > 0 && (
                        <div className="flex items-start gap-3">
                          <span className="mt-0.5 w-8 shrink-0 text-[11px] tracking-wide text-mute">
                            {t('buyerDetail.contextLabelProducts')}
                          </span>
                          <div className="flex flex-wrap gap-1.5">
                            {(localLead.importContext?.topProducts ?? [])
                              .slice(0, 5)
                              .map((p, i) => (
                                <span
                                  key={`${i}-${p}`}
                                  title={p}
                                  className="inline-flex items-center rounded-full bg-cream px-2 py-0.5 text-[11px] text-ink"
                                >
                                  {p.length > 36 ? `${p.slice(0, 36)}…` : p}
                                </span>
                              ))}
                          </div>
                        </div>
                      )}
                      {(localLead.importContext?.topPorts?.length ?? 0) > 0 && (
                        <div className="flex items-start gap-3">
                          <span className="mt-0.5 w-8 shrink-0 text-[11px] tracking-wide text-mute">
                            {t('buyerDetail.contextLabelPorts')}
                          </span>
                          <div className="flex flex-wrap gap-1.5">
                            {(localLead.importContext?.topPorts ?? []).slice(0, 4).map((p, i) => (
                              <span
                                key={`${i}-${p}`}
                                className="inline-flex items-center rounded-full bg-cream px-2 py-0.5 font-mono text-[11px] text-ink"
                              >
                                {p}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </section>
                  )}

                  {/* Personnel */}
                  {localLead.personnel && localLead.personnel.length > 0 && (
                    <section className="flex flex-col gap-3 py-5">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-[11px] tracking-[0.1em] text-mute uppercase">
                          {t('leadModal.personnel', { count: localLead.personnel.length })}
                        </span>
                        {localLead.personnel.length > 1 && (
                          <button
                            onClick={() => setPersonnelExpanded(!personnelExpanded)}
                            className="text-xs text-mute hover:text-ink"
                          >
                            {personnelExpanded ? t('leadModal.showLess') : t('leadModal.viewAll')}
                          </button>
                        )}
                      </div>
                      <div className="space-y-4">
                        <RailContact person={localLead.personnel[0]} showEmail={showBuyerEmails} />
                        {personnelExpanded &&
                          localLead.personnel
                            .slice(1)
                            .map((person, i) => (
                              <RailContact key={i} person={person} showEmail={showBuyerEmails} />
                            ))}
                      </div>
                    </section>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Shipments Tab */}
          {modalActiveTab === 'shipments' && (
            <ShipmentsPanel
              leadId={String(localLead.leadId || localLead.id)}
              bolDetailContext={localLead.bolDetailContext ?? null}
            />
          )}

          {/* Email Tab */}
          {modalActiveTab === 'email' && (
            <div className="h-full">
              {localLead && (
                <LeadEmailComposer
                  lead={localLead}
                  onClose={() => setModalActiveTab('overview')}
                  embedded={true}
                  onEmailSent={async () => {
                    await handleEmailSent()
                    toast(t('toasts.success'), { description: t('leadModal.emailSent') })
                    setModalActiveTab('overview')
                  }}
                />
              )}
            </div>
          )}
        </div>

      </div>

    </>
  )
}

/** Horizontal dt/dd row matching the design's `.rail-meta-row`. */
function RailMetaRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2 first:pt-0 last:pb-0">
      <dt className="shrink-0 text-[11px] tracking-wide text-mute">{label}</dt>
      <dd className="min-w-0 text-right">{children}</dd>
    </div>
  )
}

/** Contact card matching the design's `.rail-contact` block:
 * initials avatar + name/title head + mail/phone lines with icons. */
function RailContact({
  person,
  showEmail,
}: {
  person: Personnel
  showEmail: boolean
}) {
  const name = person.fullName || person.name || ''
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? '')
    .join('')

  return (
    <div>
      <div className="flex items-center gap-3">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-cream font-mono text-xs font-medium text-ink">
          {initials || '?'}
        </span>
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-ink">{name || '—'}</div>
          {person.position && (
            <div className="truncate text-[11px] text-mute">{person.position}</div>
          )}
        </div>
      </div>
      <ul className="mt-2 space-y-1">
        {showEmail && person.email && (
          <li className="flex items-center gap-1.5 text-[11px] text-mute">
            <Mail className="h-3 w-3 shrink-0" />
            <span className="truncate font-mono">{person.email}</span>
          </li>
        )}
        {person.phone && (
          <li className="flex items-center gap-1.5 text-[11px] text-mute">
            <Phone className="h-3 w-3 shrink-0" />
            <span className="truncate font-mono">{person.phone}</span>
          </li>
        )}
        {person.linkedinUrl && (
          <li>
            <a
              href={person.linkedinUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-[11px] text-mute hover:underline"
            >
              <Linkedin className="h-3 w-3 shrink-0" />
              LinkedIn
            </a>
          </li>
        )}
      </ul>
    </div>
  )
}

export default LeadDetailPage
