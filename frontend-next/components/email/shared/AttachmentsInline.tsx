'use client'

import React, { useCallback, useRef } from 'react'
import { Paperclip, FileText, X } from 'lucide-react'
import { useTranslations } from 'next-intl'

export interface AttachmentsInlineProps {
  files: File[]
  onChange: (files: File[]) => void
  /** Phase 1: inert. When false, renders a "Coming soon" hint and disables the dropzone. */
  enabled?: boolean
}

const formatBytes = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const AttachmentsInline: React.FC<AttachmentsInlineProps> = ({
  files,
  onChange,
  enabled = false,
}) => {
  const t = useTranslations('email')
  const inputRef = useRef<HTMLInputElement>(null)

  const totalBytes = files.reduce((sum, f) => sum + f.size, 0)

  const handlePick = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const picked = Array.from(e.target.files || [])
      if (picked.length) onChange([...files, ...picked])
      // Reset input so picking the same file twice still fires onChange.
      if (inputRef.current) inputRef.current.value = ''
    },
    [files, onChange]
  )

  const handleRemove = useCallback(
    (idx: number) => {
      onChange(files.filter((_, i) => i !== idx))
    },
    [files, onChange]
  )

  const openPicker = () => {
    if (!enabled) return
    inputRef.current?.click()
  }

  return (
    <div className="compose-attachments-inline">
      <div className="att-head">
        <Paperclip />
        {files.length > 0 ? (
          <span>
            {t('composer.attachments.count', { count: files.length })} · {formatBytes(totalBytes)}
          </span>
        ) : (
          <span>{t('composer.attachments.empty')}</span>
        )}
        {!enabled && (
          <span className="ml-2 text-[11px] italic" title={t('composer.attachments.comingSoon')}>
            ({t('composer.attachments.comingSoon')})
          </span>
        )}
      </div>

      {files.map((f, idx) => (
        <div key={`${f.name}-${idx}`} className="file-chip">
          <FileText className="fi" />
          <span className="fname">{f.name}</span>
          <span className="fsize">{formatBytes(f.size)}</span>
          <button
            type="button"
            className="fremove"
            aria-label={t('composer.attachments.remove')}
            onClick={() => handleRemove(idx)}
          >
            <X size={12} />
          </button>
        </div>
      ))}

      {enabled && (
        <button type="button" className="att-dropzone" onClick={openPicker}>
          {t('composer.attachments.add')}
        </button>
      )}

      <input
        ref={inputRef}
        type="file"
        multiple
        hidden
        onChange={handlePick}
        disabled={!enabled}
      />
    </div>
  )
}

export default AttachmentsInline
