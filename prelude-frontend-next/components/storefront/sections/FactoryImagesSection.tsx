'use client'

import { useRef, useState } from 'react'
import { useTranslations } from 'next-intl'
import { Image as ImageIcon, Upload, X } from 'lucide-react'
import { toast } from 'sonner'
import type { UseFactoryProfileDraft } from '@/hooks/useFactoryProfileDraft'
import { SectionShell } from '../primitives'

interface FactoryImagesSectionProps {
  draft: UseFactoryProfileDraft
}

const ACCEPT = 'image/*'
const MAX_SIZE_MB = 15

export function FactoryImagesSection({ draft }: FactoryImagesSectionProps) {
  const t = useTranslations('storefront')
  const [uploading, setUploading] = useState(false)
  const [errored, setErrored] = useState<Set<string>>(new Set())
  const [isDragActive, setIsDragActive] = useState(false)
  const inputRef = useRef<HTMLInputElement | null>(null)

  const photos = draft.factoryDetails.photoUrls ?? []

  const handleFiles = async (files: FileList | File[] | null) => {
    if (!files || files.length === 0) return
    const arr = Array.from(files instanceof FileList ? files : files)
    const accepted: File[] = []
    for (const file of arr) {
      if (!file.type.startsWith('image/')) {
        toast.error(t('factoryImages.errorWrongType'))
        continue
      }
      if (file.size > MAX_SIZE_MB * 1024 * 1024) {
        toast.error(t('factoryImages.errorTooLarge', { maxSizeMB: MAX_SIZE_MB }))
        continue
      }
      accepted.push(file)
    }
    if (accepted.length === 0) return

    setUploading(true)
    try {
      // Sequential so order matches the user's drop order. The hook uses
      // a functional updater, so each upload appends safely.
      for (const file of accepted) {
        try {
          await draft.uploadFactoryPhoto(file)
        } catch (e: unknown) {
          const msg = e instanceof Error ? e.message : t('factoryImages.uploadFailed')
          toast.error(msg)
        }
      }
    } finally {
      setUploading(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  const handleRemove = (url: string) => {
    const next = photos.filter((p) => p !== url)
    draft.setFactoryField('photoUrls', next)
  }

  return (
    <SectionShell title={t('factoryImages.sectionTitle')}>
      <p className="mb-2 text-xs text-zinc-500">{t('factoryImages.dropHelper')}</p>
      <label
        onDragOver={(e) => {
          e.preventDefault()
          setIsDragActive(true)
        }}
        onDragLeave={(e) => {
          e.preventDefault()
          setIsDragActive(false)
        }}
        onDrop={(e) => {
          e.preventDefault()
          setIsDragActive(false)
          void handleFiles(e.dataTransfer.files)
        }}
        className={`flex cursor-pointer items-center gap-4 rounded-lg border border-dashed px-5 py-4 transition-colors ${
          isDragActive
            ? 'border-zinc-500 bg-zinc-100'
            : 'border-zinc-300 bg-zinc-50 hover:border-zinc-400 hover:bg-zinc-100'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          multiple
          className="sr-only"
          onChange={(e) => void handleFiles(e.target.files)}
        />
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-zinc-200 bg-white text-zinc-500">
          <Upload className="h-4 w-4" strokeWidth={1.5} />
        </div>
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="text-sm font-medium text-zinc-900">
            {uploading ? t('factoryImages.uploading') : t('factoryImages.dropLabel')}
          </span>
          <span className="text-xs text-zinc-500">
            {t('factoryImages.acceptHint', { maxSizeMB: MAX_SIZE_MB })}
          </span>
        </div>
      </label>

      {photos.length > 0 && (
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {photos.map((url) => (
            <div
              key={url}
              className="group relative aspect-[4/3] overflow-hidden rounded-md border border-zinc-200 bg-zinc-100"
            >
              {errored.has(url) ? (
                <div className="flex h-full w-full items-center justify-center text-zinc-400">
                  <ImageIcon className="h-6 w-6" strokeWidth={1.5} />
                </div>
              ) : (
                <img
                  src={url}
                  alt=""
                  loading="lazy"
                  onError={() =>
                    setErrored((prev) => {
                      const n = new Set(prev)
                      n.add(url)
                      return n
                    })
                  }
                  className="h-full w-full object-cover"
                />
              )}
              <button
                type="button"
                onClick={() => handleRemove(url)}
                aria-label={t('fileChip.removeAriaLabel')}
                className="absolute top-1.5 right-1.5 flex h-6 w-6 items-center justify-center rounded-full border border-zinc-200 bg-white text-zinc-400 opacity-0 transition-opacity group-hover:opacity-100 hover:text-zinc-900"
              >
                <X className="h-3 w-3" strokeWidth={2.5} />
              </button>
            </div>
          ))}
        </div>
      )}
    </SectionShell>
  )
}
