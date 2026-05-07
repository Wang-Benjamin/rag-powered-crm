'use client'

import React from 'react'
import { useTranslations } from 'next-intl'
import { AlertTriangle } from 'lucide-react'

interface TrialExpiredBannerProps {
  show: boolean
}

export function TrialExpiredBanner({ show }: TrialExpiredBannerProps) {
  const t = useTranslations('common.trial')

  if (!show) return null

  return (
    <div className="flex items-center justify-between border-b border-rule bg-paper px-4 py-2">
      <div className="flex items-center gap-2 text-sm font-medium text-deep">
        <AlertTriangle className="h-4 w-4 shrink-0 text-threat" />
        <span>{t('expiredBanner')}</span>
      </div>
      <a
        href="mailto:sales@prelude.so?subject=Upgrade%20Plan"
        className="shrink-0 rounded-md bg-deep px-4 py-1.5 text-xs font-bold text-bone transition-colors hover:opacity-90"
      >
        {t('upgradeCta')}
      </a>
    </div>
  )
}
