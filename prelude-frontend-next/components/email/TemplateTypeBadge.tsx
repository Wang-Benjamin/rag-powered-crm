'use client'

import { Badge } from '@/components/ui/badge'
import { cn } from '@/utils/cn'
import type { TemplateLevel } from '@/types/email'

interface TemplateTypeBadgeProps {
  level: TemplateLevel
  className?: string
}

export function TemplateTypeBadge({ level, className }: TemplateTypeBadgeProps) {
  // Only show badge for variations (level 1)
  // Base templates (level 0) don't need a badge
  if (level === 0) {
    return null
  }

  return (
    <Badge variant="secondary" className={cn('text-[10px] tracking-wide uppercase', className)}>
      Variation
    </Badge>
  )
}

