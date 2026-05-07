import * as React from 'react'
import * as TogglePrimitive from '@radix-ui/react-toggle'
import { cn } from '@/utils/cn'

const base =
  'inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:border focus-visible:border-accent disabled:pointer-events-none disabled:opacity-50'

const variants = {
  default:
    'bg-transparent hover:bg-cream hover:text-mute data-[state=on]:bg-cream data-[state=on]:text-ink',
  outline: 'border border-rule bg-transparent hover:bg-cream hover:text-ink',
} as const

const sizes = {
  default: 'h-10 px-3',
  sm: 'h-9 px-2.5',
  lg: 'h-11 px-5',
} as const

const Toggle = React.forwardRef<
  React.ElementRef<typeof TogglePrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof TogglePrimitive.Root> & {
    variant?: keyof typeof variants
    size?: keyof typeof sizes
  }
>(({ className, variant = 'default', size = 'default', ...props }, ref) => (
  <TogglePrimitive.Root
    ref={ref}
    className={cn(base, variants[variant], sizes[size], className)}
    {...props}
  />
))
Toggle.displayName = TogglePrimitive.Root.displayName

export { Toggle }
