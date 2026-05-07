import * as React from 'react'
import { cn } from '@/utils/cn'

export interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  value?: number
}

const Progress = React.forwardRef<HTMLDivElement, ProgressProps>(
  ({ className, value = 0, ...props }, ref) => {
    // Ensure value is a valid number and log any issues
    const sanitizedValue = (() => {
      const numValue = Number(value)
      if (isNaN(numValue)) {
        console.warn('⚠️ Progress component received NaN value:', value, 'defaulting to 0')
        return 0
      }
      return Math.max(0, Math.min(100, numValue))
    })()

    return (
      <div
        ref={ref}
        className={cn('relative h-4 w-full overflow-hidden rounded-full bg-fog', className)}
        {...props}
      >
        <div
          className="h-full rounded-full bg-primary transition-all duration-300 ease-in-out"
          style={{ width: `${sanitizedValue}%` }}
        />
      </div>
    )
  }
)
Progress.displayName = 'Progress'

export { Progress }
