'use client'

/**
 * Single-row product edit modal.
 *
 * Used by the storefront 待上线 tab for both manual add (`mode='create'`)
 * and per-row edit (`mode='edit'`). Mirrors the field UX of
 * `<ProductCatalogReviewTable>` but for one row at a time so we don't have
 * to hide the table's add/remove affordances. Specs render as a free-form
 * textarea (one `key: value` per line) — pretty good ergonomics for the
 * tail end of catalog entries that ingestion didn't extract.
 */

import { Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useTranslations } from 'next-intl'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Select, SelectItem } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import type { PriceRange } from '@/components/onboarding/customize-ai/ingestion/types'
import type { ProductCatalogInput } from '@/lib/api/productCatalog'
import type { Product } from './types'

const CURRENCY_OPTIONS = ['USD', 'EUR', 'CNY', 'GBP', 'JPY', 'HKD']
const UNIT_OPTIONS = ['piece', 'pair', 'set', 'carton', 'kg', 'meter', 'box']

type Mode = 'create' | 'edit'

interface ProductEditDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  mode: Mode
  initial?: Product | null
  onSubmit: (input: ProductCatalogInput) => Promise<void>
  /** Only used in `mode='edit'` — wires up the destructive delete action. */
  onDelete?: (product: Product) => Promise<void>
}

interface FormState {
  name: string
  description: string
  imageUrl: string
  moq: string
  hsCode: string
  specsText: string
  priceMin: string
  priceMax: string
  currency: string
  unit: string
}

const EMPTY_FORM: FormState = {
  name: '',
  description: '',
  imageUrl: '',
  moq: '',
  hsCode: '',
  specsText: '',
  priceMin: '',
  priceMax: '',
  currency: 'USD',
  unit: 'piece',
}

function specsToText(specs?: Record<string, string>): string {
  if (!specs) return ''
  return Object.entries(specs)
    .filter(([k]) => k.trim() !== '')
    .map(([k, v]) => `${k}: ${v}`)
    .join('\n')
}

function textToSpecs(text: string): Record<string, string> {
  const out: Record<string, string> = {}
  for (const line of text.split('\n')) {
    const trimmed = line.trim()
    if (!trimmed) continue
    const colon = trimmed.indexOf(':')
    if (colon < 0) continue
    const k = trimmed.slice(0, colon).trim()
    const v = trimmed.slice(colon + 1).trim()
    if (k && v) out[k] = v
  }
  return out
}

function fromProduct(p: Product | null | undefined): FormState {
  if (!p) return EMPTY_FORM
  return {
    name: p.name ?? '',
    description: p.description ?? '',
    imageUrl: p.imageUrl ?? '',
    moq: p.moq != null ? String(p.moq) : '',
    hsCode: p.hsCode ?? '',
    specsText: specsToText(p.specs),
    priceMin: p.priceRange?.min != null ? String(p.priceRange.min) : '',
    priceMax: p.priceRange?.max != null ? String(p.priceRange.max) : '',
    currency: p.priceRange?.currency ?? 'USD',
    unit: p.priceRange?.unit ?? 'piece',
  }
}

