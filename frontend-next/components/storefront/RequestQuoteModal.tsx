'use client'

import { X } from 'lucide-react'
import { useEffect, useState } from 'react'

export interface QuoteRequestPayload {
  email: string
  name?: string
  company?: string
  quantity?: number
  message?: string
  productName: string
  productSku?: string
}

export interface RequestQuoteModalLabels {
  title: string
  subtitle: string
  yourName: string
  yourNamePlaceholder: string
  company: string
  companyPlaceholder: string
  email: string
  emailPlaceholder: string
  emailRequired: string
  quantity: string
  quantityPlaceholder: string
  message: string
  messagePlaceholder: string
  submit: string
  submitting: string
  closeAriaLabel: string
  successTitle: string
  successBody: string
  errorGeneric: string
  errorRateLimited: string
}

export function RequestQuoteModal({
  open,
  onOpenChange,
  product,
  sellerName,
  labels,
  onSubmit,
}: {
  open: boolean
  onOpenChange: (next: boolean) => void
  product: { name: string; sku?: string } | null
  sellerName: string
  labels: RequestQuoteModalLabels
  onSubmit: (payload: QuoteRequestPayload) => Promise<void>
}) {
  const [form, setForm] = useState({
    name: '',
    company: '',
    email: '',
    quantity: '',
    message: '',
  })
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      setForm({ name: '', company: '', email: '', quantity: '', message: '' })
      setSubmitting(false)
      setSuccess(false)
      setError(null)
    }
  }, [open, product?.sku, product?.name])

  useEffect(() => {
    if (!success) return
    const t = window.setTimeout(() => onOpenChange(false), 2000)
    return () => window.clearTimeout(t)
  }, [success, onOpenChange])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onOpenChange(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onOpenChange])

  if (!open || !product) return null

  const subtitle = labels.subtitle.replace('{seller}', sellerName)
  const successBody = labels.successBody.replace('{seller}', sellerName)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (submitting || !form.email) return
    setSubmitting(true)
    setError(null)
    try {
      const trimmedQty = form.quantity.replace(/[^0-9]/g, '')
      const qty = trimmedQty ? parseInt(trimmedQty, 10) : undefined
      await onSubmit({
        email: form.email.trim(),
        name: form.name.trim() || undefined,
        company: form.company.trim() || undefined,
        quantity: Number.isFinite(qty) ? qty : undefined,
        message: form.message.trim() || undefined,
        productName: product.name,
        productSku: product.sku,
      })
      setSuccess(true)
    } catch (err) {
      const msg =
        err instanceof Error && err.message === 'rate_limited'
          ? labels.errorRateLimited
          : labels.errorGeneric
      setError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  const inputClass =
    'w-full rounded-md border border-rule bg-bone px-3 py-2.5 text-sm text-deep placeholder:text-mute focus:border-accent focus:ring-2 focus:ring-accent/30 focus:outline-none'
  const labelClass =
    'mb-1.5 block text-[11px] font-medium uppercase tracking-[0.12em] text-mute'

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center sm:items-center"
      onClick={() => onOpenChange(false)}
    >
      <div className="absolute inset-0 bg-deep/60 backdrop-blur-sm" />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="request-quote-title"
        className="relative max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-t-2xl border border-rule bg-bone p-6 shadow-2xl sm:rounded-2xl sm:p-8"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          aria-label={labels.closeAriaLabel}
          onClick={() => onOpenChange(false)}
          className="absolute top-4 right-4 rounded-sm text-mute transition-colors hover:text-deep focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          <X className="h-4 w-4" />
        </button>

        {success ? (
          <div className="py-6 text-center">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-accent-lo">
              <svg
                className="h-7 w-7 text-accent"
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
            <h3
              id="request-quote-title"
              className="mb-1.5 title-page"
            >
              {labels.successTitle}
            </h3>
            <p className="text-sm text-mute">{successBody}</p>
          </div>
        ) : (
          <>
            <div className="mb-5">
              <h3
                id="request-quote-title"
                className="title-page"
              >
                {labels.title}
              </h3>
              <p className="mt-1 text-sm text-mute">{subtitle}</p>
              <p className="mt-2 text-xs font-medium uppercase tracking-[0.12em] text-mute">
                {product.name}
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label className={labelClass}>{labels.yourName}</label>
                  <input
                    type="text"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    placeholder={labels.yourNamePlaceholder}
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className={labelClass}>{labels.company}</label>
                  <input
                    type="text"
                    value={form.company}
                    onChange={(e) => setForm({ ...form, company: e.target.value })}
                    placeholder={labels.companyPlaceholder}
                    className={inputClass}
                  />
                </div>
              </div>

              <div>
                <div className="mb-1.5 flex items-baseline justify-between">
                  <label className={labelClass + ' mb-0'}>{labels.email}</label>
                  <span className="text-[10px] font-medium uppercase tracking-wider text-accent">
                    {labels.emailRequired}
                  </span>
                </div>
                <input
                  type="email"
                  required
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  placeholder={labels.emailPlaceholder}
                  className={inputClass}
                />
              </div>

              <div>
                <label className={labelClass}>{labels.quantity}</label>
                <input
                  type="text"
                  inputMode="numeric"
                  value={form.quantity}
                  onChange={(e) => setForm({ ...form, quantity: e.target.value })}
                  placeholder={labels.quantityPlaceholder}
                  className={inputClass}
                />
              </div>

              <div>
                <label className={labelClass}>{labels.message}</label>
                <textarea
                  rows={3}
                  value={form.message}
                  onChange={(e) => setForm({ ...form, message: e.target.value })}
                  placeholder={labels.messagePlaceholder}
                  className={inputClass + ' resize-none'}
                />
              </div>

              {error && (
                <div className="rounded-md border border-threat/30 bg-threat/5 px-3 py-2 text-xs text-threat">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={submitting || !form.email}
                className="w-full rounded-md bg-accent px-4 py-3 text-sm font-medium text-bone transition-colors hover:bg-accent-hi focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bone disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? labels.submitting : labels.submit}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  )
}
