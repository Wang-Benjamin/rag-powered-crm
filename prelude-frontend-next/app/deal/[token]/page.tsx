'use client'

import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams } from 'next/navigation'
import { ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'
import { PageLoader } from '@/components/ui/page-loader'
import type { PublicQuoteOption, PublicQuoteData } from '@/types/deal-room'

// ============================================================
// TYPES
// ============================================================

type QuoteOption = PublicQuoteOption
type QuoteData = PublicQuoteData

interface SampleTimeline {
  goldenSampleDays?: number
  approvalWorkflow?: boolean
  productionStartAfterApproval?: boolean
  notes?: string
}

interface RoomSettings {
  showCompliance?: boolean
  showFactory?: boolean
  showSampleTimeline?: boolean
  emailGate?: boolean
  customMessageZh?: string
  customMessageEn?: string
}

interface CompanyProfile {
  companyNameEn?: string
  companyNameZh?: string
  location?: string
  locationCoordinates?: { lat: number; lng: number }
  productDescriptionEn?: string
  logoUrl?: string
  insurance?: {
    type: string
    coverageAmount: string
    insurer: string
    policyExpiry: string
  }
}

interface FactoryDetails {
  capacity?: string
  leadTime?: string
  rushLeadTime?: string
  moq?: number
  yearEstablished?: number
  employees?: number
  photoUrls?: string[]
  videoTourUrl?: string
}

interface Certification {
  certType: string
  certNumber?: string
  issuingBody?: string
  issueDate?: string
  expiryDate?: string
  status: string
  documentUrl?: string
}

interface DealRoomData {
  deal: {
    dealId: number
    dealName: string
    quoteData: QuoteData
    sampleTimeline: SampleTimeline
    roomSettings: RoomSettings
    roomStatus: string
    valueUsd: number | null
    viewCount: number
  }
  buyer: { clientName: string }
  factory: {
    companyProfile: CompanyProfile
    factoryDetails: FactoryDetails
  }
  certifications: Certification[]
}

// ============================================================
// VIEW TRACKING
// ============================================================

function useViewTracking(token: string, dataLoaded: boolean, viewerEmail?: string) {
  const sectionsRef = useRef<Map<string, { totalMs: number; revisits: number }>>(new Map())
  const visibleSectionsRef = useRef<Map<string, number>>(new Map()) // section -> intersectionRatio
  const activeSectionRef = useRef<string | null>(null)
  const activeSectionStartRef = useRef<number | null>(null)
  const tabVisibleRef = useRef(true)
  const sessionTokenRef = useRef<string>('')
  const visitorIdRef = useRef<string>('')
  const viewerEmailRef = useRef<string | undefined>(viewerEmail)

  useEffect(() => {
    viewerEmailRef.current = viewerEmail
  }, [viewerEmail])

  useEffect(() => {
    if (!dataLoaded) return

    const existingVid = document.cookie.match(/(?:^|; )_vid=([^;]*)/)?.[1]
    if (existingVid) {
      visitorIdRef.current = existingVid
    } else {
      const vid = crypto.randomUUID()
      visitorIdRef.current = vid
      document.cookie = `_vid=${vid}; max-age=63072000; path=/; SameSite=Lax`
    }

    sessionTokenRef.current = crypto.randomUUID()

    // Close timer on the current active section (flush accumulated ms)
    const closeActiveSection = () => {
      const active = activeSectionRef.current
      if (active && activeSectionStartRef.current) {
        const elapsed = Date.now() - activeSectionStartRef.current
        const data = sectionsRef.current.get(active)
        if (data) data.totalMs += elapsed
        activeSectionStartRef.current = null
      }
    }

    // Determine the dominant (highest intersection ratio) section and switch to it
    const updateDominantSection = () => {
      if (!tabVisibleRef.current) return

      let bestSection: string | null = null
      let bestRatio = 0
      visibleSectionsRef.current.forEach((ratio, section) => {
        if (ratio > bestRatio) {
          bestRatio = ratio
          bestSection = section
        }
      })

      if (bestSection === activeSectionRef.current) return

      // Close old section
      closeActiveSection()
      if (activeSectionRef.current) {
        const oldData = sectionsRef.current.get(activeSectionRef.current)
        if (oldData) oldData.revisits += 1
      }

      // Start new section
      activeSectionRef.current = bestSection
      if (bestSection) {
        if (!sectionsRef.current.has(bestSection)) {
          sectionsRef.current.set(bestSection, { totalMs: 0, revisits: 0 })
        }
        activeSectionStartRef.current = Date.now()
      }
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const section = (entry.target as HTMLElement).dataset.section
          if (!section) return
          if (entry.isIntersecting) {
            visibleSectionsRef.current.set(section, entry.intersectionRatio)
          } else {
            visibleSectionsRef.current.delete(section)
          }
        })
        updateDominantSection()
      },
      { threshold: [0, 0.25, 0.5, 0.75, 1.0] }
    )

    document.querySelectorAll('[data-section]').forEach((el) => observer.observe(el))

    // Pause/resume tracking when tab visibility changes
    const handleVisibilityChange = () => {
      if (document.hidden) {
        tabVisibleRef.current = false
        closeActiveSection()
      } else {
        tabVisibleRef.current = true
        if (activeSectionRef.current) {
          activeSectionStartRef.current = Date.now()
        }
      }
    }
    document.addEventListener('visibilitychange', handleVisibilityChange)

    const buildPayload = () => {
      const sections: { section: string; totalSeconds: number; revisits: number }[] = []
      sectionsRef.current.forEach((data, section) => {
        let totalMs = data.totalMs
        // Add in-progress time for the currently active section
        if (
          section === activeSectionRef.current &&
          activeSectionStartRef.current &&
          tabVisibleRef.current
        ) {
          totalMs += Date.now() - activeSectionStartRef.current
        }
        sections.push({
          section,
          totalSeconds: Math.round(totalMs / 1000),
          revisits: data.revisits,
        })
      })
      return {
        visitor_id: visitorIdRef.current,
        session_token: sessionTokenRef.current,
        duration_seconds: Math.round((Date.now() - startTime) / 1000),
        sections_viewed: sections,
        viewer_email: viewerEmailRef.current || undefined,
      }
    }

    const startTime = Date.now()

    const heartbeat = setInterval(() => {
      fetch(`/api/deal/${token}/track`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildPayload()),
      }).catch(() => {})
    }, 30000)

    const handleUnload = () => {
      navigator.sendBeacon(`/api/deal/${token}/track`, JSON.stringify(buildPayload()))
    }
    window.addEventListener('beforeunload', handleUnload)

    const initialTimer = setTimeout(() => {
      fetch(`/api/deal/${token}/track`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildPayload()),
      }).catch(() => {})
    }, 2000)

    return () => {
      observer.disconnect()
      clearInterval(heartbeat)
      clearTimeout(initialTimer)
      window.removeEventListener('beforeunload', handleUnload)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [token, dataLoaded])
}

