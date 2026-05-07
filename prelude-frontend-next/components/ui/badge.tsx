import * as React from 'react'
import { cn } from '@/utils/cn'

const base =
  'inline-flex items-center rounded-full border px-2.5 py-0.5 font-mono text-[11px] font-medium uppercase tracking-[0.06em] whitespace-nowrap transition-colors focus:outline-none'

const variants = {
  default: 'border-transparent bg-primary text-primary-foreground',
  secondary: 'border-transparent bg-muted text-muted-foreground',
  destructive:
    'border-transparent bg-[oklch(0.960_0.018_30)] text-[oklch(0.420_0.180_30)]',
  outline: 'border-border bg-transparent text-foreground',
  // Semantic status variants using kit tokens
  success:
    'border-transparent bg-[oklch(0.960_0.020_160)] text-accent',
  danger:
    'border-transparent bg-[oklch(0.960_0.018_30)] text-[oklch(0.420_0.180_30)]',
  warning:
    'border-transparent bg-[oklch(0.960_0.040_85)] text-[oklch(0.450_0.100_85)]',
  info: 'border-transparent bg-muted text-muted-foreground',
  progress:
    'border-transparent bg-[oklch(0.960_0.040_85)] text-[oklch(0.450_0.100_85)]',
  neutral: 'border-transparent bg-muted text-muted-foreground',
} as const

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: keyof typeof variants
}

function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return <div className={cn(base, variants[variant], className)} {...props} />
}

export { Badge }
