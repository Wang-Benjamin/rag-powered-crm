'use client'

import React from 'react'
import { useTranslations } from 'next-intl'
import { pcardBaseCls, pcardHdCls } from './loginPrimitives'

const Showcase = () => {
  const t = useTranslations('auth.login')

  return (
    <aside
      className="relative bg-bone overflow-hidden p-10 grid grid-rows-[auto_1fr_auto] max-lg:hidden"
      aria-label="Product preview"
    >
      {/* Grid mask overlay */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage:
            'linear-gradient(to right, color-mix(in oklab, var(--rule) 55%, transparent) 1px, transparent 1px), linear-gradient(to bottom, color-mix(in oklab, var(--rule) 55%, transparent) 1px, transparent 1px)',
          backgroundSize: '64px 64px',
          backgroundPosition: '-1px -1px',
          maskImage: 'radial-gradient(ellipse at 50% 50%, black 20%, transparent 75%)',
          WebkitMaskImage: 'radial-gradient(ellipse at 50% 50%, black 20%, transparent 75%)',
        }}
      />

      <div className="relative flex items-center justify-between gap-5">
        <span className="font-mono text-[10.5px] font-medium tracking-[0.18em] uppercase text-mute whitespace-nowrap">
          {t('heroEyebrow')} · <b className="text-ink font-medium">{t('heroEyebrowEmphasis')}</b>
        </span>
        <span className="font-mono text-[10.5px] font-medium tracking-[0.18em] uppercase text-mute whitespace-nowrap">
          {t('heroDataSource')}
        </span>
      </div>

      <div className="relative self-center justify-self-center w-[min(720px,100%)] aspect-[1/0.78] max-h-[620px]">
        {/* Decorative rings */}
        <span
          className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[320px] h-[320px] rounded-[40px] pointer-events-none z-[2]"
          style={{ border: '1px solid color-mix(in oklab, var(--rule) 50%, transparent)' }}
          aria-hidden="true"
        />
        <span
          className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[180px] h-[180px] rounded-[30px] pointer-events-none z-[2]"
          style={{ border: '1px solid color-mix(in oklab, var(--rule) 75%, transparent)' }}
          aria-hidden="true"
        />

        {/* Connector lines */}
        <svg
          className="absolute inset-0 pointer-events-none z-[1]"
          viewBox="0 0 720 562"
          preserveAspectRatio="none"
          aria-hidden="true"
          style={{ stroke: 'color-mix(in oklab, var(--rule) 80%, transparent)' }}
        >
          <line x1="360" y1="281" x2="150" y2="110" strokeWidth="1" strokeDasharray="3 4" />
          <line x1="360" y1="281" x2="570" y2="90" strokeWidth="1" strokeDasharray="3 4" />
          <line x1="360" y1="281" x2="170" y2="470" strokeWidth="1" strokeDasharray="3 4" />
          <line x1="360" y1="281" x2="580" y2="450" strokeWidth="1" strokeDasharray="3 4" />
        </svg>

        {/* Hub */}
        <div
          className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[72px] h-[72px] grid place-items-center rounded-[18px] bg-deep text-bone overflow-hidden z-[4] shadow-[0_14px_32px_-18px_oklch(0.25_0.02_260/0.35)]"
          aria-hidden="true"
        >
          <span
            className="absolute inset-0 opacity-70 pointer-events-none"
            style={{
              background:
                'radial-gradient(ellipse at 80% 120%, color-mix(in oklab, var(--accent) 55%, transparent) 0%, transparent 65%)',
            }}
          />
          <span
            className="absolute -inset-px rounded-[18px] pointer-events-none"
            style={{ border: '1px solid color-mix(in oklab, var(--accent) 50%, transparent)' }}
          />
          <svg className="relative w-7 h-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
            <path d="M16.5 9.4 7.55 4.24" />
            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
            <polyline points="3.29 7 12 12 20.71 7" />
            <line x1="12" y1="22" x2="12" y2="12" />
          </svg>
        </div>

        {/* Revenue card */}
        <article
          className={`${pcardBaseCls} w-[244px] left-[6%] top-[8%] animate-[loginFloatA_9s_ease-in-out_infinite]`}
        >
          <div className={pcardHdCls}>
            <span className="w-[22px] h-[22px] grid place-items-center rounded-md bg-accent-lo text-accent" aria-hidden="true">
              <svg className="w-[13px] h-[13px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 3v18h18" />
                <path d="M18 17V9" />
                <path d="M13 17V5" />
                <path d="M8 17v-3" />
              </svg>
            </span>
            <span>{t('heroRevenue')}</span>
          </div>
          <div className="flex items-baseline justify-between gap-2">
            <span className="font-display text-[34px] font-normal leading-none tracking-[-0.015em] text-deep">$1.2M</span>
            <span className="inline-flex items-center gap-1 font-mono text-[11px] font-medium tracking-[0.04em] text-accent">↗ +24%</span>
          </div>
          <div className="mt-1 text-[11.5px] text-mute">{t('heroRevenueNote')}</div>
          <div className="grid grid-cols-12 items-end gap-1 h-11 mt-3.5" aria-hidden="true">
            {[32, 44, 38, 56, 48, 62, 54, 70, 66, 84, 92, 100].map((h, i) => (
              <span
                key={i}
                className={`block rounded-t-sm ${i >= 9 ? 'bg-accent' : 'bg-ink'}`}
                style={{ height: `${h}%` }}
              />
            ))}
          </div>
        </article>

        {/* Customers card */}
        <article
          className={`${pcardBaseCls} w-[244px] right-[6%] top-[4%] animate-[loginFloatB_11s_ease-in-out_infinite]`}
        >
          <div className={pcardHdCls}>
            <span className="w-[22px] h-[22px] grid place-items-center rounded-md bg-cream text-ink" aria-hidden="true">
              <svg className="w-[13px] h-[13px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
                <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
                <path d="M16 3.13a4 4 0 0 1 0 7.75" />
              </svg>
            </span>
            <span>{t('heroCustomers')}</span>
          </div>
          <div className="flex flex-col gap-2.5 mt-1">
            {[
              { av: 'HC', nm: 'Hartwell & Crane', ov: 'IL' },
              { av: 'BW', nm: 'Blackwood Supply', ov: 'OH' },
              { av: 'MR', nm: 'Meridian Retail', ov: 'GA' },
            ].map((row, i) => (
              <div key={i} className="grid grid-cols-[22px_1fr] items-center gap-2.5">
                <span className="w-[22px] h-[22px] grid place-items-center rounded-[5px] bg-cream text-ink font-mono text-[10px] font-medium tracking-[0.04em]">
                  {row.av}
                </span>
                <span className="text-[13px] text-ink">
                  {row.nm}
                  <span className="text-mute font-mono text-[10.5px] tracking-[0.06em] ml-1.5">{row.ov}</span>
                </span>
              </div>
            ))}
          </div>
        </article>

        {/* Outreach card */}
        <article
          className={`${pcardBaseCls} w-[256px] left-[10%] bottom-[6%] animate-[loginFloatC_10s_ease-in-out_infinite]`}
        >
          <div className={pcardHdCls}>
            <span className="w-[22px] h-[22px] grid place-items-center rounded-md bg-gold-lo text-[color:color-mix(in_oklab,var(--gold),var(--deep)_20%)]" aria-hidden="true">
              <svg className="w-[13px] h-[13px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                <polyline points="22,6 12,13 2,6" />
              </svg>
            </span>
            <span>{t('heroOutreach')}</span>
          </div>
          <div className="grid grid-cols-3 gap-1 mt-1.5 pt-2.5 border-t border-rule">
            <div className="text-left">
              <div className="font-display text-[26px] leading-none tracking-[-0.01em] text-deep">847</div>
              <div className="font-mono text-[9.5px] font-medium tracking-[0.12em] uppercase text-mute mt-1.5">{t('heroSent')}</div>
            </div>
            <div className="text-left">
              <div className="font-display text-[26px] leading-none tracking-[-0.01em] text-accent">
                62<span className="font-mono text-base align-[3px] font-medium">%</span>
              </div>
              <div className="font-mono text-[9.5px] font-medium tracking-[0.12em] uppercase text-mute mt-1.5">{t('heroOpenRate')}</div>
            </div>
            <div className="text-left">
              <div className="font-display text-[26px] leading-none tracking-[-0.01em] text-deep">
                28<span className="font-mono text-base align-[3px] font-medium">%</span>
              </div>
              <div className="font-mono text-[9.5px] font-medium tracking-[0.12em] uppercase text-mute mt-1.5">{t('heroReplyRate')}</div>
            </div>
          </div>
        </article>

        {/* Trade intel card */}
        <article
          className={`${pcardBaseCls} w-[260px] right-[4%] bottom-[10%] animate-[loginFloatD_12s_ease-in-out_infinite]`}
        >
          <div className={pcardHdCls}>
            <span className="w-[22px] h-[22px] grid place-items-center rounded-md bg-deep text-bone" aria-hidden="true">
              <svg className="w-[13px] h-[13px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <line x1="2" y1="12" x2="22" y2="12" />
                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
              </svg>
            </span>
            <span>{t('heroTradeFlow')}</span>
          </div>
          <div className="flex flex-col mt-0.5">
            {[
              { dot: 'accent', nm: t('heroUsImport'), v: '$420K' },
              { dot: 'ink', nm: t('heroEuExport'), v: '$310K' },
              { dot: 'gold', nm: t('heroApac'), v: '$280K' },
            ].map((row, i) => (
              <div key={i} className="grid grid-cols-[14px_1fr_auto] items-center gap-2.5 py-2 border-b border-rule last:border-b-0">
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    row.dot === 'accent' ? 'bg-accent' : row.dot === 'gold' ? 'bg-gold' : 'bg-ink'
                  }`}
                />
                <span className="text-[12.5px] text-ink">{row.nm}</span>
                <span className="font-mono text-[12px] tabular-nums text-deep font-medium">{row.v}</span>
              </div>
            ))}
          </div>
        </article>
      </div>

      <div className="relative flex flex-col items-center gap-3 py-3 pt-1 w-full">
        <p className="display display-s text-center whitespace-nowrap">
          {t('heroTagline')} <em className="italic text-accent">{t('heroTaglineEm')}</em>
        </p>
        <div className="flex items-center justify-center gap-3 font-mono text-[10.5px] font-medium tracking-[0.18em] uppercase text-mute whitespace-nowrap">
          <span>{t('heroSubCrm')}</span>
          <span className="inline-block w-[3px] h-[3px] rounded-full bg-rule" />
          <span>{t('heroSubTrade')}</span>
          <span className="inline-block w-[3px] h-[3px] rounded-full bg-rule" />
          <span>{t('heroSubAi')}</span>
          <span className="inline-block w-[3px] h-[3px] rounded-full bg-rule" />
          <span>{t('heroSubAnalytics')}</span>
        </div>
      </div>
    </aside>
  )
}

export default React.memo(Showcase)