// ============================================================
// MESSAGE MODAL
// ============================================================

function MessageModal({
  token,
  companyName,
  onClose,
}: {
  token: string
  companyName: string
  onClose: () => void
}) {
  const [form, setForm] = useState({
    buyerEmail: '',
    buyerName: '',
    buyerCompany: '',
    message: '',
    preferredQuantity: '',
  })
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.buyerEmail) return
    setSending(true)
    try {
      const res = await fetch(`/api/deal/${token}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          buyer_email: form.buyerEmail,
          buyer_name: form.buyerName,
          buyer_company: form.buyerCompany,
          message: form.message,
          preferred_quantity: form.preferredQuantity ? parseInt(form.preferredQuantity) : null,
        }),
      })
      if (!res.ok) throw new Error('Server error')
      setSent(true)
    } catch {
      // Deal Room is English-only for external buyers (outside i18n provider tree)
      toast.error('Failed to submit request. Please try again.')
    } finally {
      setSending(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center sm:items-center"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-stone-900/60 backdrop-blur-sm" />
      <div
        className="relative max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-t-2xl bg-bone p-6 shadow-2xl sm:rounded-2xl sm:p-8"
        onClick={(e) => e.stopPropagation()}
      >
        {sent ? (
          <div className="py-8 text-center">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-accent-lo">
              <svg
                className="h-8 w-8 text-accent"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </div>
            <h3 className="mb-2 font-serif text-xl text-stone-900">Quote Request Sent</h3>
            <p className="mb-6 text-sm text-stone-500">
              {companyName} will review your request and respond via email.
            </p>
            <button
              onClick={onClose}
              className="rounded-lg bg-stone-900 px-6 py-2.5 text-sm font-medium text-bone transition-colors hover:bg-stone-800"
            >
              Close
            </button>
          </div>
        ) : (
          <>
            <div className="mb-6 flex items-center justify-between">
              <h3 className="font-serif text-xl text-stone-900">Request a Quote</h3>
              <button
                onClick={onClose}
                className="text-stone-400 transition-colors hover:text-stone-600"
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1.5 block text-xs font-medium tracking-wider text-stone-500 uppercase">
                    Your Name
                  </label>
                  <input
                    type="text"
                    value={form.buyerName}
                    onChange={(e) => setForm({ ...form, buyerName: e.target.value })}
                    className="w-full rounded-lg border border-stone-200 px-3 py-2.5 text-sm transition-all focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 focus:outline-none"
                    placeholder="Sarah Chen"
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-medium tracking-wider text-stone-500 uppercase">
                    Company
                  </label>
                  <input
                    type="text"
                    value={form.buyerCompany}
                    onChange={(e) => setForm({ ...form, buyerCompany: e.target.value })}
                    className="w-full rounded-lg border border-stone-200 px-3 py-2.5 text-sm transition-all focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 focus:outline-none"
                    placeholder="ABC Distribution"
                  />
                </div>
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium tracking-wider text-stone-500 uppercase">
                  Email *
                </label>
                <input
                  type="email"
                  required
                  value={form.buyerEmail}
                  onChange={(e) => setForm({ ...form, buyerEmail: e.target.value })}
                  className="w-full rounded-lg border border-stone-200 px-3 py-2.5 text-sm transition-all focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 focus:outline-none"
                  placeholder="sarah@abcdist.com"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium tracking-wider text-stone-500 uppercase">
                  Quantity of Interest
                </label>
                <input
                  type="number"
                  value={form.preferredQuantity}
                  onChange={(e) => setForm({ ...form, preferredQuantity: e.target.value })}
                  className="w-full rounded-lg border border-stone-200 px-3 py-2.5 text-sm transition-all focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 focus:outline-none"
                  placeholder="10,000"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium tracking-wider text-stone-500 uppercase">
                  Message
                </label>
                <textarea
                  value={form.message}
                  onChange={(e) => setForm({ ...form, message: e.target.value })}
                  rows={3}
                  className="w-full resize-none rounded-lg border border-stone-200 px-3 py-2.5 text-sm transition-all focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 focus:outline-none"
                  placeholder="Questions about pricing, specifications, or samples..."
                />
              </div>
              <button
                type="submit"
                disabled={sending || !form.buyerEmail}
                className="w-full rounded-lg bg-teal-700 py-3 text-sm font-semibold text-bone transition-all hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {sending ? 'Submitting...' : 'Request Quote'}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  )
}

// ============================================================
// EMAIL GATE OVERLAY
// ============================================================

function EmailGateOverlay({ onSubmit }: { onSubmit: (email: string) => void }) {
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = email.trim()
    if (!trimmed || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
      setError('Please enter a valid email address')
      return
    }
    onSubmit(trimmed)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-50">
      <div className="mx-auto w-full max-w-md px-6">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-5 flex h-12 w-12 items-center justify-center rounded-full bg-accent-lo">
            <svg
              className="h-6 w-6 text-accent"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
              />
            </svg>
          </div>
          <h1 className="mb-2 font-serif text-2xl text-stone-900 sm:text-3xl">
            Enter your email to view this deal room
          </h1>
          <p className="text-sm text-stone-400">Your email will be shared with the supplier</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <input
              type="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value)
                setError('')
              }}
              placeholder="you@company.com"
              autoFocus
              className="w-full rounded-xl border border-stone-200 px-4 py-3 text-sm transition-all focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 focus:outline-none"
            />
            {error && <p className="mt-1.5 text-xs text-threat">{error}</p>}
          </div>
          <button
            type="submit"
            className="w-full rounded-xl bg-teal-700 py-3 text-sm font-semibold text-bone shadow-lg shadow-teal-700/20 transition-all hover:bg-teal-800"
          >
            Continue
          </button>
        </form>
        <p className="mt-8 text-center text-xs text-stone-300">Powered by Prelude</p>
      </div>
    </div>
  )
}

// ============================================================
// SECTION DIVIDER
// ============================================================

function QuoteExpiry({ validUntil }: { validUntil: string }) {
  const daysLeft = Math.ceil((new Date(validUntil).getTime() - Date.now()) / 86400000)
  if (daysLeft < 0) return <span className="text-xs font-medium text-threat">Quote expired</span>
  if (daysLeft <= 30)
    return (
      <span className="text-xs font-medium text-gold">
        Expires in {daysLeft} day{daysLeft !== 1 ? 's' : ''}
      </span>
    )
  return <span className="text-xs text-stone-400">Valid until {validUntil}</span>
}

function SectionDivider() {
  return (
    <div className="flex items-center justify-center py-2">
      <div className="h-px w-16 bg-stone-200" />
      <div className="mx-3 h-1.5 w-1.5 rounded-full bg-stone-300" />
      <div className="h-px w-16 bg-stone-200" />
    </div>
  )
}

// ============================================================
// SECTION COMPONENTS
// ============================================================

function CostBreakdownRow({
  label,
  value,
  currency,
  highlight,
}: {
  label: string
  value: number
  currency: string
  highlight?: boolean
}) {
  return (
    <div
      className={`flex items-center justify-between py-2 ${highlight ? 'mt-1 border-t-2 border-stone-900 pt-3' : 'border-t border-stone-100'}`}
    >
      <span className={`text-sm ${highlight ? 'font-semibold text-stone-900' : 'text-stone-500'}`}>
        {label}
      </span>
      <span
        className={`tabular-nums ${highlight ? 'text-lg font-semibold text-stone-900' : 'text-sm text-stone-700'}`}
      >
        {currency} {(value ?? 0).toFixed(2)}
      </span>
    </div>
  )
}

function QuoteOptionCard({
  option,
  quantity,
  moq,
}: {
  option: QuoteOption
  quantity: number
  moq: number
}) {
  const bd = option.costBreakdown
  const totalValue = (option.landedPrice ?? 0) * (quantity ?? 0)
  const [expanded, setExpanded] = useState(true)

  return (
    <div className="overflow-hidden rounded-xl border border-stone-200 bg-bone shadow-sm transition-shadow hover:shadow-md">
      <div className="border-b border-stone-100 bg-stone-50 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-xs font-medium tracking-wider text-stone-400 uppercase">
              {option.label}
            </span>
            {option.origin && (
              <p className="mt-0.5 text-sm text-stone-600">Origin: {option.origin}</p>
            )}
          </div>
          {option.incoterm && (
            <span className="rounded-md bg-stone-200/60 px-2.5 py-1 text-xs font-medium text-stone-600">
              {option.incoterm}
            </span>
          )}
        </div>
      </div>
      <div className="px-6 py-5">
        {/* Landed price — dominant */}
        <div className="mb-1 flex items-baseline justify-between">
          <span className="text-xs tracking-wider text-stone-400 uppercase">Landed Price</span>
          <span className="text-2xl font-semibold text-stone-900 tabular-nums">
            {option.currency || 'USD'} {(option.landedPrice ?? 0).toFixed(2)}
          </span>
        </div>
        <div className="flex items-baseline justify-between">
          <span className="text-xs tracking-wider text-stone-400 uppercase">FOB</span>
          <span className="text-sm text-stone-500 tabular-nums">
            {option.currency || 'USD'} {(option.fobPrice ?? 0).toFixed(2)}
          </span>
        </div>

        {/* Cost breakdown — expandable */}
        {bd && (bd.oceanFreight || bd.dutyAmount) && (
          <div className="mt-4">
            <button
              onClick={() => setExpanded(!expanded)}
              className="flex items-center gap-1.5 text-xs text-stone-400 transition-colors hover:text-stone-600"
            >
              <svg
                className={`h-3 w-3 transition-transform ${expanded ? 'rotate-90' : ''}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 5l7 7-7 7"
                />
              </svg>
              Cost breakdown
            </button>
            {expanded && (
              <div className="mt-2 border-t border-stone-100 pt-2">
                <CostBreakdownRow
                  label="FOB Price"
                  value={option.fobPrice}
                  currency={option.currency || 'USD'}
                />
                {bd.oceanFreight != null && (
                  <CostBreakdownRow
                    label="Ocean Freight"
                    value={bd.oceanFreight}
                    currency={option.currency || 'USD'}
                  />
                )}
                {bd.insurance != null && (
                  <CostBreakdownRow
                    label="Insurance"
                    value={bd.insurance}
                    currency={option.currency || 'USD'}
                  />
                )}
                {bd.customsBrokerage != null && (
                  <CostBreakdownRow
                    label="Customs Brokerage"
                    value={bd.customsBrokerage}
                    currency={option.currency || 'USD'}
                  />
                )}
                {bd.dutyAmount != null && (
                  <div className="-mx-6 flex items-center justify-between border-l-2 border-gold bg-gold-lo/50 px-6 py-2 pl-5">
                    <div>
                      <span className="text-sm text-gold">Import Duty</span>
                      {bd.dutyNotes && (
                        <span className="ml-2 text-xs text-gold">({bd.dutyNotes})</span>
                      )}
                    </div>
                    <span className="text-sm text-gold tabular-nums">
                      {option.currency || 'USD'} {(bd.dutyAmount ?? 0).toFixed(2)}
                    </span>
                  </div>
                )}
                {bd.otherFees != null && bd.otherFees > 0 && (
                  <CostBreakdownRow
                    label={bd.otherFeesNotes || 'Other Fees'}
                    value={bd.otherFees}
                    currency={option.currency || 'USD'}
                  />
                )}
                <CostBreakdownRow
                  label="Landed Price / unit"
                  value={option.landedPrice}
                  currency={option.currency || 'USD'}
                  highlight
                />
              </div>
            )}
          </div>
        )}

        {moq > 0 && (
          <div className="mt-4 border-t border-stone-100 pt-4 text-sm text-stone-500">
            MOQ: {(moq ?? 0).toLocaleString()} units
          </div>
        )}
        {option.leadTimeDays && (
          <div className="mt-2 text-xs text-stone-400">Lead time: {option.leadTimeDays} days</div>
        )}
      </div>
    </div>
  )
}

