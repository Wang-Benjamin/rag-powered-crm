'use client'

import React from 'react'
import type { TwoPagerStats } from '../TwoPagerPage1'
import { formatTons } from '../format'

// ── Props ─────────────────────────────────────────────────────────

interface StatsStripProps {
  stats: TwoPagerStats
}

/**
 * Render a YoY value as a signed "+18" integer with a "%" unit chip, so the
 * design's `.kpi .v em` accent + `.v .u` pattern can style each part. A flat
 * 0% reads as neutral (mute) rather than the accent color, so a zero-YoY
 * market doesn't look like a win.
 */
function renderYoy(pct: number | null) {
  if (pct === null || pct === undefined) {
    return <span className="v-muted">—</span>
  }
  const sign = pct > 0 ? '+' : pct < 0 ? '−' : ''
  const abs = Math.abs(pct).toFixed(1)
  const emClass = pct === 0 ? 'em-flat' : ''
  return (
    <>
      <em className={emClass}>{sign}{abs}</em><span className="u">%</span>
    </>
  )
}

function renderChurn(pct: number | null) {
  if (pct === null || pct === undefined) return null
  const sign = pct > 0 ? '+' : pct < 0 ? '−' : ''
  const abs = Math.abs(pct).toFixed(1)
  const emClass = pct === 0 ? 'em-flat' : 'gold-em'
  return (
    <>
      <em className={emClass}>{sign}{abs}</em><span className="u">%</span>
    </>
  )
}

export default function StatsStrip({ stats }: StatsStripProps) {
  const volumeCaption = '过去 12 个月'

  const churnNull = stats.supplierChurnPct === null || stats.supplierChurnPct === undefined

  return (
    <>
      <style>{`
        .kpi {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          border-top: 0.3mm solid var(--rule-strong);
          border-bottom: 0.3mm solid var(--rule-strong);
          margin-bottom: 4mm;
        }
        .kpi > div {
          padding: 3.5mm 5mm 3.5mm 5mm;
          border-right: 0.25mm solid var(--rule);
          box-sizing: border-box;
        }
        .kpi > div:first-child { padding-left: 0; }
        .kpi > div:last-child { border-right: 0; padding-right: 0; }
        .kpi .lb {
          font-family: var(--font-sans-cn);
          font-size: 8pt;
          color: var(--mute);
          letter-spacing: 0.08em;
          display: block;
          margin-bottom: 2mm;
        }
        .kpi .lb .lat {
          font-family: var(--font-body);
          font-size: 7pt;
          color: var(--mute);
          letter-spacing: 0.04em;
        }
        .kpi .v {
          font-family: var(--font-display);
          font-size: 22pt;
          color: var(--deep);
          line-height: 1;
          letter-spacing: -0.02em;
        }
        .kpi .v em {
          color: var(--accent);
          font-style: italic;
          font-size: 18pt;
          letter-spacing: 0;
        }
        .kpi .v em.gold-em {
          color: var(--gold);
        }
        .kpi .v em.em-flat {
          color: var(--mute);
        }
        .kpi .v .u {
          display: inline-block;
          margin-left: 1.5mm;
          color: var(--mute);
          font-size: 14pt;
          letter-spacing: 0.01em;
        }
        .kpi .v-muted {
          color: var(--mute);
          font-family: var(--font-display);
          font-size: 22pt;
          line-height: 1;
        }
        .kpi .sub {
          font-family: var(--font-sans-cn);
          font-size: 7.5pt;
          color: var(--mute);
          margin-top: 2mm;
          letter-spacing: 0.02em;
        }
      `}</style>

      <div className="kpi">
        <div>
          <span className="lb">货量 <span className="lat">· Volume</span></span>
          <div className="v">{formatTons(stats.totalImportTons)}</div>
          <div className="sub">{volumeCaption}</div>
        </div>
        <div>
          <span className="lb">同比 <span className="lat">· YoY</span></span>
          <div className="v">{renderYoy(stats.yoyGrowthPct)}</div>
          <div className="sub">2025 vs 2024</div>
        </div>
        <div>
          <span className="lb">买家数 <span className="lat">· Buyers</span></span>
          <div className="v">{stats.activeImporterCount !== null ? stats.activeImporterCount : '—'}</div>
          <div className="sub">在该品类主动采购</div>
        </div>
        <div>
          <span className="lb">流失率 <span className="lat">· Churn</span></span>
          <div className="v">
            {churnNull ? <span className="v-muted">—</span> : renderChurn(stats.supplierChurnPct)}
          </div>
          <div className="sub">
            {churnNull ? '数据不足 · Insufficient data' : '供应商流失率 · 12mo'}
          </div>
        </div>
      </div>
    </>
  )
}
