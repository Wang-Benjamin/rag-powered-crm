'use client'

import React from 'react'
import { useTranslations } from 'next-intl'

// ─────────────────────────────────────────────────────────────
// Shared Tailwind className strings
// ─────────────────────────────────────────────────────────────

export const ssoBtnCls =
  'group relative grid grid-cols-[28px_1fr_auto] items-center gap-3.5 h-[52px] px-[18px] ' +
  'bg-bone border border-rule rounded-lg text-left text-[14.5px] font-medium text-ink ' +
  'transition-[background-color,border-color,transform,color] duration-200 ' +
  'hover:bg-cream hover:border-ink ' +
  'focus-visible:outline-none focus-visible:border-accent focus-visible:shadow-[0_0_0_3px_var(--accent-lo)] ' +
  'aria-busy:cursor-progress aria-busy:text-mute ' +
  'disabled:opacity-55 disabled:cursor-not-allowed'

export const primaryCtaCls =
  'w-full inline-flex items-center justify-center gap-2.5 h-[52px] px-5 ' +
  'bg-deep text-bone border border-deep rounded-lg ' +
  'text-[15px] font-medium tracking-[-0.005em] ' +
  'transition-[background-color,border-color,transform] duration-200 ' +
  'hover:bg-accent hover:border-accent hover:-translate-y-px ' +
  'focus-visible:outline-none focus-visible:border-accent focus-visible:shadow-[0_0_0_3px_var(--accent-lo)] ' +
  'aria-busy:bg-ink aria-busy:border-ink aria-busy:cursor-progress aria-busy:transform-none ' +
  'disabled:opacity-55 disabled:cursor-not-allowed ' +
  'motion-reduce:hover:transform-none'

export const inputCls =
  'w-full h-12 px-4 bg-bone border border-rule rounded-lg ' +
  'text-[14.5px] text-ink placeholder:text-[color:color-mix(in_oklab,var(--mute)_70%,transparent)] ' +
  'transition-[border-color,box-shadow,background-color] duration-200 ' +
  'hover:border-[color:color-mix(in_oklab,var(--ink)_30%,var(--rule))] ' +
  'focus:outline-none focus:border-accent focus:shadow-[0_0_0_3px_var(--accent-lo)]'

export const fldLabelCls =
  'font-mono text-[10.5px] font-medium tracking-[0.16em] uppercase text-mute'

export const smallSpinnerCls =
  'inline-block w-[14px] h-[14px] rounded-full border-[1.5px] border-[color:color-mix(in_oklab,var(--mute)_30%,transparent)] border-t-accent animate-[spin_0.8s_linear_infinite]'

export const smallSpinnerOnDeepCls =
  'inline-block w-[14px] h-[14px] rounded-full border-[1.5px] border-[color:color-mix(in_oklab,var(--bone)_25%,transparent)] border-t-bone animate-[spin_0.8s_linear_infinite]'

export const largeSpinnerCls =
  'w-10 h-10 rounded-full border-2 border-[color:color-mix(in_oklab,var(--rule)_80%,transparent)] border-t-accent animate-[spin_0.9s_linear_infinite] motion-reduce:animate-none'

export const pcardBaseCls =
  'absolute z-[3] bg-bone border border-rule rounded-[14px] p-4 ' +
  'shadow-[0_14px_32px_-18px_oklch(0.25_0.02_260/0.22)] will-change-transform ' +
  'transition-[transform,box-shadow,border-color] duration-500 ' +
  'hover:border-ink hover:-translate-y-0.5 hover:scale-[1.01] ' +
  'hover:shadow-[0_20px_40px_-20px_oklch(0.25_0.02_260/0.3)] ' +
  'motion-reduce:animate-none'

export const pcardHdCls =
  'flex items-center gap-2 mb-2.5 font-mono text-[10px] font-medium tracking-[0.14em] uppercase text-mute whitespace-nowrap'

const authH1Cls = 'display display-s mb-3'

