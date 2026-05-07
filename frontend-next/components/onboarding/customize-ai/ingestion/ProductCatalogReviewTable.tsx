'use client'

/**
 * Editable product catalog review table.
 *
 * Introduced for M5 (product PDF lane) and reused by M6 (product CSV).
 * Controlled component: parent owns the `products` array + `onChange`. The
 * dialog/parent wires the draft from the dropzone's ready payload and calls
 * `ingestionApi.commit` on Save.
 *
 * Kind-agnostic: rows come in with or without `imageUrl`. Missing images
 * show an "Upload image" placeholder per row, matching the scope-cut path
 * in DOC_INGESTION_CODING_PLAN §6.5.
 */

import { useCallback, useRef, useState } from 'react'
import { useTranslations } from 'next-intl'
import { ImageIcon, Plus, Trash2, Upload } from 'lucide-react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectItem } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/utils/cn'
import type { ProductRecordDraft } from './types'

const CURRENCY_OPTIONS = ['USD', 'EUR', 'CNY', 'GBP', 'JPY', 'HKD']
const UNIT_OPTIONS = ['piece', 'pair', 'set', 'carton', 'kg', 'meter', 'box']

interface ProductCatalogReviewTableProps {
  products: ProductRecordDraft[]
  onChange: (products: ProductRecordDraft[]) => void
  /** Optional per-row image-upload hook; omit to hide the upload button. */
  onUploadImage?: (rowIndex: number, file: File) => Promise<string | null>
  className?: string
}

