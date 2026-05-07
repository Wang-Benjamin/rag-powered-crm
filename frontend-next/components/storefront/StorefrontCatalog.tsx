'use client'

import { ArrowUpRight, ExternalLink, Search, Share2 } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { decodeToken, getStoredIdToken } from '@/lib/auth/tokenUtils'
import { ProductCard } from './ProductCard'
import type { Product, ProductStatus } from './types'

export function StorefrontCatalog({
  status,
  products,
  onPublish,
  onEditProduct,
  leavingIds,
  enteringIds,
}: {
  status: ProductStatus
  products: Product[]
  onPublish: (ids: string[]) => void
  onEditProduct?: (product: Product) => void
  leavingIds: Set<string>
  enteringIds: Set<string>
}) {
  const t = useTranslations('storefront')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [query, setQuery] = useState('')

  // Build the seller's own storefront URL from JWT claims. Used by both the
  // Share button (copies to clipboard) and the View storefront link (opens it).
  // We do NOT bake a language into the URL — the buyer page resolves it
  // server-side from `user_profiles.preferred_locale` keyed off `?seller=`,
  // so it always tracks whatever language the seller has set in Prelude now.
  const myStorefrontUrl = useMemo(() => {
    if (typeof window === 'undefined') return null
    const token = getStoredIdToken()
    const decoded = token ? decodeToken(token) : null
    const claims = (decoded ?? {}) as { db_name?: string; email?: string }
    if (!claims.db_name) return null
    const url = new URL(`/storefront/${claims.db_name}`, window.location.origin)
    if (claims.email) url.searchParams.set('seller', claims.email)
    return url.toString()
  }, [])

  const handleShareStorefront = async () => {
    if (!myStorefrontUrl) {
      toast.error(t('catalog.shareStorefrontFailed'))
      return
    }
    try {
      await navigator.clipboard.writeText(myStorefrontUrl)
      toast.success(t('catalog.shareStorefrontCopied'))
    } catch {
      toast.error(t('catalog.shareStorefrontFailed'))
    }
  }

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return products
    return products.filter((p) => {
      const specChunks = Object.entries(p.specs ?? {})
        .map(([k, v]) => `${k} ${v}`)
        .join(' ')
      const id = p.productId ?? p.id ?? ''
      const name = p.name ?? p.nameEn ?? ''
      const hay = `${name} ${p.description ?? ''} ${specChunks} ${id}`.toLowerCase()
      return hay.includes(q)
    })
  }, [products, query])

  const visibleIds = filtered.map((p) => p.productId ?? p.id ?? '').filter(Boolean)
  const allSelected = visibleIds.length > 0 && visibleIds.every((id) => selected.has(id))
  const someSelected = selected.size > 0 && !allSelected

  const toggle = (id: string, next: boolean) => {
    setSelected((prev) => {
      const n = new Set(prev)
      if (next) n.add(id)
      else n.delete(id)
      return n
    })
  }

  const toggleAll = (next: boolean) => {
    setSelected(next ? new Set(visibleIds) : new Set())
  }

  const clear = () => setSelected(new Set())

  const publishSelected = () => {
    const ids = [...selected]
    clear()
    onPublish(ids)
  }

  const sectionTitle =
    status === 'pending' ? t('catalog.pending.sectionTitle') : t('catalog.live.sectionTitle')
  const helper = status === 'pending' ? t('catalog.pending.helper') : t('catalog.live.helper')
  const emptyTitle =
    status === 'pending' ? t('catalog.pending.emptyTitle') : t('catalog.live.emptyTitle')
  const emptyBody =
    status === 'pending' ? t('catalog.pending.emptyBody') : t('catalog.live.emptyBody')

  return (
    <section className="mb-6 rounded-lg border border-rule bg-bone p-6">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold text-deep">{sectionTitle}</h2>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search
              className="absolute top-1/2 left-2.5 h-3.5 w-3.5 -translate-y-1/2 text-mute"
              strokeWidth={1.75}
            />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t('catalog.searchPlaceholder')}
              aria-label={t('catalog.searchAriaLabel')}
              className="w-60 rounded-md border border-rule bg-bone py-1.5 pr-3 pl-8 text-sm text-ink placeholder:text-mute focus:border-deep focus:ring-2 focus:ring-deep/20 focus:outline-none"
            />
          </div>
          {status === 'live' && (
            <>
              <button
                type="button"
                onClick={handleShareStorefront}
                className="inline-flex items-center gap-1 rounded-md border border-rule bg-bone px-3 py-1.5 text-sm font-medium text-ink hover:bg-cream"
              >
                <Share2 className="h-3 w-3" strokeWidth={1.75} />
                <span>{t('catalog.shareStorefront')}</span>
              </button>
              {myStorefrontUrl && (
                <a
                  href={myStorefrontUrl}
                  target="_blank"
                  rel="noopener"
                  className="inline-flex items-center gap-1 rounded-md border border-rule bg-bone px-3 py-1.5 text-sm font-medium text-ink hover:bg-cream"
                >
                  <span>{t('catalog.viewStorefront')}</span>
                  <ExternalLink className="h-3 w-3" strokeWidth={1.75} />
                </a>
              )}
            </>
          )}
        </div>
      </div>

      <div className="mb-4 text-sm text-mute">{helper}</div>

      {status === 'pending' && selected.size > 0 && (
        <div className="sticky top-2 z-10 mb-4 flex items-center gap-3 rounded-lg bg-deep px-4 py-2.5 text-bone shadow-lg">
          <label className="flex cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              checked={allSelected}
              ref={(el) => {
                if (el) el.indeterminate = someSelected
              }}
              onChange={(e) => toggleAll(e.target.checked)}
              aria-label={t('bulkBar.selectAllAriaLabel')}
              className="h-3.5 w-3.5 accent-bone"
            />
            <span className="text-sm">
              {t('bulkBar.selectedPrefix')}{' '}
              <b>{selected.size}</b>
              {t('bulkBar.selectedSuffix') && ` ${t('bulkBar.selectedSuffix')}`}
            </span>
          </label>
          <div className="flex-1" />
          <button
            type="button"
            onClick={clear}
            className="rounded-md px-3 py-1 text-sm text-bone/70 hover:bg-deep/80 hover:text-bone"
          >
            {t('bulkBar.clear')}
          </button>
          <button
            type="button"
            onClick={publishSelected}
            className="inline-flex items-center gap-1.5 rounded-md bg-bone px-3.5 py-1.5 text-sm font-semibold text-deep shadow-sm transition-colors hover:bg-cream"
          >
            <span>{t('bulkBar.bulkPublish')}</span>
            <ArrowUpRight className="h-3.5 w-3.5" strokeWidth={2.25} aria-hidden />
          </button>
        </div>
      )}

      {filtered.length === 0 ? (
        <div className="rounded-lg border border-dashed border-rule bg-paper px-6 py-12 text-center">
          <div className="mb-1 text-base font-semibold text-deep">{emptyTitle}</div>
          <div className="text-sm text-mute">{emptyBody}</div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filtered.map((p) => {
            const id = p.productId ?? p.id ?? ''
            return (
              <ProductCard
                key={id}
                product={p}
                selected={selected.has(id)}
                onSelectedChange={(next) => toggle(id, next)}
                onPublish={status === 'pending' ? () => onPublish([id]) : undefined}
                onEdit={status === 'pending' && onEditProduct ? () => onEditProduct(p) : undefined}
                leaving={leavingIds.has(id)}
                entering={enteringIds.has(id)}
              />
            )
          })}
        </div>
      )}
    </section>
  )
}
