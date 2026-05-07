'use client'

import React from 'react'
import { useTranslations } from 'next-intl'
import { primaryCtaCls, H1Title } from '../loginPrimitives'

type Props = {
  onUsernameLogin: () => void
}

export default function MainView({ onUsernameLogin }: Props) {
  const t = useTranslations('auth.login')

  return (
    <>
      <div className="mb-10">
        <H1Title />
      </div>

      <button
        type="button"
        onClick={onUsernameLogin}
        aria-label={t('continueWithUsername')}
        className={`${primaryCtaCls} group`}
      >
        <span>{t('continueWithUsername')}</span>
        <span aria-hidden="true" className="inline-block transition-transform duration-200 group-hover:translate-x-0.5">→</span>
      </button>
    </>
  )
}
