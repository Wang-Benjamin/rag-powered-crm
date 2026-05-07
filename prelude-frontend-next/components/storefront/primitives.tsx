'use client'

import { ChevronRight, Upload, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'

export function SectionShell({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <section className="mb-6 rounded-lg border border-rule bg-bone p-6">
      <div className="mb-4">
        <h2 className="text-xl font-semibold text-deep">{title}</h2>
      </div>
      {children}
    </section>
  )
}

function Dropzone({
  label,
  helper,
  cta,
}: {
  label: string
  helper: string
  cta: string
}) {
  // Visual-only placeholder until uploads are wired (no save endpoint exists
  // for the storefront draft yet). No tabIndex / role — the element does not
  // accept input, so it must not advertise itself as keyboard-operable.
  return (
    <div
      aria-hidden="true"
      className="group flex items-center gap-4 rounded-lg border border-dashed border-rule bg-paper px-5 py-4"
    >
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-rule bg-bone text-mute">
        <Upload className="h-4 w-4" strokeWidth={1.5} />
      </div>
      <div className="flex min-w-0 flex-1 flex-col">
        <span className="text-sm font-medium text-deep">{label}</span>
        <span className="text-xs text-mute">{helper}</span>
      </div>
      <span className="rounded-md border border-rule bg-bone px-3 py-1.5 text-xs font-medium text-ink group-hover:bg-cream">
        {cta}
      </span>
    </div>
  )
}

function FileChip({
  name,
  size,
  onRemove,
  removeAriaLabel,
}: {
  name: string
  size: string
  onRemove: () => void
  removeAriaLabel: string
}) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-rule bg-paper py-1 pr-1 pl-3">
      <span className="text-xs font-medium text-deep">{name}</span>
      <span className="text-[11px] text-mute">{size}</span>
      <button
        type="button"
        onClick={onRemove}
        aria-label={removeAriaLabel}
        className="flex h-5 w-5 items-center justify-center rounded-full text-mute hover:bg-rule hover:text-deep"
      >
        <X className="h-3 w-3" strokeWidth={2.5} />
      </button>
    </span>
  )
}

export function Disclosure({
  trigger,
  children,
}: {
  trigger: string
  children: ReactNode
}) {
  const [open, setOpen] = useState(false)
  return (
    <div className="mt-4">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-1.5 text-xs font-medium text-mute hover:text-deep"
      >
        <ChevronRight
          className={`h-3.5 w-3.5 transition-transform ${open ? 'rotate-90' : ''}`}
          strokeWidth={2.25}
        />
        {trigger}
      </button>
      {open && <div className="mt-4">{children}</div>}
    </div>
  )
}

export function Field({
  label,
  htmlFor,
  full,
  children,
}: {
  label: string
  htmlFor?: string
  full?: boolean
  children: ReactNode
}) {
  return (
    <div className={full ? 'sm:col-span-2' : ''}>
      <label
        htmlFor={htmlFor}
        className="mb-1.5 block text-sm font-medium text-ink"
      >
        {label}
      </label>
      {children}
    </div>
  )
}

export function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`w-full rounded-md border border-rule bg-bone px-3 py-2 text-sm text-ink placeholder:text-mute focus:border-deep focus:ring-2 focus:ring-deep/20 focus:outline-none ${
        props.className ?? ''
      }`}
    />
  )
}

export function TextArea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={`w-full resize-y rounded-md border border-rule bg-bone px-3 py-2 text-sm text-ink placeholder:text-mute focus:border-deep focus:ring-2 focus:ring-deep/20 focus:outline-none ${
        props.className ?? ''
      }`}
    />
  )
}

export function Notice({ children }: { children: ReactNode }) {
  return (
    <div className="mb-4 rounded-md border border-gold/30 bg-gold-lo px-4 py-2.5 text-xs text-ink">
      {children}
    </div>
  )
}

export function FieldRow({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">{children}</div>
}
