'use client'

import { Children, cloneElement, isValidElement, ReactElement, ReactNode, useState } from 'react'
import { useTranslations } from 'next-intl'
import { Sparkles } from 'lucide-react'
import { cn } from '@/utils/cn'

interface AutofilledFieldHighlightProps {
  /**
   * Whether the wrapped field was auto-filled from an extraction. Flip to
   * `false` via the `onUserEdit` callback as soon as the user edits the
   * underlying input so the highlight clears.
   */
  active: boolean
  children: ReactNode
  /** Optional label for the badge; defaults to the translated "auto-filled". */
  label?: string
  className?: string
}

/**
 * Wraps a form field and gives it a soft amber background + an "auto-filled"
 * badge while `active` is true. Once the user edits the field (or the parent
 * passes `active={false}`) the highlight disappears so the UI stops claiming
 * ownership of a value the user has touched.
 *
 * The component does NOT intercept input events — callers decide when the
 * value has changed. This keeps the wrapper agnostic to the input shape
 * (select / input / custom component).
 */
export function AutofilledFieldHighlight({
  active,
  children,
  label,
  className,
}: AutofilledFieldHighlightProps) {
  const t = useTranslations('settings.customizeAi.ingestion')
  if (!active) return <>{children}</>

  return (
    <div className={cn('relative', className)}>
      <div
        className={cn(
          'rounded-md ring-2 ring-amber-300/70 bg-amber-50/60 dark:bg-amber-950/20 dark:ring-amber-700/50',
          'p-0.5 transition-colors',
        )}
      >
        {children}
      </div>
      <span
        className={cn(
          'absolute -top-2 right-2 inline-flex items-center gap-1 rounded-full px-1.5 py-0.5',
          'text-[10px] font-medium bg-amber-200 text-amber-900 dark:bg-amber-900/60 dark:text-amber-100',
        )}
      >
        <Sparkles className="h-2.5 w-2.5" />
        {label ?? t('badge.autofilled')}
      </span>
    </div>
  )
}

interface AutofillStoryProps {
  /** Keys that were filled by the extractor in this round. */
  filledKeys: Set<string>
  /** Notify parent when the user has edited a particular key. */
  onUserEdit?: (key: string) => void
  children: ReactNode
}

/**
 * Convenience container: pass React children with a `data-field` attribute
 * and `filledKeys` will automatically wrap the matching ones with
 * <AutofilledFieldHighlight active />. Not required — callers can wrap
 * individual fields directly. Useful when many fields share the same
 * extractor result.
 */
function AutofillStory({ filledKeys, children }: AutofillStoryProps) {
  const [cleared] = useState<Set<string>>(new Set())
  return (
    <>
      {Children.map(children, (child) => {
        if (!isValidElement(child)) return child
        const props = (child.props ?? {}) as Record<string, unknown>
        const key = (props['data-field'] as string | undefined) ?? undefined
        if (!key) return child
        const active = filledKeys.has(key) && !cleared.has(key)
        return (
          <AutofilledFieldHighlight active={active}>
            {cloneElement(child as ReactElement)}
          </AutofilledFieldHighlight>
        )
      })}
    </>
  )
}
