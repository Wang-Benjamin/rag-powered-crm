'use client'

import * as React from 'react'
import { AlertTriangle, Trash2, Info, X } from 'lucide-react'
import { Button } from './button'
import { cn } from '@/utils/cn'

export interface ConfirmationToastProps {
  isOpen: boolean
  onConfirm: () => void
  onCancel: () => void
  title: string
  description?: string
  confirmLabel?: string
  cancelLabel?: string
  variant?: 'default' | 'destructive' | 'warning'
  isLoading?: boolean
  itemName?: string
  itemCount?: number
}

const variantConfig = {
  default: {
    icon: Info,
    iconBg: 'bg-zinc-100 dark:bg-zinc-800',
    iconColor: 'text-zinc-600 dark:text-zinc-400',
    confirmClass: '',
  },
  destructive: {
    icon: Trash2,
    iconBg: 'bg-red-100 dark:bg-red-900/30',
    iconColor: 'text-red-600 dark:text-red-400',
    confirmClass: 'bg-red-600 hover:bg-red-700 text-white',
  },
  warning: {
    icon: AlertTriangle,
    iconBg: 'bg-amber-100 dark:bg-amber-900/30',
    iconColor: 'text-amber-600 dark:text-amber-400',
    confirmClass: '',
  },
}

export function ConfirmationToast({
  isOpen,
  onConfirm,
  onCancel,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'default',
  isLoading = false,
  itemName,
  itemCount,
}: ConfirmationToastProps) {
  if (!isOpen) return null

  const config = variantConfig[variant]
  const Icon = config.icon

  // Build title with item info
  let displayTitle = title
  if (itemName && !title.includes(itemName)) {
    displayTitle = `${title} "${itemName}"?`
  }
  if (itemCount && itemCount > 1) {
    displayTitle = title.replace(/\?$/, '') + ` (${itemCount} items)?`
  }

  return (
    <div className={cn('fixed right-6 bottom-6 z-50', 'animate-slide-up')}>
      <div
        className={cn(
          'w-[360px] rounded-lg border shadow-lg',
          'bg-white dark:bg-zinc-900',
          'border-zinc-200 dark:border-zinc-700'
        )}
      >
        <div className="p-4">
          <div className="flex items-start gap-3">
            <div
              className={cn(
                'flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full',
                config.iconBg
              )}
            >
              <Icon className={cn('h-5 w-5', config.iconColor)} />
            </div>
            <div className="min-w-0 flex-1">
              <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                {displayTitle}
              </h4>
              {description && (
                <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{description}</p>
              )}
            </div>
            <button
              onClick={onCancel}
              className="flex-shrink-0 rounded p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="mt-4 flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={onCancel} disabled={isLoading}>
              {cancelLabel}
            </Button>
            <Button
              size="sm"
              onClick={onConfirm}
              disabled={isLoading}
              loading={isLoading}
              loadingText="..."
              className={config.confirmClass}
            >
              {confirmLabel}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