export function ProductCatalogReviewTable({
  products,
  onChange,
  onUploadImage,
  className,
}: ProductCatalogReviewTableProps) {
  const t = useTranslations('settings.customizeAi.ingestion.productReview')
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [uploadingRow, setUploadingRow] = useState<number | null>(null)
  const fileInputs = useRef<Record<number, HTMLInputElement | null>>({})

  const updateRow = useCallback(
    (idx: number, patch: Partial<ProductRecordDraft>) => {
      const next = products.map((p, i) => (i === idx ? { ...p, ...patch } : p))
      onChange(next)
    },
    [products, onChange],
  )

  const removeRow = useCallback(
    (idx: number) => onChange(products.filter((_, i) => i !== idx)),
    [products, onChange],
  )

  const addRow = useCallback(
    () => onChange([...products, { name: '' }]),
    [products, onChange],
  )

  const handleImageFile = useCallback(
    async (idx: number, file: File) => {
      if (!onUploadImage) return
      setUploadingRow(idx)
      try {
        const url = await onUploadImage(idx, file)
        if (url) updateRow(idx, { imageUrl: url })
      } finally {
        setUploadingRow(null)
      }
    },
    [onUploadImage, updateRow],
  )

  if (products.length === 0) {
    return (
      <div
        className={cn(
          'rounded-md border border-dashed border-zinc-300 bg-zinc-50 p-8 text-center text-sm text-zinc-600',
          className,
        )}
      >
        {t('emptyState')}
      </div>
    )
  }

  return (
    <div className={cn('overflow-hidden rounded-md border border-zinc-200', className)}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[880px] text-sm">
          <thead className="bg-zinc-50 text-left text-xs font-medium tracking-wide text-zinc-600 uppercase">
            <tr>
              <th className="w-20 px-3 py-2">{t('columns.image')}</th>
              <th className="px-3 py-2">{t('columns.name')}</th>
              <th className="px-3 py-2">{t('columns.price')}</th>
              <th className="px-3 py-2">{t('columns.moq')}</th>
              <th className="px-3 py-2">{t('columns.description')}</th>
              <th className="px-3 py-2">{t('columns.specs')}</th>
              <th className="w-10 px-3 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100 bg-white">
            {products.map((p, idx) => (
              <tr key={idx} className="align-top">
                <td className="px-3 py-2">
                  {p.imageUrl ? (
                    <button
                      type="button"
                      className="group relative block h-16 w-16 overflow-hidden rounded-md border border-zinc-200 focus:outline-none focus:ring-2 focus:ring-zinc-900"
                      onClick={() => setPreviewUrl(p.imageUrl ?? null)}
                      aria-label={t('previewTitle')}
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={p.imageUrl}
                        alt={p.name || ''}
                        className="h-full w-full object-cover transition-opacity group-hover:opacity-90"
                      />
                    </button>
                  ) : (
                    <div className="flex h-16 w-16 flex-col items-center justify-center rounded-md border border-dashed border-zinc-300 bg-zinc-50 text-zinc-500">
                      <ImageIcon className="h-4 w-4" />
                      <span className="mt-0.5 text-[10px] leading-none">{t('noImage')}</span>
                    </div>
                  )}
                  {onUploadImage ? (
                    <>
                      <input
                        ref={(el) => {
                          fileInputs.current[idx] = el
                        }}
                        type="file"
                        accept="image/png,image/jpeg,image/webp"
                        className="hidden"
                        onChange={(e) => {
                          const f = e.target.files?.[0]
                          if (f) void handleImageFile(idx, f)
                          e.target.value = ''
                        }}
                      />
                      <button
                        type="button"
                        onClick={() => fileInputs.current[idx]?.click()}
                        className="mt-1 flex items-center gap-1 text-[11px] text-zinc-600 hover:text-zinc-900 disabled:opacity-50"
                        disabled={uploadingRow === idx}
                      >
                        <Upload className="h-3 w-3" />
                        {uploadingRow === idx ? '…' : t('uploadImage')}
                      </button>
                    </>
                  ) : null}
                </td>
                <td className="px-3 py-2">
                  <Input
                    value={p.name ?? ''}
                    onChange={(e) => updateRow(idx, { name: e.target.value })}
                    className="h-8"
                  />
                </td>
                <td className="px-3 py-2">
                  <PriceCell
                    value={p.priceRange}
                    onChange={(priceRange) => updateRow(idx, { priceRange })}
                  />
                </td>
                <td className="px-3 py-2">
                  <Input
                    type="number"
                    inputMode="numeric"
                    value={p.moq ?? ''}
                    onChange={(e) => {
                      const v = e.target.value
                      updateRow(idx, { moq: v === '' ? undefined : Number(v) })
                    }}
                    className="h-8 w-24"
                  />
                </td>
                <td className="px-3 py-2">
                  <Textarea
                    value={p.description ?? ''}
                    onChange={(e) =>
                      updateRow(idx, { description: e.target.value || undefined })
                    }
                    rows={2}
                    className="min-h-[2.5rem] text-sm"
                  />
                </td>
                <td className="px-3 py-2">
                  <SpecsBadge specs={p.specs} />
                </td>
                <td className="px-3 py-2">
                  <button
                    type="button"
                    onClick={() => removeRow(idx)}
                    className="rounded-md p-1.5 text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900"
                    aria-label={t('remove')}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="border-t border-zinc-200 bg-zinc-50 px-3 py-2">
        <Button type="button" variant="outline" size="sm" onClick={addRow}>
          <Plus className="mr-1 h-4 w-4" />
          {t('addRow')}
        </Button>
      </div>

      <Dialog open={previewUrl !== null} onOpenChange={(o) => !o && setPreviewUrl(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="title-page">{t('previewTitle')}</DialogTitle>
          </DialogHeader>
          {previewUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={previewUrl} alt="" className="max-h-[70vh] w-full object-contain" />
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  )
}

function PriceCell({
  value,
  onChange,
}: {
  value: ProductRecordDraft['priceRange']
  onChange: (v: ProductRecordDraft['priceRange']) => void
}) {
  const pr = value ?? { min: undefined, max: undefined, currency: 'USD', unit: 'piece' }
  const currency = pr.currency ?? 'USD'
  const unit = pr.unit ?? 'piece'
  const currencyOptions = CURRENCY_OPTIONS.includes(currency)
    ? CURRENCY_OPTIONS
    : [currency, ...CURRENCY_OPTIONS]
  const unitOptions = UNIT_OPTIONS.includes(unit) ? UNIT_OPTIONS : [unit, ...UNIT_OPTIONS]

  return (
    <div className="flex items-center gap-1">
      <Input
        type="number"
        inputMode="decimal"
        step="0.01"
        value={pr.min ?? ''}
        onChange={(e) => {
          const v = e.target.value
          onChange({ ...pr, min: v === '' ? undefined : Number(v), currency, unit })
        }}
        placeholder="min"
        className="h-8 w-16 text-right tabular-nums"
      />
      <span className="text-zinc-400">–</span>
      <Input
        type="number"
        inputMode="decimal"
        step="0.01"
        value={pr.max ?? ''}
        onChange={(e) => {
          const v = e.target.value
          onChange({ ...pr, max: v === '' ? undefined : Number(v), currency, unit })
        }}
        placeholder="max"
        className="h-8 w-16 text-right tabular-nums"
      />
      <Select
        size="sm"
        value={currency}
        onValueChange={(next) => onChange({ ...pr, currency: next, unit })}
        className="w-[70px]"
      >
        {currencyOptions.map((c) => (
          <SelectItem key={c} value={c}>
            {c}
          </SelectItem>
        ))}
      </Select>
      <span className="text-xs text-zinc-400">/</span>
      <Select
        size="sm"
        value={unit}
        onValueChange={(next) => onChange({ ...pr, unit: next, currency })}
        className="w-[82px]"
      >
        {unitOptions.map((u) => (
          <SelectItem key={u} value={u}>
            {u}
          </SelectItem>
        ))}
      </Select>
    </div>
  )
}

function SpecsBadge({ specs }: { specs?: Record<string, string> }) {
  const t = useTranslations('settings.customizeAi.ingestion.productReview')
  const entries = Object.entries(specs ?? {}).filter(([k, v]) => k && v)
  if (entries.length === 0) {
    return <span className="text-xs text-zinc-400">{t('specsCount', { count: 0 })}</span>
  }
  return (
    <details className="text-xs text-zinc-700">
      <summary className="cursor-pointer list-none select-none underline-offset-2 hover:underline">
        {t('specsCount', { count: entries.length })}
      </summary>
      <ul className="mt-1 space-y-0.5">
        {entries.map(([k, v]) => (
          <li key={k}>
            <span className="text-zinc-500">{k}:</span> {v}
          </li>
        ))}
      </ul>
    </details>
  )
}
