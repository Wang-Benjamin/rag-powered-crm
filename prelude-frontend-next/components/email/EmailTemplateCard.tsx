'use client'

import { useTranslations } from 'next-intl'
import { Mail, TrendingUp, Users, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { TemplateTypeBadge } from './TemplateTypeBadge'
import type { EmailTemplate } from '@/types/email'
import { cn } from '@/utils/cn'

interface EmailTemplateCardProps {
  template: EmailTemplate
  isSelected: boolean
  onSelect: () => void
  onDelete?: () => void
  parentName?: string
}

function stripHtml(html: string): string {
  return html
    .replace(/<[^>]*>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

export function EmailTemplateCard({
  template,
  isSelected,
  onSelect,
  onDelete,
  parentName,
}: EmailTemplateCardProps) {
  const t = useTranslations('email')
  const isVariation = template.level === 1
  const sends = template.sendCount || 0
  const bodyPreview = template.body ? stripHtml(template.body).slice(0, 72) : template.subject

  return (
    <div
      onClick={onSelect}
      className={cn(
        'group relative cursor-pointer rounded-lg border transition-all duration-150',
        'py-3 pr-3 pl-3.5',
        isSelected
          ? 'border-zinc-300 bg-zinc-50 shadow-sm ring-1 ring-zinc-200 dark:border-zinc-600 dark:bg-zinc-800/80 dark:ring-zinc-700'
          : 'border-transparent hover:border-zinc-200 hover:bg-zinc-50/70 dark:hover:border-zinc-700 dark:hover:bg-zinc-800/40'
      )}
    >
      {/* Selected indicator — left accent */}
      <div
        className={cn(
          'absolute top-3 bottom-3 left-0 w-[3px] rounded-full transition-all duration-200',
          isSelected
            ? 'bg-zinc-900 dark:bg-zinc-100'
            : 'bg-transparent group-hover:bg-zinc-300 dark:group-hover:bg-zinc-600'
        )}
      />

      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          {/* Row 1: Name + badges */}
          <div className="mb-0.5 flex items-center gap-1.5">
            <h4
              className={cn(
                'truncate text-[13px] font-semibold transition-colors',
                isSelected ? 'text-zinc-900 dark:text-zinc-50' : 'text-zinc-800 dark:text-zinc-200'
              )}
            >
              {template.name}
            </h4>

            {isVariation && <TemplateTypeBadge level={template.level} />}

            {template.isShared && (
              <Users className="h-3 w-3 flex-shrink-0 text-zinc-400 dark:text-zinc-500" />
            )}
          </div>

          {/* Row 2: Variation parent */}
          {isVariation && parentName && (
            <p className="mb-1 truncate text-[11px] text-zinc-400 dark:text-zinc-500">
              &larr; {parentName}
            </p>
          )}

          {/* Row 3: Body preview */}
          <p className="mb-2 line-clamp-2 text-[11px] leading-relaxed text-zinc-500 dark:text-zinc-400">
            {bodyPreview}
          </p>

          {/* Row 4: Stats */}
          <div className="flex items-center gap-2">
            <span
              className={cn(
                'inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium',
                sends >= 5
                  ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400'
                  : sends > 0
                    ? 'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400'
                    : 'bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-500'
              )}
            >
              <Mail className="h-2.5 w-2.5" />
              {t('templates.sends', { count: sends })}
            </span>
            {sends > 0 && (
              <span className="inline-flex items-center gap-1 rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
                <TrendingUp className="h-2.5 w-2.5" />
                100%
              </span>
            )}
          </div>
        </div>

        {/* Delete button */}
        {onDelete && (
          <Button
            variant="ghost"
            size="sm"
            onClick={(e) => {
              e.stopPropagation()
              onDelete()
            }}
            className="mt-0.5 h-7 w-7 flex-shrink-0 p-0 text-zinc-400 opacity-0 transition-opacity group-hover:opacity-100 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/30"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        )}
      </div>
    </div>
  )
}