const backLinkCls =
  'group inline-flex items-center gap-1.5 py-1.5 mb-4.5 text-[13px] text-mute bg-transparent border-0 cursor-pointer ' +
  'transition-colors duration-200 ' +
  'hover:text-ink ' +
  'focus-visible:outline-none focus-visible:text-accent focus-visible:shadow-[0_0_0_3px_var(--accent-lo)] focus-visible:rounded'

// ─────────────────────────────────────────────────────────────
// Small SVG helpers
// ─────────────────────────────────────────────────────────────

export const ChevSvg = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="9 18 15 12 9 6" />
  </svg>
)

const BackArrowSvg = () => (
  <svg
    className="w-[14px] h-[14px] transition-transform duration-200 group-hover:-translate-x-0.5"
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M10 12 L6 8 L10 4" />
  </svg>
)

export const QrFrameCorners = () => (
  <>
    <span className="absolute top-2 left-2 w-[14px] h-[14px] border-[1.5px] border-accent border-r-0 border-b-0 rounded-tl-[4px] pointer-events-none" />
    <span className="absolute top-2 right-2 w-[14px] h-[14px] border-[1.5px] border-accent border-l-0 border-b-0 rounded-tr-[4px] pointer-events-none" />
    <span className="absolute bottom-2 left-2 w-[14px] h-[14px] border-[1.5px] border-accent border-r-0 border-t-0 rounded-bl-[4px] pointer-events-none" />
    <span className="absolute bottom-2 right-2 w-[14px] h-[14px] border-[1.5px] border-accent border-l-0 border-t-0 rounded-br-[4px] pointer-events-none" />
  </>
)

// ─────────────────────────────────────────────────────────────
// Shared presentational components
// ─────────────────────────────────────────────────────────────

export const H1Title = () => {
  const t = useTranslations('auth.login')
  return (
    <h1 className={authH1Cls}>
      {t.rich('title', {
        em: (chunks) => <em>{chunks}</em>,
      })}
    </h1>
  )
}

export const BackToMain = ({ onBack }: { onBack: () => void }) => {
  const t = useTranslations('auth.login')
  return (
    <button type="button" onClick={onBack} aria-label={t('backToOAuth')} className={backLinkCls}>
      <BackArrowSvg />
      {t('backToOAuth')}
    </button>
  )
}

export const ErrorBanner = ({ message }: { message: string | null | undefined }) => {
  if (!message) return null
  return (
    <div
      role="alert"
      className="flex items-start gap-2.5 p-3 mb-4.5 rounded-lg text-[13.5px] bg-threat-lo border border-[color:color-mix(in_oklab,var(--threat)_35%,var(--rule))] border-l-[3px] border-l-threat text-[color:color-mix(in_oklab,var(--threat),var(--deep)_10%)]"
    >
      <svg className="w-4 h-4 text-threat flex-none mt-px" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="8" x2="12" y2="12" />
        <line x1="12" y1="16" x2="12.01" y2="16" />
      </svg>
      <div>
        <b className="block font-medium text-threat">{message}</b>
      </div>
    </div>
  )
}

export const PasswordToggle = ({ show, onToggle }: { show: boolean; onToggle: () => void }) => {
  const t = useTranslations('auth.login')
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={show ? t('hidePassword') : t('showPassword')}
      className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 grid place-items-center bg-transparent border-0 text-mute rounded-md cursor-pointer transition-[color,background-color] duration-200 hover:text-ink hover:bg-cream focus-visible:outline-none focus-visible:text-ink focus-visible:shadow-[0_0_0_3px_var(--accent-lo)]"
    >
      {show ? (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
          <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
          <path d="M14.12 14.12A3 3 0 1 1 9.88 9.88" />
          <line x1="1" y1="1" x2="23" y2="23" />
        </svg>
      ) : (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
          <circle cx="12" cy="12" r="3" />
        </svg>
      )}
    </button>
  )
}
