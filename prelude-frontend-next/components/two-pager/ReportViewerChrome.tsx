'use client'

import TwoPagerPage1, { type TwoPagerData } from '@/components/two-pager/TwoPagerPage1'
import TwoPagerPage2 from '@/components/two-pager/TwoPagerPage2'

interface ReportViewerChromeProps {
  data: TwoPagerData
  backLabel: string
  onBack: () => void
}

export default function ReportViewerChrome({ data, backLabel, onBack }: ReportViewerChromeProps) {
  const handlePrint = () => window.print()

  return (
    <div className="two-pager-outer" style={{ background: 'var(--bone)', minHeight: '100vh' }}>
      <style>{`
        @media print {
          html, body { margin: 0 !important; padding: 0 !important; background: #ffffff !important; }
          .two-pager-outer { background: #ffffff !important; padding: 0 !important; min-height: 0 !important; }
          .two-pager-outer > .two-pager-stage { padding: 0 !important; margin: 0 !important; display: block !important; }
          .two-pager-outer > .two-pager-stage > div { margin: 0 !important; padding: 0 !important; }
          .no-print { display: none !important; }
        }
        .tp-btn-back:not(:disabled):hover { background: var(--cream) !important; border-color: var(--ink) !important; }
        .tp-btn-back:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
        .tp-btn-print:not(:disabled):hover { background: var(--accent) !important; border-color: var(--accent) !important; }
        .tp-btn-print:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
      `}</style>
      <div className="no-print" style={{ position: 'fixed', top: 16, right: 16, zIndex: 50, display: 'flex', gap: 8, alignItems: 'center' }}>
        <button
          onClick={onBack}
          className="tp-btn-back"
          style={{
            padding: '8px 14px',
            borderRadius: 8,
            border: '1px solid var(--rule)',
            background: 'transparent',
            color: 'var(--ink)',
            fontSize: 13,
            cursor: 'pointer',
            fontFamily: "'JetBrains Mono', ui-monospace, monospace",
            transition: 'background 0.15s, border-color 0.15s',
          }}
        >
          ← {backLabel}
        </button>
        <button
          onClick={handlePrint}
          className="tp-btn-print"
          style={{
            padding: '8px 14px',
            borderRadius: 8,
            border: '1px solid var(--deep)',
            background: 'var(--deep)',
            color: 'var(--bone)',
            fontSize: 13,
            cursor: 'pointer',
            fontFamily: "'JetBrains Mono', ui-monospace, monospace",
            fontWeight: 500,
            transition: 'background 0.15s, border-color 0.15s',
          }}
        >
          Print / PDF
        </button>
      </div>
      <div className="two-pager-stage" style={{ display: 'flex', justifyContent: 'center', padding: '40px 16px' }}>
        <div>
          <TwoPagerPage1 data={data} />
          <TwoPagerPage2 data={data} />
        </div>
      </div>
    </div>
  )
}