export function ProductEditDialog({
  open,
  onOpenChange,
  mode,
  initial,
  onSubmit,
  onDelete,
}: ProductEditDialogProps) {
  const t = useTranslations('storefront.productEditDialog')

  const [form, setForm] = useState<FormState>(() => fromProduct(initial))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)

  // Re-seed when the dialog (re-)opens with a (possibly different) row.
  useEffect(() => {
    if (open) {
      setForm(fromProduct(initial))
      setError(null)
      setConfirmDeleteOpen(false)
    }
  }, [open, initial])

  const update = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }))

  const currencyOptions = useMemo(
    () => (CURRENCY_OPTIONS.includes(form.currency) ? CURRENCY_OPTIONS : [form.currency, ...CURRENCY_OPTIONS]),
    [form.currency],
  )
  const unitOptions = useMemo(
    () => (UNIT_OPTIONS.includes(form.unit) ? UNIT_OPTIONS : [form.unit, ...UNIT_OPTIONS]),
    [form.unit],
  )

  const handleSave = async () => {
    if (form.name.trim() === '') {
      setError(t('validation.nameRequired'))
      return
    }
    setSaving(true)
    setError(null)
    try {
      const moqValue = form.moq.trim() === '' ? null : Number(form.moq)
      const minValue = form.priceMin.trim() === '' ? undefined : Number(form.priceMin)
      const maxValue = form.priceMax.trim() === '' ? undefined : Number(form.priceMax)
      const hasPrice = minValue !== undefined || maxValue !== undefined
      const priceRange: PriceRange | null = hasPrice
        ? {
            min: minValue,
            max: maxValue,
            currency: form.currency,
            unit: form.unit,
          }
        : null

      await onSubmit({
        name: form.name.trim(),
        description: form.description.trim() || null,
        imageUrl: form.imageUrl.trim() || null,
        moq: moqValue,
        hsCode: form.hsCode.trim() || null,
        specs: textToSpecs(form.specsText),
        priceRange,
      })
      onOpenChange(false)
    } catch (e) {
      console.error('product save failed', e)
      setError(t('errorGeneric'))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!initial || !onDelete) return
    setDeleting(true)
    try {
      await onDelete(initial)
      setConfirmDeleteOpen(false)
      onOpenChange(false)
    } catch (e) {
      console.error('product delete failed', e)
      setError(t('errorDelete'))
      setConfirmDeleteOpen(false)
    } finally {
      setDeleting(false)
    }
  }

  const title = mode === 'create' ? t('titleCreate') : t('titleEdit')
  const canDelete = mode === 'edit' && Boolean(onDelete) && Boolean(initial)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] w-[min(640px,95vw)] max-w-[640px] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <Field label={t('fields.name')} required>
            <Input
              value={form.name}
              onChange={(e) => update('name', e.target.value)}
              autoFocus
              maxLength={500}
            />
          </Field>

          <Field label={t('fields.description')}>
            <Textarea
              value={form.description}
              onChange={(e) => update('description', e.target.value)}
              rows={3}
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label={t('fields.moq')}>
              <Input
                type="number"
                inputMode="numeric"
                value={form.moq}
                onChange={(e) => update('moq', e.target.value)}
              />
            </Field>
            <Field label={t('fields.hsCode')}>
              <Input
                value={form.hsCode}
                onChange={(e) => update('hsCode', e.target.value)}
                maxLength={16}
              />
            </Field>
          </div>

          <Field label={t('fields.priceRange')}>
            <div className="flex flex-wrap items-center gap-2">
              <Input
                type="number"
                inputMode="decimal"
                step="0.01"
                value={form.priceMin}
                onChange={(e) => update('priceMin', e.target.value)}
                placeholder={t('fields.priceMinPlaceholder')}
                className="w-24"
              />
              <span className="text-zinc-400">–</span>
              <Input
                type="number"
                inputMode="decimal"
                step="0.01"
                value={form.priceMax}
                onChange={(e) => update('priceMax', e.target.value)}
                placeholder={t('fields.priceMaxPlaceholder')}
                className="w-24"
              />
              <Select
                size="sm"
                value={form.currency}
                onValueChange={(next) => update('currency', next)}
                className="w-[80px]"
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
                value={form.unit}
                onValueChange={(next) => update('unit', next)}
                className="w-[100px]"
              >
                {unitOptions.map((u) => (
                  <SelectItem key={u} value={u}>
                    {u}
                  </SelectItem>
                ))}
              </Select>
            </div>
          </Field>

          <Field label={t('fields.imageUrl')} hint={t('fields.imageUrlHint')}>
            <Input
              value={form.imageUrl}
              onChange={(e) => update('imageUrl', e.target.value)}
              placeholder="https://"
            />
          </Field>

          <Field label={t('fields.specs')} hint={t('fields.specsHint')}>
            <Textarea
              value={form.specsText}
              onChange={(e) => update('specsText', e.target.value)}
              rows={4}
              placeholder={t('fields.specsPlaceholder')}
            />
          </Field>

          {error && <div className="text-sm text-red-600">{error}</div>}
        </div>

        <DialogFooter className="mt-2 flex flex-row items-center justify-between gap-2 sm:justify-between">
          {canDelete ? (
            <button
              type="button"
              onClick={() => setConfirmDeleteOpen(true)}
              disabled={saving || deleting}
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm font-medium text-zinc-500 transition-colors hover:text-red-600 disabled:opacity-50"
            >
              <Trash2 className="h-4 w-4" strokeWidth={1.75} />
              <span>{t('delete')}</span>
            </button>
          ) : (
            <span />
          )}

          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={saving || deleting}
            >
              {t('cancel')}
            </Button>
            <Button type="button" onClick={handleSave} disabled={saving || deleting}>
              {saving ? t('saving') : t('save')}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>

      <AlertDialog open={confirmDeleteOpen} onOpenChange={setConfirmDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('confirmDelete.title')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('confirmDelete.body', { name: initial?.name ?? '' })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel
              onClick={() => setConfirmDeleteOpen(false)}
              disabled={deleting}
            >
              {t('confirmDelete.cancel')}
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={deleting}
              className="bg-red-600 text-white hover:bg-red-700"
            >
              {deleting ? t('confirmDelete.deleting') : t('confirmDelete.confirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Dialog>
  )
}

function Field({
  label,
  required,
  hint,
  children,
}: {
  label: string
  required?: boolean
  hint?: string
  children: React.ReactNode
}) {
  return (
    <label className="block">
      <div className="mb-1 text-xs font-medium text-zinc-700">
        {label}
        {required && <span className="ml-0.5 text-red-500">*</span>}
      </div>
      {children}
      {hint && <div className="mt-1 text-[11px] text-zinc-500">{hint}</div>}
    </label>
  )
}
