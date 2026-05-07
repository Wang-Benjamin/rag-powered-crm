import { cn } from '@/utils/cn'

interface PageLoaderProps {
  label?: string
  brand?: boolean
  className?: string
  showLabel?: boolean
}

export function PageLoader({ label, brand = false, className, showLabel }: PageLoaderProps) {
  const shouldShowLabel = !!label && (showLabel ?? !brand)

  return (
    <div
      className={cn('page-loader', className)}
      role="status"
      aria-live="polite"
      aria-label={label && !shouldShowLabel ? label : undefined}
    >
      {brand && (
        <div className="brand">
          <span className="wordmark">Prelude</span>
          <span className="zh">璞序</span>
        </div>
      )}
      <div className="bar" />
      {shouldShowLabel && <span className="status">{label}</span>}
    </div>
  )
}
