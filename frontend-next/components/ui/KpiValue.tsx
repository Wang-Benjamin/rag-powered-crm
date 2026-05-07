import { cn } from '@/utils/cn'
import type { CSSProperties, ReactNode } from 'react'

const ACCENT_CLASS = {
  deep: 'text-deep',
  accent: 'text-accent',
  gold: 'text-gold',
  threat: 'text-threat',
} as const

export interface KpiValueProps {
  children: ReactNode
  accent?: keyof typeof ACCENT_CLASS
  className?: string
  style?: CSSProperties
}

export function KpiValue({ children, accent = 'deep', className, style }: KpiValueProps) {
  return (
    <span
      className={cn(
        'font-display text-[40px] leading-none tracking-[-0.015em] tabular-nums',
        ACCENT_CLASS[accent],
        className,
      )}
      style={style}
    >
      {children}
    </span>
  )
}
