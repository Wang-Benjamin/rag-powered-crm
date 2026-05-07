'use client'

import { type TwoPagerData } from '@/components/two-pager/TwoPagerPage1'

interface HsCodeItem {
  code: string
  description: string
  confirmed?: boolean
}

interface BatchResult {
  hsCode: string
  description: string
  data: TwoPagerData | null
  error?: string
}

interface HsCodeSelectionSectionProps {
  hsCodes: HsCodeItem[]
  selectedCode: string | null
  setSelectedCode: (code: string | null) => void
  setSelectedDescription: (desc: string) => void
  multiSelected: Set<string>
  toggleMultiSelect: (code: string) => void
  MAX_BATCH_SELECT: number
  isPickerDisabled: boolean
  batchGenerating: boolean
  batchResults: BatchResult[]
  setBatchResults: (results: BatchResult[]) => void
  setShowPreflightModal: (show: boolean) => void
  setBatchViewReport: (data: TwoPagerData | null) => void
}

export default function HsCodeSelectionSection({
  hsCodes,
  selectedCode,
  setSelectedCode,
  setSelectedDescription,
  multiSelected,
  toggleMultiSelect,
  MAX_BATCH_SELECT,
  isPickerDisabled,
  batchGenerating,
  batchResults,
  setBatchResults,
  setShowPreflightModal,
  setBatchViewReport,
}: HsCodeSelectionSectionProps) {
  return (
    <div style={{ marginBottom: 28 }}>
      <style>{`
        .tp-hs-card:hover { border-color: var(--ink) !important; }
        .tp-hs-card:focus-visible { border-color: var(--ink) !important; outline: 2px solid var(--accent); outline-offset: 2px; }
        .tp-btn-clear:not(:disabled):hover { background: var(--cream) !important; }
        .tp-btn-clear:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
        .tp-btn-view-print:not(:disabled):hover { background: var(--cream) !important; border-color: var(--ink) !important; }
        .tp-btn-view-print:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{
          fontFamily: "'JetBrains Mono', ui-monospace, monospace",
          fontSize: 11,
          fontWeight: 500,
          letterSpacing: '0.14em',
          textTransform: 'uppercase' as const,
          color: 'var(--mute)',
        }}>
          Your HS Codes / 您的HS编码
        </div>
        {multiSelected.size > 0 && (
          <div style={{ fontFamily: "'JetBrains Mono', ui-monospace, monospace", fontSize: 11, color: 'var(--accent)', letterSpacing: '0.04em' }}>
            Selected: {multiSelected.size} / {MAX_BATCH_SELECT}
          </div>
        )}
      </div>

      {hsCodes.length === 0 ? (
        <div style={{ padding: '16px', borderRadius: 12, background: 'var(--paper)', border: '1px solid var(--rule)', color: 'var(--mute)', fontSize: 13, fontFamily: "'Geist', ui-sans-serif, system-ui, sans-serif" }}>
          No HS codes in your profile. Complete onboarding or use Manual Entry below.
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
          {hsCodes.map((hs) => {
            const isActive = selectedCode === hs.code
            const isChecked = multiSelected.has(hs.code)
            const atCap = multiSelected.size >= MAX_BATCH_SELECT && !isChecked
            return (
              <div
                key={hs.code}
                className="tp-hs-card"
                style={{
                  position: 'relative',
                  borderRadius: 12,
                  border: isChecked
                    ? '1px solid var(--accent)'
                    : isActive
                    ? '1px solid var(--accent)'
                    : '1px solid var(--rule)',
                  background: isChecked
                    ? 'var(--accent-lo)'
                    : isActive
                    ? 'var(--accent-lo)'
                    : 'var(--paper)',
                  transition: 'border-color 0.15s, background 0.15s',
                }}
              >
                {/* Checkbox in top-right corner */}
                <button
                  onClick={(e) => { e.stopPropagation(); toggleMultiSelect(hs.code) }}
                  disabled={isPickerDisabled || (atCap)}
                  title={atCap ? `Max ${MAX_BATCH_SELECT} selections` : isChecked ? 'Deselect' : 'Add to batch'}
                  style={{
                    position: 'absolute',
                    top: 8,
                    right: 8,
                    width: 16,
                    height: 16,
                    borderRadius: 3,
                    border: isChecked ? '1px solid var(--accent)' : '1px solid var(--rule)',
                    background: isChecked ? 'var(--accent-lo)' : 'transparent',
                    cursor: isPickerDisabled || atCap ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: 0,
                    flexShrink: 0,
                    opacity: atCap ? 0.35 : 1,
                  }}
                  aria-label={isChecked ? `Deselect ${hs.code}` : `Select ${hs.code} for batch`}
                >
                  {isChecked && (
                    <svg width="9" height="9" viewBox="0 0 9 9" fill="none">
                      <path d="M1.5 4.5L3.5 6.5L7.5 2.5" stroke="var(--accent)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                </button>
                {/* Card body — single-click selects for single-report (disabled when batch results showing) */}
                <button
                  onClick={() => { setSelectedCode(hs.code); setSelectedDescription(hs.description) }}
                  disabled={isPickerDisabled}
                  style={{
                    width: '100%',
                    padding: '14px 32px 14px 16px',
                    borderRadius: 12,
                    border: 'none',
                    background: 'transparent',
                    cursor: isPickerDisabled ? 'wait' : 'pointer',
                    textAlign: 'left',
                  }}
                >
                  <div style={{ fontFamily: "'JetBrains Mono', ui-monospace, monospace", fontSize: 13, fontWeight: 500, color: isActive || isChecked ? 'var(--accent)' : 'var(--deep)', letterSpacing: '0.03em', marginBottom: 4 }}>
                    {hs.code}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--mute)', lineHeight: 1.4, fontFamily: "'Geist', ui-sans-serif, system-ui, sans-serif" }}>
                    {hs.description}
                  </div>
                </button>
              </div>
            )
          })}
        </div>
      )}

      {/* Batch progress indicator */}
      {batchGenerating && (
        <div style={{ marginTop: 14, display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px', borderRadius: 12, background: 'var(--paper)', border: '1px solid var(--rule)' }}>
          <div style={{ width: 16, height: 16, border: '2px solid var(--rule)', borderTop: '2px solid var(--accent)', borderRadius: '50%', animation: 'spin 1s linear infinite', flexShrink: 0 }} />
          <div style={{ fontFamily: "'JetBrains Mono', ui-monospace, monospace", fontSize: 12, color: 'var(--mute)', letterSpacing: '0.04em' }}>
            Generating {multiSelected.size} reports...
          </div>
        </div>
      )}

      {/* Batch results list */}
      {!batchGenerating && batchResults.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <div style={{
              fontFamily: "'JetBrains Mono', ui-monospace, monospace",
              fontSize: 11,
              fontWeight: 500,
              letterSpacing: '0.14em',
              textTransform: 'uppercase' as const,
              color: 'var(--mute)',
            }}>
              Batch Results — {batchResults.filter((r) => r.data).length} succeeded, {batchResults.filter((r) => !r.data).length} failed
            </div>
            {/* Fix 5: Clear results button re-enables the picker */}
            <button
              onClick={() => setBatchResults([])}
              className="tp-btn-clear"
              style={{
                padding: '3px 10px',
                borderRadius: 4,
                border: '1px solid var(--rule)',
                background: 'transparent',
                color: 'var(--mute)',
                fontSize: 11,
                fontFamily: "'JetBrains Mono', ui-monospace, monospace",
                cursor: 'pointer',
                whiteSpace: 'nowrap' as const,
                transition: 'background 0.15s',
              }}
            >
              Clear results
            </button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {batchResults.map((r) => (
              <div
                key={r.hsCode}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 14px',
                  borderRadius: 8,
                  border: r.data
                    ? '1px solid oklch(0.420 0.070 160 / 0.35)'
                    : '1px solid oklch(0.85 0.040 20)',
                  background: r.data
                    ? 'var(--accent-lo)'
                    : 'oklch(0.97 0.010 20)',
                  gap: 12,
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontFamily: "'JetBrains Mono', ui-monospace, monospace", fontSize: 12, fontWeight: 500, color: r.data ? 'var(--accent)' : 'oklch(0.45 0.12 20)', letterSpacing: '0.03em' }}>
                    {r.hsCode}
                  </div>
                  {r.error && (
                    <div style={{ fontSize: 11, color: 'oklch(0.50 0.10 20)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const, fontFamily: "'JetBrains Mono', ui-monospace, monospace" }}>
                      {r.error}
                    </div>
                  )}
                </div>
                {r.data && (
                  <button
                    onClick={() => setBatchViewReport(r.data)}
                    className="tp-btn-view-print"
                    style={{
                      flexShrink: 0,
                      padding: '5px 12px',
                      borderRadius: 6,
                      border: '1px solid var(--rule)',
                      background: 'transparent',
                      color: 'var(--ink)',
                      fontSize: 11,
                      fontFamily: "'JetBrains Mono', ui-monospace, monospace",
                      fontWeight: 500,
                      cursor: 'pointer',
                      whiteSpace: 'nowrap' as const,
                      transition: 'background 0.15s, border-color 0.15s',
                    }}
                  >
                    View / Print
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
