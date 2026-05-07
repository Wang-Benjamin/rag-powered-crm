/**
 * Domain-to-semantic badge variant mappings
 * Maps business domain values to semantic badge variants
 */

export type BadgeVariant = 'success' | 'danger' | 'warning' | 'info' | 'progress' | 'neutral'

// Customer Status
const customerStatusVariant: Record<string, BadgeVariant> = {
  active: 'success',
  inactive: 'danger',
  churned: 'danger',
  'at-risk': 'warning',
  'renewal-pending': 'neutral',
  completed: 'neutral',
  prospect: 'neutral',
} as const

// Deal Room Status
export const dealStageVariant: Record<string, BadgeVariant> = {
  draft: 'neutral',
  sent: 'info',
  viewed: 'progress',
  quote_requested: 'warning',
  'closed-won': 'success',
  'closed-lost': 'danger',
} as const

// Deal Status
const dealStatusVariant: Record<string, BadgeVariant> = {
  Active: 'success',
  'On Hold': 'warning',
  Cancelled: 'danger',
  Completed: 'neutral',
  // Lowercase variants for consistency
  active: 'success',
  'on hold': 'warning',
  cancelled: 'danger',
  completed: 'neutral',
} as const

// Lead Status
export const leadStatusVariant: Record<string, BadgeVariant> = {
  new: 'info',
  synced_to_crm: 'progress',
  qualified: 'success',
  not_interested: 'danger',
  // Alternative formats
  'synced to crm': 'progress',
  'not interested': 'danger',
} as const

// Customer Stage (sales pipeline)
export const customerStageVariant: Record<string, BadgeVariant> = {
  new: 'neutral',
  contacted: 'info',
  replied: 'progress',
  engaged: 'warning',
  quoting: 'success',
} as const

/**
 * Generic helper to get variant with fallback
 */
export function getVariant(
  mapping: Record<string, BadgeVariant>,
  value: string | undefined | null,
  fallback: BadgeVariant = 'neutral'
): BadgeVariant {
  if (!value) return fallback
  const normalized = value.toLowerCase()
  return mapping[normalized] ?? mapping[value] ?? fallback
}

/**
 * Format status text for display
 * Capitalizes first letter, replaces hyphens/underscores with spaces
 */
export function formatStatusLabel(status: string | undefined | null): string {
  if (!status) return 'Unknown'
  return status.replace(/[-_]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}
