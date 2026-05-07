'use client'

import React from 'react'
import type { TwoPagerData, TwoPagerBuyerContact } from './TwoPagerPage1'
import Page2Header from './page2/Page2Header'
import { formatTons, formatPct } from './format'

// ── Helpers ───────────────────────────────────────────────────────────────────

function buildMetaCn(c: TwoPagerBuyerContact): string {
  const parts: string[] = []
  if (c.annualVolumeTons !== null) parts.push(formatTons(c.annualVolumeTons))
  if (c.trendYoyPct !== null) parts.push(`同比 ${formatPct(c.trendYoyPct)}`)
  if (c.cnPrevSupplierCount !== null && c.cnCurrSupplierCount !== null) {
    parts.push(`供应商 ${c.cnPrevSupplierCount}→${c.cnCurrSupplierCount}家`)
  }
  if (c.cnSubheader) parts.push(c.cnSubheader)
  return parts.join(' · ')
}

/**
 * Renders an emailBody string, wrapping [CONTACT NAME] / [COMPANY NAME] and
 * the design's placeholder-style tokens like [product category] or $X.XX in a
 * highlight span so users see they are unfilled.
 */
function renderEmailBodyWithPlaceholders(body: string): React.ReactNode {
  const pattern = /(\[[^\]]+\]|\$X\.XX|\$X\.XM)/
  const parts = body.split(pattern)
  return parts.map((part, i) =>
    i % 2 === 1 ? (
      <span key={i} className="hl">{part}</span>
    ) : (
      <React.Fragment key={i}>{part}</React.Fragment>
    ),
  )
}

// ── Contact Card ──────────────────────────────────────────────────────────────

interface ContactCardProps {
  contact: TwoPagerBuyerContact
  index: number
}

function ContactCard({ contact, index }: ContactCardProps) {
  const rank = String(index + 1).padStart(2, '0')
  const meta = buildMetaCn(contact)
  const city = contact.location || ''
  const title = contact.contactTitle || '职位未知 / Title unknown'

  return (
    <div className="p2-contact">
      <div className="rk">
        {rank} · <b>{contact.buyerName}</b>{city ? <> · {city}</> : null}
      </div>
      <div className="nm">
        {contact.contactName} · {title}
      </div>
      <div className="dt">
        <span className="mono">{contact.contactEmail}</span>
        {meta ? <> · {meta}</> : null}
      </div>
      {contact.emailSubject && (
        <div className="em">
          <span className="sb">{contact.emailSubject}</span>
          <p>{contact.emailBody && renderEmailBodyWithPlaceholders(contact.emailBody)}</p>
        </div>
      )}
    </div>
  )
}

// ── Component ─────────────────────────────────────────────────────────────────

interface TwoPagerPage2Props {
  data: TwoPagerData
}

const TOTAL_CARD_SLOTS = 3

