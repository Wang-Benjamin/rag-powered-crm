'use client'

import { ImageIcon } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { useSearchParams } from 'next/navigation'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { toast } from 'sonner'

import {
  fetchPublicStorefront,
  submitQuoteRequest,
  StorefrontApiError,
  type PublicStorefront,
  type PublicStorefrontProduct,
} from '@/lib/api/storefront'
import { RequestQuoteModal, type QuoteRequestPayload } from './RequestQuoteModal'

// ─── helpers ────────────────────────────────────────────────────────────────

const STRIPE = {
  background:
    'repeating-linear-gradient(135deg, var(--cream) 0 14px, var(--fog) 14px 15px)',
} as const

const RADIAL_OVERLAY = {
  background:
    'radial-gradient(ellipse at 20% 120%, color-mix(in oklab, var(--accent) 50%, transparent) 0%, transparent 60%)',
} as const

function Eyebrow({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
  return (
    <p
      className={`font-mono text-[11px] uppercase text-mute ${
        wide ? 'tracking-[0.14em]' : 'tracking-[0.08em]'
      }`}
    >
      {children}
    </p>
  )
}

function SectionHead({
  eyebrow,
  title,
  lede,
  size = 'sm',
  mb = 'none',
}: {
  eyebrow: string
  title: ReactNode
  lede: string
  size?: 'sm' | 'lg'
  mb?: 'none' | 'tight' | 'wide'
}) {
  const titleClass =
    size === 'lg'
      ? 'font-display text-[clamp(40px,5vw,64px)] text-deep mt-2 leading-none'
      : 'font-display text-[clamp(32px,3.5vw,44px)] text-deep mt-2'
  const mbClass = mb === 'wide' ? 'mb-16' : mb === 'tight' ? 'mb-10' : 'mb-0'
  return (
    <div className={`grid lg:grid-cols-[1fr_1.4fr] gap-12 items-end ${mbClass}`}>
      <div>
        <Eyebrow>{eyebrow}</Eyebrow>
        <h2 className={titleClass}>{title}</h2>
      </div>
      <p className="text-[17px] text-mute max-w-[52ch]">{lede}</p>
    </div>
  )
}

function FooterHeading({ children }: { children: ReactNode }) {
  return (
    <h4 className="font-mono text-[11px] text-mute uppercase tracking-[0.1em] mb-4 font-medium">
      {children}
    </h4>
  )
}

function FooterLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      href={href}
      className="block text-ink no-underline text-sm mb-2.5 hover:text-accent transition-colors"
    >
      {children}
    </a>
  )
}

// Flatten the lean `specs` JSONB ({ "颜色": "红白", … }) into a one-line
// summary for the catalog card. Falls back to `description` when specs is empty.
function summarizeProduct(product: PublicStorefrontProduct): string {
  const entries = Object.entries(product.specs ?? {}).filter(
    ([, v]) => v != null && String(v).trim() !== '',
  )
  if (entries.length > 0) {
    return entries.map(([k, v]) => `${k}: ${v}`).join(' · ')
  }
  return product.description ?? ''
}

function InlineProductCard({
  product,
  onQuote,
  disabled,
}: {
  product: PublicStorefrontProduct
  onQuote: (p: PublicStorefrontProduct) => void
  disabled: boolean
}) {
  const moqLabel =
    product.moq != null ? `MOQ: ${product.moq.toLocaleString()}` : 'MOQ: on request'
  const specLine = summarizeProduct(product)
  return (
    <button
      className="group flex flex-col text-left border border-rule rounded-xl overflow-hidden bg-bone hover:border-ink hover:-translate-y-0.5 hover:shadow-[0_14px_32px_-18px_oklch(0.25_0.02_260/0.25)] transition"
      onClick={() => onQuote(product)}
      disabled={disabled}
    >
      <div className="aspect-square border-b border-rule bg-cream relative flex items-center justify-center overflow-hidden">
        {product.imageUrl ? (
          <img
            src={product.imageUrl}
            alt={product.name}
            loading="lazy"
            className="h-full w-full object-cover"
          />
        ) : (
          <ImageIcon className="h-12 w-12 text-mute/60" aria-hidden />
        )}
      </div>
      <div className="flex-1 flex flex-col gap-2.5 p-[18px]">
        <div className="flex justify-between items-baseline gap-3">
          <span className="title-block truncate">{product.name}</span>
          {product.hsCode && (
            <span className="font-mono text-[10px] text-mute whitespace-nowrap">
              {product.hsCode}
            </span>
          )}
        </div>
        {specLine && <div className="text-xs text-mute line-clamp-2">{specLine}</div>}
        <div className="mt-auto pt-3 border-t border-rule flex justify-between items-baseline">
          <span className="font-mono text-[11px] text-mute">{moqLabel}</span>
          <span className="inline-flex items-center gap-1.5 text-xs text-accent border border-accent/40 group-hover:border-accent group-hover:bg-accent-lo px-2.5 py-1 rounded-md font-medium transition">
            + Quote
          </span>
        </div>
      </div>
    </button>
  )
}

