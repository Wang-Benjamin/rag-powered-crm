'use client'

import type { SignatureFields } from '@/types/email/signature'

interface SignaturePreviewProps {
  fields: SignatureFields
}

// Mirrors the Python renderer's output (12px text, 50px logo) so the in-product
// preview matches what recipients actually see.
export function SignaturePreview({ fields }: SignaturePreviewProps) {
  const hasContent = !!(
    fields.name ||
    fields.title ||
    fields.email ||
    fields.phoneNumber ||
    fields.location ||
    fields.link ||
    fields.logoUrl
  )

  if (!hasContent) {
    return (
      <div className="rounded-lg border border-rule bg-bone p-5">
        <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-mute mb-2">
          Preview
        </p>
        <p className="text-sm text-mute italic">
          Fill in your details on the left to see a preview.
        </p>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-rule bg-bone p-5">
      <p className="font-mono text-[11px] uppercase tracking-[0.1em] text-mute mb-2">
        Preview
      </p>
      <div
        className="text-ink"
        style={{ fontSize: '12px', lineHeight: 1.6, marginTop: '20px' }}
      >
        {fields.name && <div>{fields.name}</div>}
        {fields.title && <div>{fields.title}</div>}
        {fields.email && (
          <div>
            <a
              href={`mailto:${fields.email}`}
              className="text-deep underline"
            >
              {fields.email}
            </a>
          </div>
        )}
        {fields.phoneNumber && <div>{fields.phoneNumber}</div>}
        {fields.location && <div>{fields.location}</div>}
        {fields.link && (
          <div>
            <a
              href={fields.link}
              target="_blank"
              rel="noopener noreferrer"
              className="text-deep underline"
            >
              {fields.link}
            </a>
          </div>
        )}
      </div>
      {fields.logoUrl && (
        <img
          src={fields.logoUrl}
          alt="Signature logo"
          style={{ height: '50px', marginTop: '8px', display: 'block' }}
        />
      )}
    </div>
  )
}
