'use client'

import React from 'react'
import type { TwoPagerBuyer } from '../TwoPagerPage1'
import { formatTons } from '../format'

// Format supplier change as "pct" + "prev→curr家" parts. When prev=0 the
// percentage is meaningless (0→N is "appeared from nothing"), so skip the %.
// Design semantics (flipped from our previous component):
//   decrease (negative %) → .down → green (accent) → supplier consolidation
//   increase (positive %) → .up   → gold → new supplier adds
//   0% / unchanged        → .flat → mute
function computeSupplierChange(
  prev: number | null,
  curr: number | null,
): { pct: string | null; count: string; tone: 'up' | 'down' | 'flat' } {
  if (prev === null || curr === null) {
    return { pct: null, count: '—', tone: 'flat' }
  }
  if (prev === 0) {
    return {
      pct: null,
      count: `${prev}→${curr}家`,
      tone: curr > 0 ? 'up' : 'flat',
    }
  }
  const pctNum = ((curr - prev) / prev) * 100
  const sign = pctNum > 0 ? '+' : pctNum < 0 ? '−' : ''
  const abs = Math.abs(pctNum).toFixed(1)
  return {
    pct: `${sign}${abs}%`,
    count: `${prev}→${curr}家`,
    tone: pctNum > 0 ? 'up' : pctNum < 0 ? 'down' : 'flat',
  }
}

// ── Props ─────────────────────────────────────────────────────────

interface BuyerTableProps {
  buyers: TwoPagerBuyer[]
}

export default function BuyerTable({ buyers }: BuyerTableProps) {
  const total = buyers.length

  return (
    <>
      <style>{`
        .tbl { flex: 0 0 auto; min-height: 0; margin-bottom: 4mm; }
        .tbl-legend {
          font-family: var(--font-sans-cn);
          font-size: 7pt;
          color: var(--mute);
          letter-spacing: 0.04em;
          margin-bottom: 1mm;
        }
        .tbl-legend .sw {
          display: inline-block;
          width: 1.6mm;
          height: 1.6mm;
          border-radius: 50%;
          vertical-align: 0.2mm;
          margin-right: 1mm;
        }

        .rpr {
          display: grid;
          grid-template-columns: 7mm 1fr 36mm 24mm 32mm 14mm;
          gap: 2.5mm;
          align-items: center;
          padding: 2.1mm 0;
          border-bottom: 0.2mm solid var(--rule);
          font-size: 9pt;
        }
        .rpr:last-child { border-bottom: 0; }
        .rpr.h {
          border-bottom: 0.3mm solid var(--rule-strong);
          padding-bottom: 2.4mm;
          padding-top: 0;
          font-family: var(--font-mono);
          font-size: 6.5pt;
          letter-spacing: 0.12em;
          color: var(--mute);
          text-transform: uppercase;
        }
        .rpr.h .cn {
          font-family: var(--font-sans-cn);
          font-size: 7.5pt;
          letter-spacing: 0.04em;
          text-transform: none;
          color: var(--deep);
          font-weight: 500;
        }

        .rpr .rk {
          font-family: var(--font-mono);
          font-size: 8pt;
          color: var(--mute);
          letter-spacing: 0.04em;
        }
        .rpr .buyer {
          font-family: var(--font-body);
          color: var(--deep);
          font-weight: 500;
          letter-spacing: -0.005em;
          line-height: 1.2;
          font-size: 9.5pt;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .rpr .city {
          font-family: var(--font-body);
          color: var(--mute);
          font-size: 8.5pt;
          line-height: 1.2;
          letter-spacing: 0;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .rpr .v {
          font-family: var(--font-body);
          color: var(--ink);
          font-variant-numeric: tabular-nums;
          font-weight: 500;
          font-size: 9.5pt;
          letter-spacing: -0.005em;
          text-align: left;
        }
        .rpr .ch {
          font-variant-numeric: tabular-nums;
          font-size: 9pt;
          letter-spacing: -0.005em;
          line-height: 1.2;
          display: flex;
          align-items: baseline;
          gap: 2mm;
          justify-content: flex-start;
        }
        .rpr .ch .pct {
          font-family: var(--font-body);
          font-weight: 500;
        }
        .rpr .ch.down .pct { color: var(--accent); }
        .rpr .ch.up   .pct { color: var(--gold);   }
        .rpr .ch.flat .pct { color: var(--mute);   }
        .rpr .ch .ct {
          font-family: var(--font-sans-cn);
          font-size: 7.5pt;
          color: var(--mute);
          letter-spacing: 0;
          white-space: nowrap;
        }
        .rpr .sc {
          font-family: var(--font-body);
          display: inline-flex;
          align-items: center;
          gap: 2mm;
          color: var(--accent);
          font-weight: 500;
          font-size: 10pt;
          font-variant-numeric: tabular-nums;
          justify-content: flex-start;
        }
        .rpr .sc .d {
          width: 2mm;
          height: 2mm;
          border-radius: 50%;
          background: var(--accent);
          flex-shrink: 0;
        }
        .rpr .sc.m { color: var(--gold); }
        .rpr .sc.m .d { background: var(--gold); }
        .rpr .sc-muted {
          font-family: var(--font-body);
          color: var(--mute);
          font-size: 10pt;
        }
      `}</style>

      <div className="sec-label">
        <span className="cn">按意向评分排序 · 全部 {total} 家</span>
        <span>Ranked by intent score · all {total}</span>
      </div>

      <div className="tbl-legend">
        供应商变化 · <span className="sw" style={{ background: 'var(--accent)' }}></span>绿色 = 减少 · <span className="sw" style={{ background: 'var(--gold)' }}></span>黄色 = 新增
      </div>

      <div className="tbl">
        <div className="rpr h">
          <div>#</div>
          <div><span className="cn">买家</span></div>
          <div><span className="cn">所在地</span></div>
          <div><span className="cn">年进口量</span></div>
          <div><span className="cn">同比供应商变化</span></div>
          <div><span className="cn">评分</span></div>
        </div>
        {buyers.map((b) => {
          const { pct, count, tone } = computeSupplierChange(b.cnPrevSupplierCount, b.cnCurrSupplierCount)
          const city = [b.city, b.state].filter(Boolean).join(', ')
          const rank2 = String(b.rank).padStart(2, '0')
          const scoreClass = b.score !== null && b.score >= 85 ? 'sc' : 'sc m'

          return (
            <div className="rpr" key={b.rank}>
              <div className="rk">{rank2}</div>
              <div className="buyer">{b.name}</div>
              <div className="city">{city || '—'}</div>
              <div className="v">{formatTons(b.annualVolumeTons)}</div>
              <div className={`ch ${tone}`}>
                {pct && <span className="pct">{pct}</span>}
                <span className="ct">{count}</span>
              </div>
              <div>
                {b.score !== null ? (
                  <span className={scoreClass}>
                    <span className="d"></span>{b.score}
                  </span>
                ) : (
                  <span className="sc-muted">—</span>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </>
  )
}
