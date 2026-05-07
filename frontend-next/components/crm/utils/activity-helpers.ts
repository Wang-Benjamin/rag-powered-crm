/**
 * Shared helpers for CRM activity/timeline components.
 *
 * Extracted from ActivityPanel, InteractionDetailsModal, NoteDetailsModal,
 * CustomerDetailModal, and DealActivityPanel to eliminate duplication.
 */

import {
  Mail,
  PhoneCall,
  Calendar,
  FileText,
  Activity,
  type LucideIcon,
} from 'lucide-react'

/** Minimal translation function signature compatible with next-intl Translator. */
type TranslateFunc = (key: any, ...args: any[]) => string

// ---------------------------------------------------------------------------
// Note star helpers
// ---------------------------------------------------------------------------

/** Whether the star value represents a starred note. */
export function isNoteStarred(star?: string): boolean {
  return star === 'important' || star === 'urgent' || star === 'starred'
}

/**
 * Map a star value to a user-facing label.
 * Accepts a `t` function scoped to the `crm` namespace.
 */
export function getStarDisplayText(
  star: string | undefined,
  t: TranslateFunc
): string {
  switch (star) {
    case 'important':
      return t('activityPanel.starImportant')
    case 'urgent':
      return t('activityPanel.starUrgent')
    case 'starred':
      return t('activityPanel.starStarred')
    default:
      return ''
  }
}

// ---------------------------------------------------------------------------
// Email direction badge
// ---------------------------------------------------------------------------

export interface DirectionBadge {
  label: string
  variant: 'secondary' | 'neutral'
}

/**
 * Return badge props for an email direction string, or `null` if unknown.
 * Accepts a `t` function scoped to the `crm` namespace.
 */
export function getEmailDirectionBadge(
  direction: string | undefined,
  t: TranslateFunc
): DirectionBadge | null {
  if (!direction) return null

  const lower = direction.toLowerCase()
  if (lower === 'sent') {
    return { label: t('interactionDetail.sent'), variant: 'secondary' }
  }
  if (lower === 'received') {
    return { label: t('interactionDetail.received'), variant: 'neutral' }
  }
  return null
}

// ---------------------------------------------------------------------------
// Timeline type config (icon + zinc-only colours)
// ---------------------------------------------------------------------------

export interface TypeConfig {
  icon: LucideIcon
  bgColor: string
  textColor: string
  borderColor: string
}

const TYPE_CONFIGS: Record<string, TypeConfig> = {
  email: { icon: Mail, bgColor: 'bg-zinc-100', textColor: 'text-zinc-900', borderColor: 'border-zinc-200' },
  call: { icon: PhoneCall, bgColor: 'bg-zinc-100', textColor: 'text-zinc-900', borderColor: 'border-zinc-200' },
  meeting: { icon: Calendar, bgColor: 'bg-zinc-100', textColor: 'text-zinc-900', borderColor: 'border-zinc-200' },
  note: { icon: FileText, bgColor: 'bg-zinc-100', textColor: 'text-zinc-900', borderColor: 'border-zinc-200' },
}

const DEFAULT_TYPE_CONFIG: TypeConfig = {
  icon: Activity,
  bgColor: 'bg-zinc-100',
  textColor: 'text-zinc-900',
  borderColor: 'border-zinc-200',
}

/** Look up icon + colour config for an activity type string. */
export function getTypeConfig(type: string): TypeConfig {
  return TYPE_CONFIGS[type] || DEFAULT_TYPE_CONFIG
}

// ---------------------------------------------------------------------------
// HTML stripping (for email body previews)
// ---------------------------------------------------------------------------

/** Strip HTML tags from a string, removing signature blocks first. */
export function stripHtml(text: string): string {
  return text
    .replace(/<div\s+style="margin-top:\s*20px[^"]*"[^>]*>[\s\S]*$/gi, '') // strip signature block
    .replace(/<(style|script)[^>]*>.*?<\/\1>/gis, '')
    .replace(/<br\s*\/?>/gi, ' ')
    .replace(/<\/p>/gi, ' ')
    .replace(/<\/div>/gi, ' ')
    .replace(/<[^>]+>/g, '')
    .replace(/\s{2,}/g, ' ')
    .trim()
}
