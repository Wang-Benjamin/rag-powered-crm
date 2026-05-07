'use client'

import * as React from 'react'

import { InlineLoader } from '@/components/ui/inline-loader'
import { cn } from '@/utils/cn'

const base =
  'inline-flex items-center justify-center rounded-[8px] font-medium transition-all duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[3px] focus-visible:outline-accent disabled:pointer-events-none disabled:opacity-50 disabled:cursor-not-allowed font-body'

const variants = {
  default:
    'bg-primary text-primary-foreground border border-primary hover:bg-accent hover:border-accent hover:-translate-y-px',
  primary:
    'bg-primary text-primary-foreground border border-primary hover:bg-accent hover:border-accent hover:-translate-y-px',
  secondary:
    'bg-transparent border border-border text-foreground hover:bg-muted hover:border-foreground',
  destructive:
    'bg-destructive text-destructive-foreground border border-destructive hover:bg-destructive/90',
  outline:
    'bg-transparent border border-border text-foreground hover:bg-muted hover:border-foreground',
  ghost: 'bg-transparent border border-transparent text-foreground hover:bg-muted',
  link: 'text-accent underline-offset-4 hover:underline border border-transparent',
} as const

const sizes = {
  default: 'px-4 py-[10px] text-sm',
  sm: 'px-[14px] py-2 text-[13px]',
  lg: 'px-[22px] py-[14px] text-[15px]',
  icon: 'h-10 w-10 p-2',
} as const

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof variants
  size?: keyof typeof sizes
  loading?: boolean
  loadingText?: string
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = 'default',
      size = 'default',
      disabled = false,
      loading = false,
      loadingText,
      children,
      ...props
    },
    ref
  ) => {
    const isDisabled = disabled || loading

    return (
      <button
        className={cn(base, variants[variant], sizes[size], className)}
        disabled={isDisabled}
        ref={ref}
        {...props}
      >
        {loading ? (
          <InlineLoader label={loadingText || 'Loading'} />
        ) : (
          children
        )}
      </button>
    )
  }
)
Button.displayName = 'Button'

export { Button }
