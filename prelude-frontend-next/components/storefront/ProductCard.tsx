'use client'

import { Check } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { ProductMedia } from './ProductMedia'
import type { Product } from './types'

// Seller-side product card. The buyer-facing storefront uses an inline card
// inside `PublicStorefrontView` and does NOT pass through here.
export function ProductCard({
  product,
  selected,
  onSelectedChange,
  onPublish,
  onEdit,
  leaving,
  entering,
}: {
  product: Product
  selected: boolean
  onSelectedChange: (next: boolean) => void
  onPublish?: () => void
  onEdit?: () => void
  leaving?: boolean
  entering?: boolean
}) {
  const t = useTranslations('storefront')

  // Catalog rows surface a lean `name`; the legacy mock path uses `nameEn`.
  // Falling back keeps this card readable in both shapes until the buyer
  // mock is replaced by the real publish pipeline.
  const displayName = product.name ?? product.nameEn ?? ''

  // Specs render as a comma-joined "key: value" line under the title. The
  // ingestion lanes drop arbitrary keys here (Material, Outsole, …); manual
  // adds typically leave it empty. Falls back to the description so the card
  // is never blank for rows where neither is set.
  const specEntries = Object.entries(product.specs ?? {}).filter(
    ([, value]) => value && value.toString().trim().length > 0,
  )
  const specLine = specEntries.length > 0
    ? specEntries.map(([k, v]) => `${k}: ${v}`).join(' · ')
    : (product.description ?? '')

  const moqLine =
    typeof product.moq === 'number' && product.moq > 0
      ? t('productCard.moqPrefix', { moq: product.moq.toLocaleString() })
      : null

  return (
    <article
      className={`group relative flex flex-col overflow-hidden rounded-lg border bg-bone transition-all duration-200 ${
        selected
          ? 'border-deep ring-2 ring-deep/20'
          : 'border-rule hover:-translate-y-[1px] hover:shadow-sm'
      } ${leaving ? 'scale-[0.98] opacity-0' : ''} ${
        entering ? 'animate-[pc-enter_0.3s_ease]' : ''
      }`}
      style={{ transition: 'opacity 0.26s ease, transform 0.26s ease, box-shadow 0.2s ease' }}
    >
      <label
        className={`absolute top-2 left-2 z-10 flex h-6 w-6 cursor-pointer items-center justify-center rounded-md border bg-bone/95 backdrop-blur transition-opacity ${
          selected
            ? 'border-deep opacity-100'
            : 'border-rule opacity-0 group-hover:opacity-100 focus-within:opacity-100'
        }`}
      >
        <input
          type="checkbox"
          className="sr-only"
          aria-label={t('productCard.selectAriaLabel')}
          checked={selected}
          onChange={(e) => onSelectedChange(e.target.checked)}
        />
        {selected && <Check className="h-3.5 w-3.5 text-deep" strokeWidth={3} />}
      </label>

      <ProductMedia imageUrl={product.imageUrl} alt={displayName} />

      <div className="flex flex-1 flex-col gap-2 px-5 py-4">
        <div>
          <h3 className="text-base font-semibold leading-snug text-deep">{displayName}</h3>
        </div>
        {specLine && <div className="text-xs text-ink line-clamp-3">{specLine}</div>}
        {moqLine && <div className="text-[11px] text-mute">{moqLine}</div>}
        {product.status === 'live' && product.publishedAt && (
          <div className="mt-auto text-[11px] text-mute/80">
            {t('productCard.publishedPrefix')} {formatPublishedAt(product.publishedAt)}
          </div>
        )}
      </div>

      <div className="flex items-center justify-end gap-2 border-t border-rule px-4 py-3">
        {onEdit && (
          <button
            type="button"
            onClick={onEdit}
            className="rounded-md px-3 py-1.5 text-sm font-medium text-mute hover:bg-cream hover:text-deep"
          >
            {t('productCard.edit')}
          </button>
        )}
        {product.status === 'pending' && onPublish && (
          <button
            type="button"
            onClick={onPublish}
            className="rounded-md px-3 py-1.5 text-sm font-medium text-mute hover:bg-cream hover:text-deep disabled:opacity-60"
          >
            {t('productCard.publish')}
          </button>
        )}
      </div>
    </article>
  )
}

function formatPublishedAt(iso: string): string {
  // Accept either a date-only string ("2026-04-12") or a full ISO timestamp.
  // The buyer-side mock returns date-only; the real backend returns an ISO
  // timestamp from `published_at`. Either way we want YYYY-MM-DD on the card.
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) return iso
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toISOString().slice(0, 10)
}
