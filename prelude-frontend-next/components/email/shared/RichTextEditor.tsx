'use client'

import React, {
  useEffect,
  useCallback,
  forwardRef,
  useImperativeHandle,
  useRef,
} from 'react'
import { useTranslations } from 'next-intl'
import { Bold, Italic, Underline } from 'lucide-react'
import { Toggle } from '@/components/ui/toggle'

export interface RichTextEditorProps {
  value: string
  onChange: (html: string) => void
  onFocus?: () => void
  onBlur?: () => void
  /**
   * IME composition events. When provided, parent can guard expensive work
   * (e.g. translation invalidation) until composition ends. The editor itself
   * already suppresses internal onChange while composing — these props are for
   * downstream consumers that need to track composition state.
   */
  onCompositionStart?: () => void
  onCompositionEnd?: () => void
  placeholder?: string
  minHeight?: string
  /**
   * Hide the built-in B/I/U toolbar. Use when an external toolbar drives the
   * editor (e.g. the compose-shell `.rt-toolbar`). External toolbars should
   * focus the editor first, then call `document.execCommand('bold' | …)`.
   */
  hideToolbar?: boolean
  /**
   * Override the outer wrapper className. The default applies a rounded border
   * + focus ring; pass an empty string to opt out (e.g. inside `.compose`).
   */
  wrapperClassName?: string
  /** Optional className on the contenteditable surface itself. */
  editorClassName?: string
}

const DEFAULT_WRAPPER =
  'overflow-hidden rounded-lg border border-zinc-200 focus-within:ring-2 focus-within:ring-ring dark:border-zinc-700'
const DEFAULT_EDITOR =
  'overflow-auto px-4 pt-2 pb-4 text-sm outline-none empty:before:text-muted-foreground empty:before:content-[attr(data-placeholder)]'

const RichTextEditor = forwardRef<HTMLDivElement, RichTextEditorProps>(
  (
    {
      value,
      onChange,
      onFocus,
      onBlur,
      onCompositionStart,
      onCompositionEnd,
      placeholder,
      minHeight = '300px',
      hideToolbar = false,
      wrapperClassName,
      editorClassName,
    },
    ref
  ) => {
    const t = useTranslations('email')
    const resolvedPlaceholder = placeholder ?? t('richTextEditor.bodyPlaceholder')
    const internalRef = useRef<HTMLDivElement>(null)
    // IME composition guard: skip onChange while user is mid-composition (e.g.
    // pinyin candidate selection). Otherwise React rerenders mid-IME and
    // corrupts the input. Fire a single onChange when composition ends.
    const isComposingRef = useRef(false)

    useImperativeHandle(ref, () => internalRef.current as HTMLDivElement)

    useEffect(() => {
      // Don't overwrite innerHTML if the user is mid-composition or focused —
      // would clobber selection + IME candidates.
      if (
        internalRef.current &&
        document.activeElement !== internalRef.current &&
        !isComposingRef.current
      ) {
        internalRef.current.innerHTML = (value || '').replace(/\n/g, '<br>')
      }
    }, [value])

    const executeCommand = useCallback(
      (command: string) => {
        document.execCommand(command, false)
        internalRef.current?.focus()
        onChange(internalRef.current?.innerHTML || '')
      },
      [onChange]
    )

    const handleBold = useCallback(() => executeCommand('bold'), [executeCommand])
    const handleItalic = useCallback(() => executeCommand('italic'), [executeCommand])
    const handleUnderline = useCallback(() => executeCommand('underline'), [executeCommand])

    const isCommandActive = (command: string): boolean => {
      try {
        return document.queryCommandState(command)
      } catch {
        return false
      }
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey) {
        const handlers: Record<string, () => void> = {
          b: handleBold,
          i: handleItalic,
          u: handleUnderline,
        }
        if (handlers[e.key]) {
          e.preventDefault()
          handlers[e.key]()
        }
      }
    }

    const handleInput = (e: React.FormEvent<HTMLDivElement>) => {
      if (isComposingRef.current) return
      onChange(e.currentTarget.innerHTML || '')
    }

    const handleCompositionStart = () => {
      isComposingRef.current = true
      onCompositionStart?.()
    }

    const handleCompositionEnd = (e: React.CompositionEvent<HTMLDivElement>) => {
      isComposingRef.current = false
      onChange(e.currentTarget.innerHTML || '')
      onCompositionEnd?.()
    }

    return (
      <div className={wrapperClassName ?? DEFAULT_WRAPPER}>
        {!hideToolbar && (
          <div className="flex items-center gap-1 px-3 pt-3 pb-1">
            <Toggle
              pressed={isCommandActive('bold')}
              onPressedChange={handleBold}
              size="sm"
              aria-label={t('richTextEditor.bold')}
            >
              <Bold className="h-4 w-4" />
            </Toggle>
            <Toggle
              pressed={isCommandActive('italic')}
              onPressedChange={handleItalic}
              size="sm"
              aria-label={t('richTextEditor.italic')}
            >
              <Italic className="h-4 w-4" />
            </Toggle>
            <Toggle
              pressed={isCommandActive('underline')}
              onPressedChange={handleUnderline}
              size="sm"
              aria-label={t('richTextEditor.underline')}
            >
              <Underline className="h-4 w-4" />
            </Toggle>
          </div>
        )}

        <div
          ref={internalRef}
          contentEditable
          onInput={handleInput}
          onKeyDown={handleKeyDown}
          onBlur={onBlur}
          onFocus={onFocus}
          onCompositionStart={handleCompositionStart}
          onCompositionEnd={handleCompositionEnd}
          suppressContentEditableWarning
          className={editorClassName ?? DEFAULT_EDITOR}
          style={{ minHeight }}
          data-placeholder={resolvedPlaceholder}
        />
      </div>
    )
  }
)

RichTextEditor.displayName = 'RichTextEditor'

export default RichTextEditor
