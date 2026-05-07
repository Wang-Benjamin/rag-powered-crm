'use client'

import React from 'react'
import { useTranslations } from 'next-intl'
import {
  ssoBtnCls,
  primaryCtaCls,
  smallSpinnerCls,
  ChevSvg,
  H1Title,
} from '../loginPrimitives'

type Props = {
  loadingProvider: string | null
  wechatLoading: boolean
  onGoogleLogin: () => void
  onMicrosoftLogin: () => void
  onWechatLogin: () => void
  onUsernameLogin: () => void
}

export default function MainView({
  loadingProvider,
  wechatLoading,
  onGoogleLogin,
  onMicrosoftLogin,
  onWechatLogin,
  onUsernameLogin,
}: Props) {
  const t = useTranslations('auth.login')

  return (
    <>
      <div className="mb-10">
        <H1Title />
      </div>

      <div className="flex flex-col gap-2.5" role="group">
        {/* Google */}
        <button
          type="button"
          className={ssoBtnCls}
          onClick={onGoogleLogin}
          disabled={!!loadingProvider}
          aria-busy={loadingProvider === 'google'}
          aria-label={t('continueWithGoogle')}
        >
          <span className="w-[22px] h-[22px] grid place-items-center group-aria-busy:opacity-35" aria-hidden="true">
            <svg viewBox="0 0 48 48" className="w-[22px] h-[22px]">
              <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
              <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
              <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
              <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
            </svg>
          </span>
          <span className="flex flex-col gap-0.5 min-w-0">
            <span className="text-ink font-medium">{t('continueWithGoogle')}</span>
            <span className="font-mono text-[10px] font-medium tracking-[0.14em] uppercase text-mute">{t('googleMeta')}</span>
          </span>
          <span className="text-mute transition-[transform,color] duration-200 group-hover:text-ink group-hover:translate-x-0.5 group-aria-busy:hidden" aria-hidden="true">
            <ChevSvg />
          </span>
          {loadingProvider === 'google' && <span className={`${smallSpinnerCls} absolute right-[18px]`} aria-hidden="true" />}
        </button>

        {/* Microsoft */}
        <button
          type="button"
          className={ssoBtnCls}
          onClick={onMicrosoftLogin}
          disabled={!!loadingProvider}
          aria-busy={loadingProvider === 'microsoft'}
          aria-label={t('continueWithMicrosoft')}
        >
          <span className="w-[22px] h-[22px] grid place-items-center group-aria-busy:opacity-35" aria-hidden="true">
            <svg viewBox="0 0 48 48" className="w-[22px] h-[22px]">
              <path fill="#F25022" d="M6 6h17v17H6z" />
              <path fill="#7FBA00" d="M25 6h17v17H25z" />
              <path fill="#00A4EF" d="M6 25h17v17H6z" />
              <path fill="#FFB900" d="M25 25h17v17H25z" />
            </svg>
          </span>
          <span className="flex flex-col gap-0.5 min-w-0">
            <span className="text-ink font-medium">{t('continueWithMicrosoft')}</span>
            <span className="font-mono text-[10px] font-medium tracking-[0.14em] uppercase text-mute">{t('microsoftMeta')}</span>
          </span>
          <span className="text-mute transition-[transform,color] duration-200 group-hover:text-ink group-hover:translate-x-0.5 group-aria-busy:hidden" aria-hidden="true">
            <ChevSvg />
          </span>
          {loadingProvider === 'microsoft' && <span className={`${smallSpinnerCls} absolute right-[18px]`} aria-hidden="true" />}
        </button>

        {/* WeChat */}
        <button
          type="button"
          className={ssoBtnCls}
          onClick={onWechatLogin}
          disabled={!!loadingProvider || wechatLoading}
          aria-busy={wechatLoading}
          aria-label={t('scanWithWeChat')}
        >
          <span className="w-[22px] h-[22px] grid place-items-center group-aria-busy:opacity-35" aria-hidden="true">
            <svg viewBox="0 0 48 48" className="w-[22px] h-[22px]">
              <path fill="#09B83E" d="M18.5 6C9.4 6 2 12.4 2 20.3c0 4.4 2.4 8.3 6.2 10.9L6.6 36l5.6-2.8c1.9.5 3.9.8 5.9.8.5 0 1 0 1.5-.1-.3-1-.5-2.1-.5-3.2 0-7.3 7-13.1 15.6-13.1h.8C34 11.6 27 6 18.5 6zm-5 7.2c1.1 0 2 .9 2 2 0 1.1-.9 2-2 2s-2-.9-2-2c0-1.1.9-2 2-2zm10 0c1.1 0 2 .9 2 2 0 1.1-.9 2-2 2s-2-.9-2-2c0-1.1.9-2 2-2z" />
              <path fill="#09B83E" d="M46 30.4c0-6.5-6.2-11.7-13.9-11.7-8 0-13.9 5.3-13.9 11.7 0 6.5 5.9 11.7 13.9 11.7 1.7 0 3.4-.3 4.9-.7L42 44l-1.3-4.3c3.2-2.2 5.3-5.4 5.3-9.3zM27.5 27c-.9 0-1.7-.8-1.7-1.7 0-.9.8-1.7 1.7-1.7s1.7.8 1.7 1.7c0 .9-.8 1.7-1.7 1.7zm9.2 0c-.9 0-1.7-.8-1.7-1.7 0-.9.8-1.7 1.7-1.7.9 0 1.7.8 1.7 1.7 0 .9-.8 1.7-1.7 1.7z" />
            </svg>
          </span>
          <span className="flex flex-col gap-0.5 min-w-0">
            <span className="text-ink font-medium">{t('scanWithWeChat')}</span>
            <span className="font-mono text-[10px] font-medium tracking-[0.14em] uppercase text-mute">{t('wechatMeta')}</span>
          </span>
          <span className="text-mute transition-[transform,color] duration-200 group-hover:text-ink group-hover:translate-x-0.5 group-aria-busy:hidden" aria-hidden="true">
            <ChevSvg />
          </span>
          {wechatLoading && <span className={`${smallSpinnerCls} absolute right-[18px]`} aria-hidden="true" />}
        </button>
      </div>

      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3.5 mt-[26px] mb-[18px]" role="separator">
        <span className="h-px bg-rule" />
        <span className="font-mono text-[10.5px] font-medium tracking-[0.2em] uppercase text-mute">{t('or')}</span>
        <span className="h-px bg-rule" />
      </div>

      <button
        type="button"
        onClick={onUsernameLogin}
        aria-label={t('continueWithUsername')}
        className={`${primaryCtaCls} group`}
      >
        <span>{t('continueWithUsername')}</span>
        <span aria-hidden="true" className="inline-block transition-transform duration-200 group-hover:translate-x-0.5">→</span>
      </button>
    </>
  )
}
