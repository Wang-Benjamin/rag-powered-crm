'use client'

import React from 'react'

// ── Helper ────────────────────────────────────────────────────────

function reportMonth(iso: string): string {
  try {
    const d = new Date(iso)
    return `${d.getUTCFullYear()}年${d.getUTCMonth() + 1}月`
  } catch {
    return ''
  }
}

// ── Props ─────────────────────────────────────────────────────────

interface Page1HeaderProps {
  hsCode: string | null
  hsCodeDescription: string | null
  hsCodeDescriptionCn: string | null
  generatedAt: string
  pageMarker: string
}

export default function Page1Header({
  hsCode,
  hsCodeDescription,
  hsCodeDescriptionCn,
  generatedAt,
  pageMarker,
}: Page1HeaderProps) {
  const month = reportMonth(generatedAt)
  const titleCn = hsCodeDescriptionCn || hsCodeDescription || (hsCode ? `HS ${hsCode}` : '美国进口商')
  const titleEn = hsCodeDescription || (hsCode ? `HS ${hsCode}` : 'US Importers')

  return (
    <>
      <style>{`
        /* ── Page header ── */
        /* NOTE: class prefix is tp-ph, not ph — global .ph in design-kit/tokens.css
           paints a placeholder stripe pattern and we MUST not collide with it. */
        .tp-ph {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          padding-bottom: 4mm;
          border-bottom: 0.3mm solid var(--rule-strong);
          margin-bottom: 4mm;
        }
        .tp-ph-brand {
          display: flex;
          flex-direction: column;
          gap: 1mm;
        }
        .tp-ph-brand .row1 {
          display: flex;
          align-items: baseline;
          gap: 3mm;
        }
        .tp-ph-brand .wm {
          font-family: var(--font-display);
          font-size: 15pt;
          color: var(--deep);
          letter-spacing: -0.005em;
          line-height: 1;
        }
        .tp-ph-brand .zh {
          font-family: var(--font-serif-cn);
          font-size: 11pt;
          color: var(--mute);
          letter-spacing: 0.06em;
          padding-left: 3mm;
          border-left: 0.25mm solid var(--rule-strong);
          line-height: 1;
        }
        .tp-ph-brand .url {
          font-family: var(--font-body);
          font-size: 7.5pt;
          color: var(--mute);
          letter-spacing: 0.04em;
          line-height: 1;
        }
        .tp-ph-meta {
          font-family: var(--font-mono);
          font-size: 7.5pt;
          letter-spacing: 0.1em;
          color: var(--mute);
          text-transform: uppercase;
          text-align: right;
          line-height: 1.55;
        }
        .tp-ph-meta b { color: var(--deep); font-weight: 500; }

        /* ── Title block ── */
        .eyebrow {
          font-family: var(--font-mono);
          font-size: 7.5pt;
          letter-spacing: 0.14em;
          color: var(--accent);
          text-transform: uppercase;
          margin-bottom: 4mm;
          display: block;
        }
        .title {
          font-family: var(--font-serif-cn);
          font-weight: 600;
          font-size: 26pt;
          color: var(--deep);
          line-height: 1.2;
          letter-spacing: 0.01em;
          margin: 0 0 3mm;
        }
        .title em {
          font-family: var(--font-display);
          font-style: italic;
          font-weight: 400;
          color: var(--accent);
          letter-spacing: -0.005em;
        }
        .subtitle {
          font-family: var(--font-sans-cn);
          font-size: 10pt;
          color: var(--mute);
          letter-spacing: 0.02em;
          line-height: 1.6;
          margin: 0 0 4mm;
          max-width: 130mm;
        }
      `}</style>

      <header className="tp-ph">
        <div className="tp-ph-brand">
          <div className="row1">
            <span className="wm">Prelude</span>
            <span className="zh">璞序</span>
          </div>
          <span className="url">preludeos.com</span>
        </div>
        <div className="tp-ph-meta">
          <div>{hsCode ? `HS ${hsCode}` : 'US Customs · CBP'}</div>
          <div><b>{month}</b> · {pageMarker}</div>
        </div>
      </header>

      <span className="eyebrow">Free Buyer Report · 免费买家报告</span>
      <h1 className="title">
        {titleCn}
        {titleEn && titleEn !== titleCn ? <> <em>{titleEn}</em></> : null}
      </h1>
      <p className="subtitle">基于美国海关公开申报数据 · 覆盖过去 12 个月 · 按进口量与意向评分排序。</p>
    </>
  )
}
