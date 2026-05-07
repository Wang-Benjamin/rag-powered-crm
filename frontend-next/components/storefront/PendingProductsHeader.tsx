'use client'

/**
 * Standalone "Import products" section for the 待上线 tab.
 *
 * One unified upload tile accepts PDF, CSV, and XLSX — the
 * `<ProductCatalogReviewDialog>` runs in `kind='auto'` mode and resolves
 * the ingestion lane from the chosen file's extension. The manual-add
 * affordance stays as a tertiary action in the section header so it
 * doesn't compete with the primary import flow.
 */

import { Plus, Upload } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { useState } from 'react'
import { ProductCatalogReviewDialog } from '@/components/onboarding/customize-ai/ingestion/ProductCatalogReviewDialog'

export function PendingProductsHeader({
  onAddManual,
  onCommitted,
}: {
  onAddManual: () => void
  onCommitted: (insertedCount: number) => void
}) {
  const t = useTranslations('storefront.pendingHeader')
  const [open, setOpen] = useState(false)

  return (
    <section className="mb-6 rounded-lg border border-zinc-200 bg-white p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-zinc-900">{t('sectionTitle')}</h2>
          <p className="mt-1 text-sm text-zinc-500">{t('sectionHelper')}</p>
        </div>
        <button
          type="button"
          onClick={onAddManual}
          className="inline-flex items-center gap-1 rounded-md border border-zinc-200 bg-white px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
        >
          <Plus className="h-3.5 w-3.5" strokeWidth={2} />
          <span>{t('addManual')}</span>
        </button>
      </div>

      <button
        type="button"
        onClick={() => setOpen(true)}
        className="group flex w-full items-center gap-4 rounded-md border border-zinc-200 bg-zinc-50 px-5 py-4 text-left transition-colors hover:border-zinc-300 hover:bg-white"
      >
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-white text-zinc-500 ring-1 ring-zinc-200 group-hover:text-zinc-900">
          <Upload className="h-5 w-5" strokeWidth={1.75} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium text-zinc-900">{t('upload.label')}</span>
          <span className="mt-0.5 block text-xs text-zinc-500">{t('upload.helper')}</span>
        </span>
        <span className="hidden text-[11px] font-medium uppercase tracking-wide text-zinc-400 sm:inline">
          {t('upload.formats')}
        </span>
      </button>

      <ProductCatalogReviewDialog
        open={open}
        onOpenChange={setOpen}
        kind="auto"
        onCommitted={(count) => {
          setOpen(false)
          onCommitted(count)
        }}
      />
    </section>
  )
}
