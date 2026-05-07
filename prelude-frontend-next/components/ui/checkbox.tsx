'use client'

import * as React from 'react'
import { Check } from 'lucide-react'
import { cn } from '@/utils/cn'

export interface CheckboxProps extends Omit<
  React.InputHTMLAttributes<HTMLInputElement>,
  'checked' | 'onChange'
> {
  checked?: boolean
  onCheckedChange?: (checked: boolean) => void
}

const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, checked, onCheckedChange, ...props }, ref) => (
    <div className="relative">
      <input
        ref={ref}
        type="checkbox"
        checked={checked}
        onChange={(e) => onCheckedChange?.(e.target.checked)}
        className="sr-only"
        {...props}
      />
      <div
        className={cn(
          'peer h-4 w-4 shrink-0 cursor-pointer rounded-sm border transition-colors',
          checked
            ? 'border-deep bg-deep'
            : 'border-rule bg-bone hover:border-mute',
          'focus:outline-none disabled:cursor-not-allowed disabled:opacity-50',
          className
        )}
        onClick={() => onCheckedChange?.(!checked)}
      >
        {checked && (
          <div className="flex items-center justify-center">
            <Check className="h-3 w-3 text-bone" />
          </div>
        )}
      </div>
    </div>
  )
)
Checkbox.displayName = 'Checkbox'

export { Checkbox }
