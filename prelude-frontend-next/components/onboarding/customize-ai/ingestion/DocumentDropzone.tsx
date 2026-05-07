'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslations } from 'next-intl'
import { AlertCircle, CheckCircle2, Loader2, Upload, X } from 'lucide-react'
import { cn } from '@/utils/cn'
import { ingestionApi } from '@/lib/api/ingestion'
import type { DraftPayload, DropzoneState, JobKind } from './types'

interface DocumentDropzoneProps {
  /**
   * Lane to upload to. Either a fixed `JobKind` (the original wizard usage)
   * or a resolver that picks the lane from the chosen file — used by the
   * storefront's combined PDF + CSV/XLSX upload portal where the user
   * shouldn't have to pick the format up-front.
   */
  kind: JobKind | ((file: File) => JobKind)
  /** Accept attribute for the file input — MIME list per lane. */
  accept: string
  /**
   * Human-friendly label shown in the idle hint (e.g. "PDF"). Falls back to
   * the raw ``accept`` string, which is ugly — callers should pass this.
   */
  acceptLabel?: string
  /** Rejected above this size. */
  maxSizeMB: number
  /** Called once the backend returns `ready_for_review`. */
  onReady: (draft: DraftPayload, jobId: string) => void
  /** Called on size/MIME rejection or terminal extractor failure. */
  onFailed: (message: string) => void
  /**
   * Called with the accepted ``File`` once it passes MIME + size checks and
   * before the upload begins, and again with ``null`` whenever the dropzone
   * resets (Replace / Try again / failure). Lets the parent reuse the same
   * file for a separate POST so the user only drags once.
   */
  onFileStaged?: (file: File | null) => void
  /** Optional one-line label above the dropzone. */
  label?: string
  /** Visual density — `compact` used inside modals. */
  size?: 'default' | 'compact'
  className?: string
}

const POLL_INTERVAL_MS = 2000
const POLL_CEILING_MS = 120_000

function friendlyBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function DocumentDropzone({
  kind,
  accept,
  acceptLabel,
  maxSizeMB,
  onReady,
  onFailed,
  onFileStaged,
  label,
  size = 'default',
  className,
}: DocumentDropzoneProps) {
  const t = useTranslations('settings.customizeAi.ingestion')

  const [state, setState] = useState<DropzoneState>('idle')
  const [filename, setFilename] = useState<string | null>(null)
  const [fileSize, setFileSize] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [jobId, setJobId] = useState<string | null>(null)
  const [isDragActive, setIsDragActive] = useState(false)

  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const startedAt = useRef<number | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)

  // Stop polling when the component unmounts or we leave `processing`.
  const clearPolling = useCallback(() => {
    if (pollTimer.current) {
      clearTimeout(pollTimer.current)
      pollTimer.current = null
    }
  }, [])
  useEffect(() => () => clearPolling(), [clearPolling])

  const fail = useCallback(
    (message: string) => {
      clearPolling()
      setState('failed')
      setError(message)
      onFailed(message)
      onFileStaged?.(null)
    },
    [clearPolling, onFailed, onFileStaged],
  )

  const reset = useCallback(() => {
    clearPolling()
    setState('idle')
    setFilename(null)
    setFileSize(null)
    setError(null)
    setJobId(null)
    startedAt.current = null
    if (inputRef.current) inputRef.current.value = ''
    onFileStaged?.(null)
  }, [clearPolling, onFileStaged])

  const pollOnce = useCallback(
    async (id: string) => {
      try {
        const job = await ingestionApi.getJob(id)
        if (job.status === 'ready_for_review') {
          clearPolling()
          setState('ready')
          const payload = (job.draftPayload ?? {}) as DraftPayload
          onReady(payload, id)
          return
        }
        if (job.status === 'failed') {
          fail(job.error || t('errors.extractionFailed'))
          return
        }
        if (job.status === 'committed' || job.status === 'discarded') {
          clearPolling()
          return
        }
        // still processing — check the ceiling then schedule the next tick
        if (startedAt.current && Date.now() - startedAt.current > POLL_CEILING_MS) {
          fail(t('errors.timeout'))
          return
        }
        pollTimer.current = setTimeout(() => pollOnce(id), POLL_INTERVAL_MS)
      } catch (e) {
        fail(e instanceof Error ? e.message : t('errors.unknown'))
      }
    },
    [clearPolling, fail, onReady, t],
  )

  const handleFiles = useCallback(
    async (files: FileList | File[] | null) => {
      if (!files || files.length === 0) return
      const file = files instanceof FileList ? files[0] : files[0]
      if (!file) return

      // MIME / extension check — accept string is a comma list.
      const acceptTokens = accept.split(',').map((s) => s.trim()).filter(Boolean)
      const accepted =
        acceptTokens.length === 0 ||
        acceptTokens.some((tok) => {
          if (tok.startsWith('.')) return file.name.toLowerCase().endsWith(tok.toLowerCase())
          if (tok.endsWith('/*')) return file.type.startsWith(tok.slice(0, -1))
          return file.type === tok
        })
      if (!accepted) {
        fail(t('errors.wrongType', { accept }))
        return
      }
      if (file.size > maxSizeMB * 1024 * 1024) {
        fail(t('errors.tooLarge', { maxSizeMB }))
        return
      }

      setFilename(file.name)
      setFileSize(file.size)
      setError(null)
      setState('uploading')
      onFileStaged?.(file)

      try {
        const resolvedKind = typeof kind === 'function' ? kind(file) : kind
        const job = await ingestionApi.upload(file, resolvedKind)
        setJobId(job.jobId)
        startedAt.current = Date.now()
        if (job.status === 'ready_for_review') {
          setState('ready')
          onReady((job.draftPayload ?? {}) as DraftPayload, job.jobId)
          return
        }
        if (job.status === 'failed') {
          fail(job.error || t('errors.extractionFailed'))
          return
        }
        setState('processing')
        pollTimer.current = setTimeout(() => pollOnce(job.jobId), POLL_INTERVAL_MS)
      } catch (e) {
        fail(e instanceof Error ? e.message : t('errors.uploadFailed'))
      }
    },
    [accept, fail, kind, maxSizeMB, onFileStaged, onReady, pollOnce, t],
  )

  // ===== drag-and-drop handlers =====
  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragActive(true)
  }, [])
  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragActive(false)
  }, [])
  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setIsDragActive(false)
      if (state === 'idle' || state === 'failed') {
        void handleFiles(e.dataTransfer.files)
      }
    },
    [handleFiles, state],
  )

  // ===== render =====

  const padding = size === 'compact' ? 'p-4' : 'p-6'
  const baseFrame =
    'rounded-lg border border-dashed transition-colors bg-zinc-50 dark:bg-zinc-900/40'

  if (state === 'uploading' || state === 'processing') {
    return (
      <div
        className={cn(
          baseFrame,
          'border-zinc-300 dark:border-zinc-700',
          padding,
          className,
        )}
        aria-live="polite"
      >
        <div className="flex items-center gap-3">
          <Loader2 className="h-5 w-5 animate-spin text-zinc-500" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100 truncate">
              {state === 'uploading' ? t('state.uploading') : t('state.processing')}
            </p>
            {filename && (
              <p className="text-xs text-zinc-500 truncate">
                {filename}
                {fileSize != null ? ` · ${friendlyBytes(fileSize)}` : ''}
              </p>
            )}
          </div>
        </div>
      </div>
    )
  }

  if (state === 'ready') {
    return (
      <div
        className={cn(
          baseFrame,
          'border-emerald-300 bg-emerald-50 dark:border-emerald-800/60 dark:bg-emerald-950/30',
          padding,
          className,
        )}
        aria-live="polite"
      >
        <div className="flex items-start gap-3">
          <CheckCircle2 className="h-5 w-5 text-emerald-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-emerald-900 dark:text-emerald-100">
              {t('state.ready')}
            </p>
            <p className="text-xs text-emerald-800/80 dark:text-emerald-200/80 mt-0.5">
              {t('state.readyHint', { filename: filename ?? '' })}
            </p>
          </div>
          <button
            type="button"
            onClick={reset}
            className="text-xs text-emerald-900/70 hover:text-emerald-900 underline-offset-2 hover:underline"
          >
            {t('action.replace')}
          </button>
        </div>
      </div>
    )
  }

  if (state === 'failed') {
    return (
      <div
        className={cn(
          baseFrame,
          'border-red-300 bg-red-50 dark:border-red-900/60 dark:bg-red-950/30',
          padding,
          className,
        )}
        aria-live="assertive"
      >
        <div className="flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-red-900 dark:text-red-100">
              {t('state.failed')}
            </p>
            <p className="text-xs text-red-800/80 dark:text-red-200/80 mt-0.5">
              {error || t('errors.unknown')}
            </p>
          </div>
          <button
            type="button"
            onClick={reset}
            className="text-xs text-red-900/70 hover:text-red-900 underline-offset-2 hover:underline"
          >
            {t('action.tryAgain')}
          </button>
        </div>
      </div>
    )
  }

  // idle
  return (
    <div className={className}>
      {label && (
        <p className="text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1.5">{label}</p>
      )}
      <label
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        className={cn(
          baseFrame,
          'block cursor-pointer hover:border-zinc-400 hover:bg-zinc-100/60 dark:hover:bg-zinc-900',
          isDragActive && 'border-zinc-500 bg-zinc-100 dark:bg-zinc-900',
          'border-zinc-300 dark:border-zinc-700',
          padding,
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          className="sr-only"
          onChange={(e) => void handleFiles(e.target.files)}
        />
        <div className="flex items-center gap-3">
          <Upload className="h-5 w-5 text-zinc-500 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
              {t('state.idle.title')}
            </p>
            <p className="text-xs text-zinc-500 mt-0.5">
              {t('state.idle.hint', { accept: acceptLabel ?? accept, maxSizeMB })}
            </p>
          </div>
        </div>
      </label>
    </div>
  )
}

/** Tiny helper so callers can dismiss the "auto-filled" story manually. */
function DropzoneDiscardButton({ onClick }: { onClick: () => void }) {
  const t = useTranslations('settings.customizeAi.ingestion')
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-700"
    >
      <X className="h-3.5 w-3.5" />
      {t('action.startOver')}
    </button>
  )
}
