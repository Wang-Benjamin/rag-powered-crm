import { cn } from '@/utils/cn'

export type SkeletonVariant = 'tall' | 'mono' | 'num' | 'chip' | 'avatar'

const variantStyle: Record<SkeletonVariant, React.CSSProperties> = {
  tall: { height: 18 },
  mono: { height: 12, borderRadius: 3 },
  num: { height: 14, width: 56, marginLeft: 'auto' },
  chip: { height: 22, width: 68, borderRadius: 999 },
  avatar: { height: 32, width: 32, borderRadius: '50%' },
}

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: SkeletonVariant
  width?: string | number
}

function Skeleton({ className, variant, width, style, ...props }: SkeletonProps) {
  const baseStyle = variant ? variantStyle[variant] : undefined
  const widthStyle =
    width != null
      ? { width: typeof width === 'number' ? `${width}px` : width }
      : undefined
  return (
    <div
      className={cn('skel', className)}
      style={{ ...baseStyle, ...widthStyle, ...style }}
      {...props}
    />
  )
}

export { Skeleton }
