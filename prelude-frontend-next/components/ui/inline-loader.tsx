import type { ReactNode } from 'react'

import { cn } from '@/utils/cn'

interface InlineLoaderProps {
  label: ReactNode
  className?: string
}

export function InlineLoader({ label, className }: InlineLoaderProps) {
  return (
    <span className={cn('loading-inline', className)} role="status" aria-live="polite">
      <span className="word">{label}</span>
    </span>
  )
}
