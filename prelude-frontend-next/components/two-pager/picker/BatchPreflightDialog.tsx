'use client'

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'

interface BatchPreflightDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  multiSelected: Set<string>
  onConfirm: () => void
  IY_CREDITS_PER_REPORT: number
  APOLLO_COST_PER_REPORT: number
}

export default function BatchPreflightDialog({
  open,
  onOpenChange,
  multiSelected,
  onConfirm,
  IY_CREDITS_PER_REPORT,
  APOLLO_COST_PER_REPORT,
}: BatchPreflightDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        style={{ maxWidth: 420, background: 'var(--bone)', border: '1px solid var(--rule)', color: 'var(--ink)' }}
      >
        <DialogHeader>
          <DialogTitle style={{ fontFamily: "'Instrument Serif', 'Times New Roman', serif", fontSize: 20, fontWeight: 400, color: 'var(--deep)' }}>
            Confirm Batch Generation
          </DialogTitle>
        </DialogHeader>
        <div style={{ fontFamily: "'Geist', ui-sans-serif, system-ui, sans-serif", fontSize: 14, color: 'var(--mute)', lineHeight: 1.6, marginTop: 4 }}>
          Generating reports for <strong style={{ color: 'var(--ink)', fontWeight: 600 }}>{multiSelected.size}</strong> HS codes will use approximately:
        </div>
        <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ padding: '10px 14px', borderRadius: 8, background: 'var(--paper)', border: '1px solid var(--rule)', fontFamily: "'JetBrains Mono', ui-monospace, monospace", fontSize: 13 }}>
            <span style={{ color: 'var(--mute)' }}>IY Credits </span>
            <span style={{ color: 'var(--gold)', fontWeight: 500 }}>~{multiSelected.size * IY_CREDITS_PER_REPORT}</span>
          </div>
          <div style={{ padding: '10px 14px', borderRadius: 8, background: 'var(--paper)', border: '1px solid var(--rule)', fontFamily: "'JetBrains Mono', ui-monospace, monospace", fontSize: 13 }}>
            <span style={{ color: 'var(--mute)' }}>Apollo Cost </span>
            <span style={{ color: 'var(--gold)', fontWeight: 500 }}>${(multiSelected.size * APOLLO_COST_PER_REPORT).toFixed(2)}</span>
          </div>
        </div>
        <p style={{ fontSize: 11, color: 'var(--mute)', fontFamily: "'JetBrains Mono', ui-monospace, monospace", marginTop: 8, letterSpacing: '0.04em' }}>
          Reports run in parallel. Partial success is preserved if any fail.
        </p>
        <DialogFooter style={{ marginTop: 16, gap: 8 }}>
          <button
            onClick={() => onOpenChange(false)}
            className="tp-btn-cancel"
            style={{
              padding: '9px 18px',
              borderRadius: 8,
              border: '1px solid var(--rule)',
              background: 'transparent',
              color: 'var(--mute)',
              fontSize: 13,
              fontFamily: "'Geist', ui-sans-serif, system-ui, sans-serif",
              cursor: 'pointer',
              transition: 'background 0.15s',
            }}
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="tp-btn-confirm"
            style={{
              padding: '9px 18px',
              borderRadius: 8,
              border: '1px solid var(--deep)',
              background: 'var(--deep)',
              color: 'var(--bone)',
              fontSize: 13,
              fontFamily: "'Geist', ui-sans-serif, system-ui, sans-serif",
              fontWeight: 500,
              cursor: 'pointer',
              transition: 'background 0.15s, border-color 0.15s',
            }}
          >
            Continue
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