// ─── main component ──────────────────────────────────────────────────────────

export function PublicStorefrontView({ slug }: { slug: string }) {
  // Buyer page is English-only by design.
  const tModal = useTranslations('storefront.requestQuoteModal')
  const tPage = useTranslations('storefront.publicPage')

  const sellerEmail = useSearchParams().get('seller')

  const [data, setData] = useState<PublicStorefront | null>(null)
  const [error, setError] = useState<'not_found' | 'generic' | null>(null)
  const [loading, setLoading] = useState(true)
  const [quoteProduct, setQuoteProduct] = useState<PublicStorefrontProduct | null>(null)

  // Catalog state — `specs.category` is the only category source on lean
  // products today; absent that, the filter pills collapse to just "All".
  const [activeFilter, setActiveFilter] = useState<string>('all')
  const [density, setDensity] = useState<'comfortable' | 'dense'>('comfortable')

  // Sticky CTA visibility
  const [stickyVisible, setStickyVisible] = useState(false)
  const heroRef = useRef<HTMLElement>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchPublicStorefront(slug)
      .then((res) => {
        if (cancelled) return
        setData(res)
        setError(null)
      })
      .catch((err) => {
        if (cancelled) return
        if (err instanceof StorefrontApiError && err.status === 404) {
          setError('not_found')
        } else {
          setError('generic')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [slug])

  useEffect(() => {
    const onScroll = () => {
      setStickyVisible(window.scrollY > 600)
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const handleSubmit = async (payload: QuoteRequestPayload) => {
    if (!sellerEmail) {
      throw new Error('Missing seller in storefront URL')
    }
    await submitQuoteRequest(slug, payload, sellerEmail)
    toast.success(tPage('toastSent'))
  }

  const modalLabels = {
    title: tModal('title'),
    subtitle: String(tModal.raw('subtitle')),
    yourName: tModal('yourName'),
    yourNamePlaceholder: tModal('yourNamePlaceholder'),
    company: tModal('company'),
    companyPlaceholder: tModal('companyPlaceholder'),
    email: tModal('email'),
    emailPlaceholder: tModal('emailPlaceholder'),
    emailRequired: tModal('emailRequired'),
    quantity: tModal('quantity'),
    quantityPlaceholder: tModal('quantityPlaceholder'),
    message: tModal('message'),
    messagePlaceholder: tModal('messagePlaceholder'),
    submit: tModal('submit'),
    submitting: tModal('submitting'),
    cancel: tModal('cancel'),
    closeAriaLabel: tModal('closeAriaLabel'),
    successTitle: tModal('successTitle'),
    successBody: String(tModal.raw('successBody')),
    errorGeneric: tModal('errorGeneric'),
    errorRateLimited: tModal('errorRateLimited'),
  }

  // ── loading / error states ──────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-sm text-mute">{tPage('loading')}</div>
      </div>
    )
  }

  if (error === 'generic') {
    return (
      <div className="flex min-h-screen items-center justify-center px-6">
        <div className="max-w-md text-center">
          {/* Geist (no font-display) — display headings require an italic <em> phrase per design kit, which doesn't fit a short error label. */}
          <h1 className="text-2xl font-bold text-deep">{tPage('errorTitle')}</h1>
          <p className="mt-3 text-sm text-mute">{tPage('errorBody')}</p>
        </div>
      </div>
    )
  }

  if (error === 'not_found' || !data) {
    return (
      <div className="flex min-h-screen items-center justify-center px-6">
        <div className="max-w-md text-center">
          <h1 className="text-2xl font-bold text-deep">{tPage('notFoundTitle')}</h1>
          <p className="mt-3 text-sm text-mute">{tPage('notFoundBody')}</p>
        </div>
      </div>
    )
  }

  const canRequestQuote = Boolean(sellerEmail)
  const {
    sellerName,
    factoryPhotoUrl,
    heroStats,
    keyFacts,
    certifications,
    contact,
    products,
  } = data
  // Brandmark monogram: pick first character, fall back to "?" if empty.
  // Italic Instrument Serif renders well for Latin caps but is meaningless on
  // CJK glyphs — drop italic for non-Latin so the monogram stays legible.
  const monogram = sellerName.charAt(0) || '?'
  const isLatinMonogram = /^[A-Za-z]/.test(monogram)
  const monogramClass = isLatinMonogram
    ? 'font-display italic'
    : 'font-display'
  const currentYear = new Date().getFullYear()

  // Hero meta strip — Q1-a: render seller string as-is in `primary`, leave
  // unit + sub blank. Cells with no value are still rendered (empty value
  // shows as em-dash) so the four-column grid keeps its shape.
  const heroCells: Array<{ label: string; primary: string | null }> = [
    { label: 'Founded', primary: heroStats.yearFounded },
    { label: 'Employees', primary: heroStats.staff },
    { label: 'Capacity', primary: heroStats.capacity },
    { label: 'Export share', primary: heroStats.exportShare },
  ]
  const hasAnyHeroStat = heroCells.some((c) => c.primary)

  // Key Facts — Q3-a: free string in `primary`, no `unit`/`sub` split. Hide
  // rows with no value so the strip doesn't look like a row of em-dashes.
  const keyFactCells: Array<{ label: string; primary: string }> = [
    { label: 'MOQ', primary: keyFacts.moq ?? '' },
    { label: 'Lead time', primary: keyFacts.leadTime ?? '' },
    { label: 'Samples', primary: keyFacts.samplePolicy ?? '' },
    { label: 'Shipping', primary: keyFacts.shipping ?? '' },
    { label: 'Payment', primary: keyFacts.payment ?? '' },
  ].filter((c) => c.primary)

  // Catalog category filter — derived from `specs.category` when present.
  // No category column on lean products, so when nothing has it we collapse
  // to a single "All products" pill.
  const categories = Array.from(
    new Set(
      products
        .map((p) => (p.specs ?? {})['category'] ?? (p.specs ?? {})['Category'])
        .filter((c): c is string => Boolean(c)),
    ),
  )

  const filteredProducts =
    activeFilter === 'all'
      ? products
      : products.filter(
          (p) =>
            ((p.specs ?? {})['category'] ?? (p.specs ?? {})['Category']) ===
            activeFilter,
        )

  const scrollToCatalog = () => {
    document.getElementById('catalog')?.scrollIntoView({ behavior: 'smooth' })
  }

  // ── render ──────────────────────────────────────────────────────────────

  return (
    <>
      {/* ── 1. STICKY NAV ───────────────────────────────────────────────── */}
      <nav className="sticky top-0 z-40 border-b border-rule bg-bone/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-[1240px] items-center justify-between px-10">
          {/* Brandmark */}
          <div className="flex items-center gap-2.5">
            <span className={`grid h-7 w-7 place-items-center rounded-md bg-deep ${monogramClass} text-bone text-sm`}>
              {monogram}
            </span>
            <span className="font-medium text-deep text-sm">{sellerName}</span>
            <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full bg-accent-lo px-2.5 py-1 font-mono text-[11px] uppercase tracking-[0.06em] text-accent">
              <span className="h-1.5 w-1.5 rounded-full bg-accent" />
              Verified supplier
            </span>
          </div>

          {/* Center nav links — hidden below lg */}
          <div className="hidden lg:flex items-center gap-6">
            {(
              [
                ['Overview', '#about'],
                ['Certifications', '#certifications'],
                ['Catalog', '#catalog'],
                ['Terms', '#facts'],
                ['Contact', '#contact'],
              ] as const
            ).map(([label, href]) => (
              <a
                key={href}
                href={href}
                className="text-sm text-mute hover:text-ink transition-colors"
              >
                {label}
              </a>
            ))}
          </div>

          {/* Right CTA */}
          <button
            onClick={scrollToCatalog}
            className="rounded-lg bg-deep px-4 py-2 text-sm font-medium text-bone hover:bg-accent transition-colors"
          >
            Request quote
          </button>
        </div>
      </nav>

      {/* ── 2. HERO ─────────────────────────────────────────────────────── */}
      <header id="about" ref={heroRef} className="bg-bone">
        <div className="mx-auto max-w-[1240px] px-10 py-16 lg:py-20">
          <div className="grid grid-cols-1 lg:grid-cols-[1.2fr_1fr] gap-16 items-end">
            {/* Left */}
            <div>
              <Eyebrow wide>Verified manufacturer</Eyebrow>
              <h1 className="mt-4 font-display text-deep text-[clamp(56px,8vw,112px)] leading-none tracking-[-0.015em]">
                {sellerName},
                <br />
                <em className="italic text-accent">engineered for export.</em>
              </h1>
              <p className="mt-7 max-w-[54ch] text-lg text-mute">
                A verified manufacturing partner on Prelude. In-house production, certified
                materials, and an export team that replies in English within one business day.
              </p>

              {/* Incomplete share notice — relocated under summary */}
              {!canRequestQuote && (
                <p className="mt-4 max-w-[54ch] rounded-md border border-rule bg-paper px-3 py-2 text-xs text-mute">
                  {tPage('incompleteShare')}
                </p>
              )}

              <div className="mt-8 flex flex-wrap gap-3">
                <button
                  onClick={scrollToCatalog}
                  className="rounded-lg bg-deep px-5 py-3.5 text-[15px] font-medium text-bone hover:bg-accent transition-colors"
                >
                  Request a quote →
                </button>
              </div>
            </div>

            {/* Right — factory photo, with striped placeholder fallback */}
            {factoryPhotoUrl ? (
              <div className="aspect-[4/5] min-h-[420px] rounded-xl border border-rule overflow-hidden bg-cream">
                <img
                  src={factoryPhotoUrl}
                  alt={`${sellerName} factory`}
                  className="h-full w-full object-cover"
                />
              </div>
            ) : (
              <div
                className="aspect-[4/5] min-h-[420px] rounded-xl border border-rule overflow-hidden flex items-end p-4 relative"
                style={STRIPE}
              >
                <div className="absolute inset-3 rounded-lg border border-dashed border-mute/30 pointer-events-none" />
                <span className="relative font-mono text-[11px] uppercase tracking-[0.04em] bg-bone px-2.5 py-1.5 rounded border border-rule text-mute">
                  Factory photo
                </span>
              </div>
            )}
          </div>

          {/*
            Hero meta strip — Q1-a: free strings in `primary`. Hide the strip
            entirely when no tenant has filled any of yearFounded / staff /
            capacity / exportShare; otherwise render all four cells so the grid
            keeps its column shape, with em-dash on missing values.
          */}
          {hasAnyHeroStat && (
            <div className="border-t border-rule mt-16 pt-6 grid grid-cols-2 sm:grid-cols-4 gap-y-6 sm:gap-y-0">
              {heroCells.map((cell, i) => {
                const isFirstInMobileRow = i % 2 === 0
                const isFirstInDesktopRow = i === 0
                return (
                  <div
                    key={cell.label}
                    className={[
                      'px-5',
                      isFirstInMobileRow ? 'pl-0 sm:pl-5' : 'border-l border-rule',
                      isFirstInDesktopRow
                        ? 'sm:border-l-0 sm:pl-0'
                        : 'sm:border-l sm:border-rule sm:pl-5',
                    ].join(' ')}
                  >
                    <Eyebrow>{cell.label}</Eyebrow>
                    <p className="font-display text-3xl text-deep mt-1.5 leading-[1.05]">
                      {cell.primary ?? '—'}
                    </p>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </header>

      {/* ── 3. TRUST BAND ───────────────────────────────────────────────── */}
      {/* Hide the entire band when no active certifications exist (graceful degradation). */}
      {certifications.length > 0 && (
        <section id="certifications" className="border-y border-rule bg-paper py-10">
          <div className="mx-auto max-w-[1240px] px-10 grid lg:grid-cols-[200px_1fr] gap-12 items-center">
            <div>
              <h3 className="text-sm font-medium text-ink">Certifications</h3>
              <p className="text-[13px] text-mute mt-1.5">
                Documents available on request.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              {certifications.map((cert) => {
                // Q2-a: no `mark` glyph. Chip = [type] [issuingBody] [number].
                const label = cert.certType ?? 'Certified'
                return (
                  <div
                    key={cert.certId}
                    title={cert.notes ?? undefined}
                    className="inline-flex items-center gap-2.5 px-3.5 py-2.5 bg-bone border border-rule rounded-[10px] text-[13px] text-ink hover:border-ink hover:-translate-y-px transition cursor-default"
                  >
                    <span>{label}</span>
                    {cert.issuingBody && (
                      <span className="font-mono text-[10px] text-mute">
                        {cert.issuingBody}
                      </span>
                    )}
                    {cert.certNumber && (
                      <span className="font-mono text-[10px] text-mute">
                        {cert.certNumber}
                      </span>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </section>
      )}

      {/* ── 4. KEY FACTS ────────────────────────────────────────────────── */}
      {/* Hide entire section when no terms saved (graceful degradation). */}
      {keyFactCells.length > 0 && (
        <section id="facts" className="border-y border-rule bg-paper">
          <div className="mx-auto max-w-[1240px] px-10 py-16">
            <SectionHead
              eyebrow="The short answers"
              title={<>Before you <em className="italic text-accent">ask</em>.</>}
              lede="What North American buyers want to know first. Exact terms by SKU are confirmed in a quote."
            />
          </div>

          {/* Q3-a: free strings in `primary`. Card body smaller than the
              hero stat card to accommodate longer terms ("30% T/T deposit,
              70% on B/L copy") without wrapping awkwardly. */}
          <div
            className="border-t border-rule grid grid-cols-1 sm:grid-cols-2"
            style={{ gridTemplateColumns: `repeat(auto-fit, minmax(220px, 1fr))` }}
          >
            {keyFactCells.map((fact, i) => {
              const isLast = i === keyFactCells.length - 1
              return (
                <div
                  key={fact.label}
                  className={`px-7 py-8 ${isLast ? '' : 'border-r border-rule'}`}
                >
                  <Eyebrow>{fact.label}</Eyebrow>
                  <p className="text-xl text-deep leading-snug mt-3">{fact.primary}</p>
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* ── 5. CATALOG ──────────────────────────────────────────────────── */}
      <section id="catalog" className="bg-bone">
        <div className="mx-auto max-w-[1240px] px-10 py-20">
          <SectionHead
            eyebrow="Product catalog"
            title={
              products.length > 0 ? (
                <>
                  {products.length} {products.length === 1 ? 'SKU' : 'SKUs'},
                  <br />
                  <em className="italic text-accent">live and ready to quote.</em>
                </>
              ) : (
                <>
                  Catalog{' '}
                  <em className="italic text-accent">coming soon.</em>
                </>
              )
            }
            lede="Each SKU below is published by the manufacturer. Click Quote on any product to start a request — the seller's export team will reply within one business day."
            mb="tight"
          />

          {products.length === 0 ? (
            // Graceful empty state — tenant has no live products yet.
            <div className="border border-dashed border-rule rounded-xl bg-paper px-8 py-20 text-center">
              <p className="text-sm text-mute">Catalog coming soon.</p>
            </div>
          ) : (
            <>
              {/* Toolbar */}
              <div className="flex flex-wrap items-center justify-between gap-5 mb-8">
                {/* Filter pills — only show category pills when at least one
                    product has a `specs.category`. Otherwise just "All products". */}
                <div className="flex flex-wrap gap-1.5">
                  <button
                    aria-pressed={activeFilter === 'all'}
                    onClick={() => setActiveFilter('all')}
                    className={`text-[13px] px-3.5 py-2 rounded-full border transition ${
                      activeFilter === 'all'
                        ? 'bg-deep text-bone border-deep'
                        : 'border-rule text-mute hover:text-ink hover:border-ink'
                    }`}
                  >
                    All products{' '}
                    <span className="font-mono opacity-60 ml-1">{products.length}</span>
                  </button>
                  {categories.map((cat) => (
                    <button
                      key={cat}
                      aria-pressed={activeFilter === cat}
                      onClick={() => setActiveFilter(cat)}
                      className={`text-[13px] px-3.5 py-2 rounded-full border transition ${
                        activeFilter === cat
                          ? 'bg-deep text-bone border-deep'
                          : 'border-rule text-mute hover:text-ink hover:border-ink'
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>

                {/* Density toggle */}
                <div className="flex items-center gap-3">
                  <span className="font-mono text-[11px] text-mute uppercase tracking-[0.06em]">
                    View
                  </span>
                  <div className="flex border border-rule rounded-lg overflow-hidden">
                    {(['comfortable', 'dense'] as const).map((d) => (
                      <button
                        key={d}
                        aria-pressed={density === d}
                        onClick={() => setDensity(d)}
                        className={`px-3 py-1.5 text-[13px] transition ${
                          density === d ? 'bg-cream text-ink' : 'text-mute hover:text-ink'
                        }`}
                      >
                        {d === 'comfortable' ? 'Comfortable' : 'Dense'}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Catalog grid */}
              <div
                className={`grid gap-6 grid-cols-1 sm:grid-cols-2 ${
                  density === 'dense' ? 'lg:grid-cols-4 gap-4' : 'lg:grid-cols-3'
                }`}
              >
                {filteredProducts.map((p) => (
                  <InlineProductCard
                    key={p.productId}
                    product={p}
                    onQuote={setQuoteProduct}
                    disabled={!canRequestQuote}
                  />
                ))}
              </div>
            </>
          )}
        </div>
      </section>

      {/* ── 6. CTA BLOCK ────────────────────────────────────────────────── */}
      <section className="bg-deep text-bone py-20 relative overflow-hidden">
        {/* Radial gradient overlay */}
        <div className="absolute inset-0 opacity-50" style={RADIAL_OVERLAY} />

        <div className="mx-auto max-w-[1240px] px-10 grid lg:grid-cols-[1.2fr_1fr] gap-12 items-center relative">
          {/* Left */}
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-accent-lo">
              Ready to start?
            </p>
            <h2 className="font-display text-[clamp(40px,5vw,64px)] text-bone mt-4 leading-none">
              Get a <em className="italic text-accent-lo">formal quote</em> in 48 hours.
            </h2>
            <p className="text-bone/80 mt-8 max-w-[48ch] text-[17px] leading-relaxed">
              Send your request to the manufacturer&apos;s export team directly. Replies typically
              come within one business day — often with photos, tooling options, and a shipping
              estimate already attached.
            </p>
          </div>

          {/* Right — single CTA button */}
          <button
            onClick={scrollToCatalog}
            className="bg-bone text-deep border border-bone rounded-[10px] p-5 text-left flex justify-between items-center gap-5 hover:bg-accent-lo hover:-translate-y-0.5 transition w-full"
          >
            <span>
              <span className="block text-base font-medium text-deep mb-1">Build a quote</span>
              <span className="text-[13px] text-mute">
                Pick a product · formal RFQ in 48h
              </span>
            </span>
            <span className="text-xl">→</span>
          </button>
        </div>
      </section>

      {/* ── 7. CONTACT ──────────────────────────────────────────────────── */}
      <section id="contact" className="bg-bone">
        <div className="mx-auto max-w-[1240px] px-10 py-20">
          <SectionHead
            eyebrow="Talk to the factory"
            title={
              <>
                Direct line to <em className="italic text-accent">the export team.</em>
              </>
            }
            lede="The seller's export contact handles every overseas enquiry directly. No sales agents, no trading-company middle layer."
            size="lg"
            mb="wide"
          />

          {/* Info — single column. Email + phone are intentionally NOT shown:
              the page is unauthenticated, and the buyer's only way to reach
              the seller is via the Quote modal, which routes through Prelude. */}
          <div className="grid lg:grid-cols-[minmax(0,560px)] gap-16 items-start">
            <dl className="grid grid-cols-[140px_1fr] gap-y-4 gap-x-6 border-t border-rule pt-6">
              <dt className="font-mono text-[11px] text-mute uppercase tracking-[0.06em] self-center">
                Export contact
              </dt>
              <dd className="text-[15px] text-ink m-0">
                {contact.name ? (
                  <>
                    {contact.name}
                    {contact.title && (
                      <>
                        <br />
                        <span className="font-mono text-xs text-mute">{contact.title}</span>
                      </>
                    )}
                  </>
                ) : (
                  'Reach out via Prelude'
                )}
              </dd>

              <dt className="font-mono text-[11px] text-mute uppercase tracking-[0.06em] self-start pt-0.5">
                Office hours
              </dt>
              <dd className="text-[15px] text-ink m-0">
                Mon–Fri, 09:00–18:00 CST (GMT+8)
                <br />
                <span className="font-mono text-xs text-mute">
                  Replies outside hours — next business day
                </span>
              </dd>

              {contact.languages.length > 0 && (
                <>
                  <dt className="font-mono text-[11px] text-mute uppercase tracking-[0.06em] self-center">
                    Languages
                  </dt>
                  <dd className="text-[15px] text-ink m-0">
                    {contact.languages.join(', ')}
                  </dd>
                </>
              )}
            </dl>
          </div>
        </div>
      </section>

      {/* ── 8. FOOTER ───────────────────────────────────────────────────── */}
      <footer className="border-t border-rule pt-12 pb-8 bg-paper">
        <div className="mx-auto max-w-[1240px] px-10">
          <div className="grid grid-cols-2 lg:grid-cols-[2fr_1fr_1fr_1fr] gap-8 mb-10">
            {/* Col 1 — brandmark */}
            <div>
              <div className="flex items-center gap-2">
                <span className={`grid h-7 w-7 place-items-center rounded-md bg-deep ${monogramClass} text-bone text-sm`}>
                  {monogram}
                </span>
                <span className="font-medium text-deep text-sm">{sellerName}</span>
              </div>
              <p className="text-[13px] text-mute leading-relaxed max-w-[38ch] mt-3">
                {sellerName} on Prelude · A verified manufacturing partner.
              </p>
            </div>

            {/* Col 2 — Company */}
            <div>
              <FooterHeading>Company</FooterHeading>
              <ul className="list-none p-0 m-0">
                {[
                  ['Overview', '#about'],
                  ['Certifications', '#certifications'],
                  ['Terms', '#facts'],
                ].map(([label, href]) => (
                  <li key={href}>
                    <FooterLink href={href}>{label}</FooterLink>
                  </li>
                ))}
              </ul>
            </div>

            {/* Col 3 — Catalog */}
            <div>
              <FooterHeading>Catalog</FooterHeading>
              <ul className="list-none p-0 m-0">
                <li>
                  <FooterLink href="#catalog">All products</FooterLink>
                </li>
                {categories.slice(0, 3).map((cat) => (
                  <li key={cat}>
                    <FooterLink href="#catalog">{cat}</FooterLink>
                  </li>
                ))}
              </ul>
            </div>

            {/* Col 4 — Contact */}
            <div>
              <FooterHeading>Contact</FooterHeading>
              <ul className="list-none p-0 m-0">
                <li>
                  <FooterLink href="#contact">Contact info</FooterLink>
                </li>
                <li>
                  <FooterLink href="#catalog">Request a quote</FooterLink>
                </li>
              </ul>
            </div>
          </div>

          {/* Footer bottom */}
          <div className="flex justify-between items-center pt-6 border-t border-rule text-xs text-mute">
            <span>
              © {currentYear} {sellerName} · All rights reserved
            </span>
            <a
              href="https://preludeos.com"
              className="inline-flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.06em] text-mute px-2.5 py-1.5 border border-rule rounded-full bg-bone hover:border-ink hover:text-ink transition no-underline"
            >
              <span className="grid h-3.5 w-3.5 place-items-center rounded bg-deep font-display italic text-bone text-[10px]">
                P
              </span>
              Powered by Prelude
            </a>
          </div>
        </div>
      </footer>

      {/* ── 9. STICKY CTA PILL ──────────────────────────────────────────── */}
      <div
        className={`fixed bottom-5 left-1/2 z-30 -translate-x-1/2 transition-transform duration-300 ${
          stickyVisible ? 'translate-y-0' : 'translate-y-[120%]'
        }`}
      >
        <div className="bg-deep text-bone py-2.5 pl-5 pr-2.5 rounded-full flex items-center gap-4 shadow-[0_20px_60px_-20px_oklch(0.2_0.02_260/0.4)]">
          <span className="hidden sm:block text-bone/75 text-[13px]">
            Ready to evaluate?
          </span>
          <button
            onClick={scrollToCatalog}
            className="rounded-full bg-bone text-deep px-4 py-2 text-sm font-medium hover:bg-accent-lo transition-colors whitespace-nowrap"
          >
            Request quote
          </button>
        </div>
      </div>

      {/* ── QUOTE MODAL ─────────────────────────────────────────────────── */}
      <RequestQuoteModal
        open={quoteProduct !== null}
        onOpenChange={(next) => {
          if (!next) setQuoteProduct(null)
        }}
        product={
          quoteProduct
            ? { name: quoteProduct.name, sku: quoteProduct.productId }
            : null
        }
        sellerName={sellerName}
        labels={modalLabels}
        onSubmit={handleSubmit}
      />
    </>
  )
}
