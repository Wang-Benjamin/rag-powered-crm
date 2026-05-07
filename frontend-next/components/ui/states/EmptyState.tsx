import React from 'react'
import { LucideIcon } from 'lucide-react'

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description: string
  action?: React.ReactNode
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon: Icon,
  title,
  description,
  action,
}) => (
  <div className="py-12 text-center">
    <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-cream">
      <Icon className="h-8 w-8 text-mute" />
    </div>
    <h3 className="mb-2 title-block">{title}</h3>
    <p className="mx-auto mb-6 max-w-md text-sm text-mute">{description}</p>
    {action && <div className="flex items-center justify-center gap-3">{action}</div>}
  </div>
)
