'use client'

import React from 'react'
import { useTranslations } from 'next-intl'

export interface RecipientItem {
  /** Stable key — leadId for buyers, clientId for CRM customers/deals. */
  id: string | number
  /** Display name (company / contact). */
  name: string
  /** Email address. May be empty if unresolved. */
  email: string
  /** Optional error state (e.g. bounced, missing email). */
  error?: string
}

export interface RecipientListProps {
  items: RecipientItem[]
  activeIndex: number
  onSelect: (index: number) => void
  /** Indices that are approved-to-send. */
  approved: Set<number>
  /** Indices that have been edited since AI generation. */
  modified?: Set<number>
  /** Toggle approval for a single recipient. When provided, the status icon
   * becomes a clickable button that flips between approved / pending. */
  onToggleApprove?: (index: number) => void
}

/**
 * Vertical list of recipient chips (mass mode). Default shows ~5 visible
 * without scroll (max-height: 280px ≈ 5 × 56px). Scrolls if the upstream
 * supplies 6-10 recipients (business cap is 10).
 *
 * Each row surfaces approval (✓ / ◯ / ⚠) and modified-since-generate (●)
 * state so reviewers do not have to scroll the right pane to audit the
 * batch.
 */
const RecipientList: React.FC<RecipientListProps> = ({
  items,
  activeIndex,
  onSelect,
  approved,
  modified,
  onToggleApprove,
}) => {
  const t = useTranslations('email')

  // Recipients without an email cannot receive a send. Surface counts against
  // sendable rows only, so the header doesn't read e.g. "10 / 10" when 3 of
  // those 10 are unsendable.
  const sendableTotal = items.reduce((n, item) => (item.error ? n : n + 1), 0)
  const approvedSendable = items.reduce(
    (n, item, idx) => (!item.error && approved.has(idx) ? n + 1 : n),
    0
  )

  return (
    <div>
      <div className="recip-list-hd">
        <span>{t('composer.recipients.title')}</span>
        <span>
          {approvedSendable} / {sendableTotal}
        </span>
      </div>

      <div className="recip-list" role="listbox" aria-label={t('composer.recipients.title')}>
        {items.map((item, idx) => {
          const isActive = idx === activeIndex
          const isApproved = approved.has(idx)
          const isModified = modified?.has(idx) ?? false
          const hasError = !!item.error

          let statusGlyph = '◯'
          let statusClass = ''
          if (hasError) {
            statusGlyph = '⚠'
            statusClass = 'error'
          } else if (isApproved) {
            statusGlyph = '✓'
            statusClass = 'approved'
          }

          const StatusEl = onToggleApprove ? 'span' : 'span'
          return (
            <div
              key={item.id}
              role="option"
              aria-selected={isActive}
              className={`recip-row${isActive ? ' active' : ''}`}
              title={hasError ? item.error : item.email}
              onClick={() => onSelect(idx)}
            >
              {onToggleApprove ? (
                <button
                  type="button"
                  className={`recip-status ${statusClass} clickable`}
                  onClick={(e) => {
                    e.stopPropagation()
                    if (!hasError) onToggleApprove(idx)
                  }}
                  disabled={hasError}
                  aria-label={
                    isApproved ? t('composer.unapprove') : t('composer.approve')
                  }
                  title={isApproved ? t('composer.unapprove') : t('composer.approve')}
                >
                  {statusGlyph}
                </button>
              ) : (
                <StatusEl className={`recip-status ${statusClass}`}>{statusGlyph}</StatusEl>
              )}
              <span className="recip-id">
                <span className="name">{item.name || t('composer.recipients.unknown')}</span>
                <span className="email">{item.email || t('composer.recipients.noEmail')}</span>
              </span>
              <span className={`recip-modified${isModified ? '' : ' hidden'}`} aria-hidden />
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default RecipientList
