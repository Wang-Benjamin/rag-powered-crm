'use client'

import React from 'react'
import { useTranslations } from 'next-intl'
import { useParams } from 'next/navigation'
import { AlertTriangle, X } from 'lucide-react'
import { Link } from '@/i18n/navigation'
import { useEmailSync } from '@/contexts/EmailSyncProvider'

const SYNC_ERRORS_ENABLED = process.env.NEXT_PUBLIC_SYNC_ERROR_TOASTS !== 'false'

/**
 * SyncErrorBanner — shown at the top of the dashboard when a CRM sync
 * authentication error is detected. Persists across page reloads (localStorage).
 * Dismissed by user click or cleared automatically on next successful sync /
 * auth token change.
 */
export function SyncErrorBanner() {
  const { syncError, clearSyncError } = useEmailSync()
  const t = useTranslations('email.syncError')
  // The profiles page is workspace-scoped; SidebarMenu prepends /workspace/{id}
  // automatically, but next-intl's <Link> does not — so we build the full path here.
  const params = useParams<{ workspaceId?: string }>()
  const reconnectHref = params?.workspaceId
    ? `/workspace/${params.workspaceId}/profiles?tab=preferences`
    : '/profiles?tab=preferences'

  if (!SYNC_ERRORS_ENABLED || !syncError) return null

  return (
    <div className="flex items-center justify-between border-b border-gold/30 bg-gold-lo px-4 py-2">
      <div className="flex items-center gap-2 text-sm font-medium text-[color:color-mix(in_oklab,var(--gold),var(--deep)_35%)]">
        <AlertTriangle className="h-4 w-4 shrink-0" />
        <span>{t('message')}</span>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Link
          href={reconnectHref}
          className="rounded-md bg-gold px-3 py-1 text-xs font-semibold text-deep transition-colors hover:bg-[color:color-mix(in_oklab,var(--gold),var(--deep)_15%)] hover:text-bone"
        >
          {t('reconnect')}
        </Link>
        <button
          type="button"
          onClick={clearSyncError}
          aria-label={t('dismiss')}
          className="rounded p-0.5 text-[color:color-mix(in_oklab,var(--gold),var(--deep)_35%)] transition-colors hover:bg-gold/15"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