// ============================================================
// MAIN PAGE
// ============================================================

export default function DealRoomPage() {
  const params = useParams()
  const token = params.token as string

  const [data, setData] = useState<DealRoomData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showMessageModal, setShowMessageModal] = useState(false)
  const [activePhoto, setActivePhoto] = useState(0)
  const [gateEmail, setGateEmail] = useState<string | undefined>(undefined)
  const [gateBypass, setGateBypass] = useState(false)

  const emailGateActive = !!data?.deal.roomSettings.emailGate && !gateBypass
  useViewTracking(token, !!data && !emailGateActive, gateEmail)

  useEffect(() => {
    fetch(`/api/deal/${token}`)
      .then((res) => {
        if (!res.ok) throw new Error('Deal room not found')
        return res.json()
      })
      .then((d: DealRoomData) => {
        setData(d)
        document.title = `Deal Room — ${d.factory?.companyProfile?.companyNameEn || d.deal?.dealName || 'Deal Room'}`
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [token])

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bone">
        <PageLoader brand label="Loading deal room" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <div className="text-center">
          <h1 className="mb-2 font-serif text-2xl text-stone-900">Deal Room Unavailable</h1>
          <p className="text-stone-500">This deal room may have expired or been closed.</p>
        </div>
      </div>
    )
  }

  if (emailGateActive) {
    return (
      <>
        <style jsx global>{`
          body {
            font-family: 'DM Sans', system-ui, sans-serif;
          }
          .font-serif {
            font-family: 'DM Serif Display', Georgia, serif;
          }
        `}</style>
        <EmailGateOverlay
          onSubmit={(email) => {
            setGateEmail(email)
            setGateBypass(true)
          }}
        />
      </>
    )
  }

  const { deal, buyer, factory, certifications } = data
  const { companyProfile, factoryDetails } = factory
  const quoteData = deal.quoteData
  const settings = deal.roomSettings
  const timeline = deal.sampleTimeline
  const photos = factoryDetails?.photoUrls || []

  const hasCerts = certifications.length > 0 || companyProfile?.insurance
  const hasFactory =
    factoryDetails && (factoryDetails.capacity || factoryDetails.leadTime || photos.length > 0)
  const hasTimeline = timeline && (timeline.goldenSampleDays || timeline.notes)

  // Landed price for mobile CTA
  const primaryOption = quoteData?.options?.[0]
  const landedDisplay = primaryOption
    ? `${primaryOption.currency || 'USD'} ${(primaryOption.landedPrice ?? 0).toFixed(2)}/unit`
    : null

  return (
    <>
      <style jsx global>{`
        body {
          font-family: 'DM Sans', system-ui, sans-serif;
        }
        .font-serif {
          font-family: 'DM Serif Display', Georgia, serif;
        }
      `}</style>

      <div className="min-h-screen">
        {/* ─── HERO HEADER ─── */}
        <header data-section="header" className="bg-stone-900 text-bone">
          <div className="mx-auto max-w-3xl px-5 py-12 sm:py-16">
            <div className="flex items-start gap-5">
              {companyProfile?.logoUrl && (
                <img
                  src={companyProfile.logoUrl}
                  alt=""
                  className="h-14 w-14 flex-shrink-0 rounded-lg border border-bone/10 bg-bone/10 object-contain p-1 sm:h-16 sm:w-16"
                />
              )}
              <div className="min-w-0">
                <h1 className="font-serif text-2xl leading-tight text-bone sm:text-3xl">
                  {companyProfile?.companyNameEn || deal.dealName}
                </h1>
                {companyProfile?.location && (
                  <p className="mt-1 text-sm text-stone-400">{companyProfile.location}</p>
                )}
              </div>
            </div>
            <div className="mt-8 border-t border-stone-700/50 pt-6">
              <p className="text-[11px] font-medium tracking-[0.2em] text-stone-500 uppercase">
                Prepared for
              </p>
              <p className="mt-1 text-lg text-stone-200">{buyer.clientName}</p>
            </div>
          </div>
        </header>

        <main className="mx-auto max-w-3xl px-5">
          {/* ─── QUOTE ─── */}
          {quoteData?.options?.length > 0 && (
            <section data-section="quote" className="py-10 sm:py-14">
              <p className="mb-2 text-[11px] font-semibold tracking-[0.15em] text-stone-400 uppercase">
                Pricing
              </p>
              <div className="mb-6 flex items-baseline justify-between">
                <h2 className="font-serif text-xl text-stone-900 sm:text-2xl">
                  {quoteData.productName || 'Quote'}
                </h2>
                {quoteData.validUntil && <QuoteExpiry validUntil={quoteData.validUntil} />}
              </div>
              {quoteData.hsCode && (
                <p className="mb-6 text-sm text-stone-400">HS {quoteData.hsCode}</p>
              )}
              <div className="grid gap-4 sm:grid-cols-2">
                {quoteData.options.map((opt, i) => (
                  <QuoteOptionCard
                    key={i}
                    option={opt}
                    quantity={quoteData.quantity}
                    moq={quoteData.moq}
                  />
                ))}
              </div>
            </section>
          )}

          <SectionDivider />

          {/* ─── COMPLIANCE ─── */}
          {hasCerts && settings?.showCompliance !== false && (
            <>
              <section data-section="compliance" className="py-10 sm:py-14">
                <p className="mb-2 text-[11px] font-semibold tracking-[0.15em] text-stone-400 uppercase">
                  Compliance
                </p>
                <h2 className="mb-6 font-serif text-xl text-stone-900 sm:text-2xl">
                  Certifications & Insurance
                </h2>
                <div className="grid gap-3 sm:grid-cols-2">
                  {certifications.map((cert, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-3.5 rounded-xl border border-stone-200 bg-bone p-4"
                    >
                      {/* Shield icon */}
                      <div
                        className={`flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg ${cert.status === 'active' ? 'bg-accent-lo' : 'bg-threat-lo'}`}
                      >
                        <ShieldCheck
                          className={`h-[18px] w-[18px] ${cert.status === 'active' ? 'text-accent' : 'text-threat'}`}
                          strokeWidth={1.5}
                        />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-stone-900">
                          {cert.certType}
                        </p>
                        <p className="mt-0.5 text-xs text-stone-400">
                          {cert.issuingBody}
                          {cert.expiryDate ? ` \u00B7 Exp. ${cert.expiryDate}` : ''}
                        </p>
                        {cert.documentUrl && (
                          <a
                            href={cert.documentUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="mt-1.5 inline-flex items-center gap-1 text-xs font-medium text-teal-700 transition-colors hover:text-teal-900"
                          >
                            View certificate
                            <svg
                              className="h-3 w-3"
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                              />
                            </svg>
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                  {companyProfile?.insurance && (
                    <div className="flex items-start gap-3.5 rounded-xl border border-stone-200 bg-bone p-4">
                      <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-accent-lo">
                        <ShieldCheck
                          className="h-[18px] w-[18px] text-accent"
                          strokeWidth={1.5}
                        />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-stone-900">
                          {companyProfile.insurance.type}
                        </p>
                        <p className="mt-0.5 text-xs text-stone-400">
                          {companyProfile.insurance.coverageAmount} &middot;{' '}
                          {companyProfile.insurance.insurer}
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              </section>
              <SectionDivider />
            </>
          )}

          {/* ─── FACTORY ─── */}
          {hasFactory && settings?.showFactory !== false && (
            <>
              <section data-section="factory" className="py-10 sm:py-14">
                <p className="mb-2 text-[11px] font-semibold tracking-[0.15em] text-stone-400 uppercase">
                  Factory
                </p>
                <h2 className="mb-6 font-serif text-xl text-stone-900 sm:text-2xl">
                  Production Facility
                </h2>
                {photos.length > 0 && (
                  <div className="mb-6">
                    <div className="relative aspect-[3/2] overflow-hidden rounded-xl bg-stone-100">
                      <img
                        src={photos[activePhoto]}
                        alt="Factory"
                        className="h-full w-full object-cover"
                      />
                    </div>
                    {photos.length > 1 && (
                      <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
                        {photos.map((url, i) => (
                          <button
                            key={i}
                            onClick={() => setActivePhoto(i)}
                            className={`h-12 w-16 flex-shrink-0 overflow-hidden rounded-lg border-2 transition-all ${i === activePhoto ? 'scale-105 border-teal-600 opacity-100' : 'border-transparent opacity-60 hover:opacity-80'}`}
                          >
                            <img src={url} alt="" className="h-full w-full object-cover" />
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {factoryDetails.capacity && (
                    <div className="rounded-xl border border-stone-200 bg-bone p-4">
                      <p className="text-[10px] font-medium tracking-wider text-stone-400 uppercase">
                        Capacity
                      </p>
                      <p className="mt-1 text-sm font-medium text-stone-900">
                        {factoryDetails.capacity}
                      </p>
                    </div>
                  )}
                  {factoryDetails.leadTime && (
                    <div className="rounded-xl border border-stone-200 bg-bone p-4">
                      <p className="text-[10px] font-medium tracking-wider text-stone-400 uppercase">
                        Lead Time
                      </p>
                      <p className="mt-1 text-sm font-medium text-stone-900">
                        {factoryDetails.leadTime}
                      </p>
                    </div>
                  )}
                  {factoryDetails.moq && (
                    <div className="rounded-xl border border-stone-200 bg-bone p-4">
                      <p className="text-[10px] font-medium tracking-wider text-stone-400 uppercase">
                        MOQ
                      </p>
                      <p className="mt-1 text-sm font-medium text-stone-900">
                        {(factoryDetails.moq ?? 0).toLocaleString()} units
                      </p>
                    </div>
                  )}
                  {factoryDetails.yearEstablished && (
                    <div className="rounded-xl border border-stone-200 bg-bone p-4">
                      <p className="text-[10px] font-medium tracking-wider text-stone-400 uppercase">
                        Established
                      </p>
                      <p className="mt-1 text-sm font-medium text-stone-900">
                        {factoryDetails.yearEstablished}
                      </p>
                    </div>
                  )}
                </div>
                {factoryDetails.videoTourUrl && (
                  <a
                    href={factoryDetails.videoTourUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-teal-700 transition-colors hover:text-teal-900"
                  >
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
                      />
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                    Watch Factory Tour
                  </a>
                )}
              </section>
              <SectionDivider />
            </>
          )}

          {/* ─── SAMPLE TIMELINE ─── */}
          {hasTimeline && settings?.showSampleTimeline !== false && (
            <>
              <section data-section="sample_timeline" className="py-10 sm:py-14">
                <p className="mb-2 text-[11px] font-semibold tracking-[0.15em] text-stone-400 uppercase">
                  Samples
                </p>
                <h2 className="mb-6 font-serif text-xl text-stone-900 sm:text-2xl">
                  Sample Timeline
                </h2>
                <div className="rounded-xl border border-stone-200 bg-bone p-6">
                  <div className="flex items-center gap-4">
                    {timeline.goldenSampleDays && (
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-teal-50">
                          <span className="text-sm font-semibold text-teal-700">
                            {timeline.goldenSampleDays}d
                          </span>
                        </div>
                        <div>
                          <p className="text-sm font-medium text-stone-900">Golden Sample</p>
                          <p className="text-xs text-stone-400">
                            Ships in {timeline.goldenSampleDays} business days
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                  {timeline.approvalWorkflow && (
                    <p className="mt-4 border-t border-stone-100 pt-4 text-xs text-stone-400">
                      Built-in approval workflow &middot; Production starts after sample approval
                    </p>
                  )}
                  {timeline.notes && (
                    <p className="mt-3 text-sm text-stone-500">{timeline.notes}</p>
                  )}
                </div>
              </section>
              <SectionDivider />
            </>
          )}

          {/* ─── MESSAGE ─── */}
          <section data-section="message" className="py-10 pb-28 sm:py-14 sm:pb-14">
            {settings?.customMessageEn && (
              <div className="mb-6 rounded-r-xl border-l-[3px] border-teal-600 bg-stone-50 p-6">
                <p className="text-sm leading-relaxed whitespace-pre-line text-stone-600 italic">
                  {settings.customMessageEn}
                </p>
                <p className="mt-4 text-xs text-stone-400 not-italic">
                  &mdash; {companyProfile?.companyNameEn || 'The Manufacturer'}
                </p>
              </div>
            )}
            <button
              onClick={() => setShowMessageModal(true)}
              className="group hidden w-full items-center justify-center gap-2 rounded-xl bg-teal-700 px-8 py-3.5 text-sm font-semibold text-bone shadow-lg shadow-teal-700/20 transition-all hover:bg-teal-800 sm:inline-flex sm:w-auto"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                />
              </svg>
              Request Quote
              <svg
                className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 5l7 7-7 7"
                />
              </svg>
            </button>
          </section>
        </main>

        {/* ─── MOBILE STICKY CTA ─── */}
        <div className="fixed right-0 bottom-0 left-0 z-40 border-t border-stone-200 bg-bone/80 p-4 backdrop-blur-xl sm:hidden">
          <button
            onClick={() => setShowMessageModal(true)}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-teal-700 py-3.5 text-sm font-semibold text-bone shadow-lg"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
              />
            </svg>
            {landedDisplay ? `${landedDisplay} — Request Quote` : 'Request Quote'}
          </button>
        </div>

        {/* ─── FOOTER ─── */}
        <footer className="mt-4 border-t border-stone-200">
          <div className="mx-auto max-w-3xl px-5 py-6 text-center">
            <p className="text-xs text-stone-300">Powered by Prelude</p>
          </div>
        </footer>
      </div>

      {showMessageModal && (
        <MessageModal
          token={token}
          companyName={companyProfile?.companyNameEn || 'the manufacturer'}
          onClose={() => setShowMessageModal(false)}
        />
      )}
    </>
  )
}