export default function TwoPagerPage2({ data }: TwoPagerPage2Props) {
  const { buyerContacts } = data
  const cards = buyerContacts.slice(0, TOTAL_CARD_SLOTS)

  return (
    <div className="two-pager-root two-pager-page2 page">
      <style>{`
        /* Page 2 inherits --bone/--paper/--ink/--mute/etc from .two-pager-root */
        .two-pager-page2 { break-before: page; }

        /* ── Decision-maker cards ── */
        .contacts {
          display: flex;
          flex-direction: column;
          gap: 5mm;
          flex: 1;
          min-height: 0;
          margin-bottom: 6mm;
          overflow: hidden;
        }
        .p2-contact {
          border: 0.25mm solid var(--rule);
          border-left: 0.6mm solid var(--accent);
          border-radius: 1.2mm;
          padding: 4.5mm 5mm;
          background: var(--paper);
        }
        .p2-contact .rk {
          font-family: var(--font-mono);
          font-size: 7pt;
          letter-spacing: 0.12em;
          color: var(--mute);
          text-transform: uppercase;
          margin-bottom: 2mm;
          display: flex;
          align-items: center;
          gap: 2mm;
          flex-wrap: wrap;
        }
        .p2-contact .rk b { color: var(--deep); font-weight: 500; }
        .p2-contact .nm {
          font-family: var(--font-body);
          font-weight: 500;
          font-size: 11pt;
          color: var(--deep);
          letter-spacing: -0.005em;
          margin-bottom: 1.2mm;
          line-height: 1.25;
        }
        .p2-contact .dt {
          font-family: var(--font-sans-cn);
          font-size: 8.5pt;
          color: var(--mute);
          letter-spacing: 0;
          margin-bottom: 3mm;
          line-height: 1.5;
        }
        .p2-contact .dt .mono {
          font-family: var(--font-mono);
          font-size: 8pt;
          color: var(--ink);
        }

        /* Email block */
        .em {
          background: var(--bone);
          border: 0.2mm solid var(--rule);
          border-radius: 1mm;
          padding: 3.5mm 4mm;
        }
        .em .sb {
          display: block;
          font-family: var(--font-body);
          font-weight: 500;
          font-size: 9.5pt;
          color: var(--deep);
          letter-spacing: -0.005em;
          margin-bottom: 2mm;
          line-height: 1.3;
        }
        .em p {
          font-family: var(--font-body);
          font-size: 9pt;
          color: var(--ink);
          margin: 0;
          line-height: 1.55;
          white-space: pre-wrap;
          display: -webkit-box;
          -webkit-line-clamp: 6;
          -webkit-box-orient: vertical;
          overflow: hidden;
        }
        .em p .hl {
          background: color-mix(in oklab, var(--accent) 16%, transparent);
          padding: 0 2px;
          border-radius: 1px;
        }

        /* ── Paywall CTA (design: .p2-cta) ── */
        .p2-cta {
          margin: 0 -18mm -15mm;
          padding: 7mm 18mm;
          background: var(--deep);
          color: var(--bone);
          display: grid;
          grid-template-columns: 1fr auto;
          gap: 8mm;
          align-items: center;
          box-sizing: border-box;
        }
        .p2-cta-body { font-family: var(--font-sans-cn); }
        .p2-cta-ln {
          font-size: 9.5pt;
          line-height: 1.6;
          color: color-mix(in oklab, var(--bone) 82%, var(--deep));
          max-width: 125mm;
          letter-spacing: 0.01em;
        }
        .p2-cta-ln b { color: var(--bone); font-weight: 600; }
        .p2-cta-price {
          text-align: right;
          display: flex;
          align-items: baseline;
          gap: 2mm;
          white-space: nowrap;
        }
        .p2-cta-price .p2-price {
          font-family: var(--font-display);
          font-size: 30pt;
          color: var(--bone);
          line-height: 1;
          letter-spacing: -0.01em;
        }
        .p2-cta-price .p2-per {
          font-family: var(--font-sans-cn);
          font-size: 9.5pt;
          color: color-mix(in oklab, var(--bone) 72%, var(--deep));
          letter-spacing: 0.02em;
        }
      `}</style>

      <Page2Header data={data} />

      <div className="sec-label">
        <span className="cn">前 {TOTAL_CARD_SLOTS} 位联系人</span>
        <span>Top {TOTAL_CARD_SLOTS} contacts · ready to send</span>
      </div>

      <div className="contacts">
        {cards.map((contact, i) => (
          <ContactCard key={contact.buyerSlug + i} contact={contact} index={i} />
        ))}
      </div>

      <div className="p2-cta">
        <div className="p2-cta-body">
          <div className="p2-cta-ln">
            本报告覆盖品类 <b>Top {TOTAL_CARD_SLOTS}</b> 决策人 · <b>付费版</b>每月刷新 <b>250+</b> 买家，按具体产品定制，含完整联系方式和自动开发信。
          </div>
        </div>
        <div className="p2-cta-price">
          <span className="p2-price">¥8,999</span>
          <span className="p2-per">/ 季</span>
        </div>
      </div>
    </div>
  )
}
