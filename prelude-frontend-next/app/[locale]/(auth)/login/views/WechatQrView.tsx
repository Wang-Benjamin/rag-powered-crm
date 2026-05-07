'use client'

import React from 'react'
import { useTranslations } from 'next-intl'
import {
  largeSpinnerCls,
  BackToMain,
  H1Title,
  QrFrameCorners,
} from '../loginPrimitives'

type Props = {
  wechatQrUrl: string | null
  wechatScanned: boolean
  wechatExpired: boolean
  onBack: () => void
  onRefresh: () => void
}

const qrFrameCls =
  'relative w-60 h-60 p-3.5 bg-bone border border-rule rounded-2xl grid place-items-center shadow-[0_14px_32px_-20px_oklch(0.25_0.02_260/0.2)]'

const qrFootnoteCls =
  'mt-1 font-mono text-[10.5px] tracking-[0.14em] uppercase text-mute flex items-center gap-2'

const pulseDotCls =
  'w-1 h-1 rounded-full bg-accent shadow-[0_0_0_3px_var(--accent-lo)] animate-pulse motion-reduce:animate-none'

export default function WechatQrView({
  wechatQrUrl,
  wechatScanned,
  wechatExpired,
  onBack,
  onRefresh,
}: Props) {
  const t = useTranslations('auth.login')

  const showLive = !wechatScanned && !wechatExpired
  const showScanned = wechatScanned && !wechatExpired
  const showExpired = wechatExpired

  return (
    <>
      <BackToMain onBack={onBack} />

      <div className="mb-6">
        <H1Title />
      </div>

      {showLive && (
        <div className="flex flex-col items-center gap-[18px]">
          <p className="text-[13.5px] text-mute text-center">{t('wechatScanning')}</p>
          <div className={qrFrameCls} aria-label={t('scanWithWeChat')}>
            <QrFrameCorners />
            {wechatQrUrl ? (
              <img src={wechatQrUrl} alt="WeChat QR" className="w-[208px] h-[208px] object-contain block" />
            ) : (
              <div className="w-[208px] h-[208px] flex items-center justify-center">
                <div className={largeSpinnerCls} aria-hidden="true" />
              </div>
            )}
          </div>
          <div className={qrFootnoteCls}>
            <span className={pulseDotCls} />
            <span>{t('wechatWaitingScan')}</span>
          </div>
        </div>
      )}

      {showScanned && (
        <div className="flex flex-col items-center gap-[18px]">
          <div className={qrFrameCls} aria-live="polite">
            <QrFrameCorners />
            <div className="w-[208px] h-[208px] flex flex-col items-center justify-center gap-3.5 text-center">
              <div className={largeSpinnerCls} aria-hidden="true" />
              <p className="text-[13.5px] text-mute leading-[1.5] max-w-[16ch]">
                <b className="title-panel block mb-1">
                  {t('wechatScanReceivedTitle')}
                </b>
                {t('wechatScanReceivedBody')}
              </p>
            </div>
          </div>
          <div className={qrFootnoteCls}>
            <span className={pulseDotCls} />
            <span>{t('wechatAwaitingConfirmation')}</span>
          </div>
        </div>
      )}

      {showExpired && (
        <div className="flex flex-col items-center gap-[18px]">
          <div className={qrFrameCls}>
            <QrFrameCorners />
            <div className="w-[208px] h-[208px] flex flex-col items-center justify-center gap-3.5 text-center">
              <div className="w-10 h-10 grid place-items-center rounded-full bg-cream text-mute" aria-hidden="true">
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="9" />
                  <polyline points="12 7 12 12 15 14" />
                </svg>
              </div>
              <p className="text-[13.5px] text-mute leading-[1.5] max-w-[16ch]">
                <b className="title-panel block mb-1">
                  {t('wechatQrExpiredTitle')}
                </b>
                {t('wechatQrExpiredBody')}
              </p>
              <button
                type="button"
                onClick={onRefresh}
                className="inline-flex items-center gap-2 px-3.5 h-9 bg-bone border border-rule rounded-lg text-ink text-[13px] font-medium cursor-pointer transition-all duration-200 hover:border-ink hover:bg-cream focus-visible:outline-none focus-visible:border-accent focus-visible:shadow-[0_0_0_3px_var(--accent-lo)]"
              >
                <svg className="w-[13px] h-[13px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M21 12a9 9 0 1 1-3-6.7L21 8" />
                  <path d="M21 3v5h-5" />
                </svg>
                {t('wechatRefreshQr')}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
