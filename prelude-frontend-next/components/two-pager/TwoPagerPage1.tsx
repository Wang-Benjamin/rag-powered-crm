'use client'

import React from 'react'
import Page1Header from './page1/Page1Header'
import StatsStrip from './page1/StatsStrip'
import BuyerTable from './page1/BuyerTable'

// ── Types — match TwoPagerResponse Pydantic schema (camelCase via ApiClient) ──

export interface TwoPagerStats {
  // Real ImportYeti volume signals — replaces the old totalImportUsdCn
  // estimate. All annualized from the 6-month PowerQuery window.
  totalImportTons: number | null
  totalContainers: number | null
  totalHsShipments: number | null
  yoyGrowthPct: number | null
  activeImporterCount: number | null
  supplierChurnPct: number | null
}

export interface TwoPagerBuyer {
  rank: number
  slug: string
  name: string
  city: string | null
  state: string | null
  annualVolumeTons: number | null
  containersCount: number | null
  hsShipmentsCount: number | null
  cnPrevSupplierCount: number | null
  cnCurrSupplierCount: number | null
  trendYoyPct: number | null
  score: number | null
}

export interface TwoPagerBuyerContact {
  buyerSlug: string
  buyerName: string
  score: number | null
  location: string | null
  annualVolumeTons: number | null
  containersCount: number | null
  hsShipmentsCount: number | null
  trendYoyPct: number | null
  cnPrevSupplierCount: number | null
  cnCurrSupplierCount: number | null
  cnSubheader: string | null
  contactName: string | null
  contactTitle: string | null
  contactEmail: string | null
  fetchStatus: 'found' | 'not_found' | 'failed'
  emailSubject: string | null
  emailBody: string | null
  // Backend metadata: true when the contact was AI-mocked (Apollo missed).
  // Frontend renders synth and real contacts identically; this is here so
  // analytics / export flows can distinguish if needed.
  isSynthesized?: boolean
}

export interface TwoPagerData {
  // Both may be null: HS-only requests may omit a human-readable
  // description; product-only requests carry no HS code. Page1Header
  // has a final `HS <code>` fallback so the title never renders blank.
  hsCode: string | null
  hsCodeDescription: string | null
  hsCodeDescriptionCn: string | null
  generatedAt: string
  stats: TwoPagerStats
  buyers: TwoPagerBuyer[]
  buyerContacts: TwoPagerBuyerContact[]
  warnings: string[] | null
}

// ── Component ─────────────────────────────────────────────────────

interface TwoPagerPage1Props {
  data: TwoPagerData
}

export default function TwoPagerPage1({ data }: TwoPagerPage1Props) {
  const { stats, buyers, hsCode, generatedAt } = data
  const displayed = buyers.length

  return (
    <div className="two-pager-root two-pager-page1 page">
      <style>{`
        /* ── Design tokens (inlined for self-contained print artifact) ── */
        .two-pager-root {
          --bone:        oklch(0.972 0.008 85);
          --paper:       oklch(0.955 0.013 85);
          --ink:         oklch(0.22 0.015 260);
          --deep:        oklch(0.18 0.02 260);
          --mute:        oklch(0.54 0.015 260);
          --rule:        oklch(0.89 0.012 80);
          --rule-strong: oklch(0.82 0.013 80);
          --accent:      oklch(0.52 0.09 155);
          --accent-lo:   oklch(0.65 0.08 155);
          --gold:        oklch(0.65 0.12 75);

          --font-sans-cn:    var(--font-noto-sans-sc), 'Noto Sans SC', 'PingFang SC', ui-sans-serif, system-ui, sans-serif;
          --font-serif-cn:   var(--font-noto-serif-sc), 'Noto Serif SC', 'Songti SC', 'Source Han Serif SC', serif;
          --font-display:    var(--font-instrument-serif), 'Instrument Serif', serif;
          --font-body:       var(--font-geist), 'Geist', ui-sans-serif, system-ui, sans-serif;
          --font-mono:       var(--font-jetbrains-mono), 'JetBrains Mono', ui-monospace, monospace;
        }

        .two-pager-root {
          font-family: var(--font-sans-cn);
          font-size: 10pt;
          line-height: 1.55;
          color: var(--ink);
          -webkit-font-smoothing: antialiased;
          text-rendering: optimizeLegibility;
          -webkit-print-color-adjust: exact;
          print-color-adjust: exact;
        }

        /* Latin/numeric runs use Geist */
        .two-pager-root .lat,
        .two-pager-root .mono {
          font-family: var(--font-body);
        }

        /* ── A4 page frame ── */
        .two-pager-root.page {
          width: 210mm;
          height: 297mm;
          background: var(--bone);
          position: relative;
          overflow: visible;
          padding: 18mm 18mm 15mm;
          box-sizing: border-box;
          margin: 0 auto 8mm;
          box-shadow: 0 4mm 20mm rgba(0,0,0,0.18);
          display: flex;
          flex-direction: column;
        }
        .two-pager-page1 { page-break-after: always; break-after: page; }

        @page { size: A4; margin: 0; }
        @media print {
          html, body { background: white !important; margin: 0 !important; padding: 0 !important; }
          .two-pager-root.page { margin: 0; box-shadow: none; }
          .no-print { display: none !important; }
        }

        /* ── Section label (shared between pages) ── */
        .two-pager-root .sec-label {
          font-family: var(--font-mono);
          font-size: 7pt;
          letter-spacing: 0.14em;
          color: var(--mute);
          text-transform: uppercase;
          margin: 0 0 3mm;
          display: flex;
          justify-content: space-between;
        }
        .two-pager-root .sec-label .cn {
          font-family: var(--font-sans-cn);
          letter-spacing: 0.08em;
          color: var(--deep);
          font-weight: 500;
          font-size: 8pt;
        }

        /* ── Page footer ── */
        .two-pager-root .rp-foot {
          margin-top: auto;
          padding-top: 4mm;
          border-top: 0.25mm solid var(--rule);
          display: flex;
          justify-content: space-between;
          font-family: var(--font-mono);
          font-size: 7pt;
          color: var(--mute);
          letter-spacing: 0.1em;
          text-transform: uppercase;
        }
        .two-pager-root .rp-foot .cn {
          font-family: var(--font-sans-cn);
          letter-spacing: 0.06em;
          text-transform: none;
          color: var(--deep);
          font-size: 8pt;
        }
      `}</style>

      <Page1Header
        hsCode={hsCode}
        hsCodeDescription={data.hsCodeDescription}
        hsCodeDescriptionCn={data.hsCodeDescriptionCn}
        generatedAt={generatedAt}
        pageMarker="01 / 02"
      />

      <StatsStrip stats={stats} />

      <BuyerTable buyers={buyers} />

      <div className="rp-foot">
        <span className="cn">已显示 {displayed} / {displayed}</span>
        <span>数据源 · 美国海关 (CBP)</span>
      </div>
    </div>
  )
}
