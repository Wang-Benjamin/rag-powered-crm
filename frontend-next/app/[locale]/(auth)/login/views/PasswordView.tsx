'use client'

import React from 'react'
import { useTranslations } from 'next-intl'
import {
  inputCls,
  fldLabelCls,
  primaryCtaCls,
  smallSpinnerOnDeepCls,
  H1Title,
  ErrorBanner,
  PasswordToggle,
} from '../loginPrimitives'

type Props = {
  username: string
  password: string
  showPassword: boolean
  loadingProvider: string | null
  error: string | null | undefined
  onUsernameChange: (v: string) => void
  onPasswordChange: (v: string) => void
  onTogglePassword: () => void
  onSubmit: (e: React.FormEvent) => void
  onBack: () => void
}

export default function PasswordView({
  username,
  password,
  showPassword,
  loadingProvider,
  error,
  onUsernameChange,
  onPasswordChange,
  onTogglePassword,
  onSubmit,
  onBack,
}: Props) {
  const t = useTranslations('auth.login')

  return (
    <>
      <div className="mb-6">
        <H1Title />
      </div>

      <ErrorBanner message={error} />

      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4 mt-2">
        <div className="flex flex-col gap-2">
          <label htmlFor="pw-username" className={fldLabelCls}>{t('username')}</label>
          <input
            id="pw-username"
            className={inputCls}
            type="text"
            value={username}
            onChange={(e) => onUsernameChange(e.target.value)}
            required
            disabled={loadingProvider === 'password'}
            placeholder={t('usernamePlaceholder')}
            autoComplete="username"
          />
        </div>

        <div className="flex flex-col gap-2">
          <label htmlFor="pw-password" className={fldLabelCls}>{t('password')}</label>
          <div className="relative">
            <input
              id="pw-password"
              className={`${inputCls} pr-[46px]`}
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => onPasswordChange(e.target.value)}
              required
              disabled={loadingProvider === 'password'}
              placeholder={t('passwordPlaceholder')}
              autoComplete="current-password"
            />
            <PasswordToggle show={showPassword} onToggle={onTogglePassword} />
          </div>
        </div>

        <button
          type="submit"
          className={`${primaryCtaCls} group mt-2`}
          disabled={loadingProvider === 'password'}
          aria-busy={loadingProvider === 'password'}
        >
          {loadingProvider === 'password' ? (
            <>
              <span className={smallSpinnerOnDeepCls} />
              <span>{t('signingIn')}</span>
            </>
          ) : (
            <>
              <span>{t('signIn')}</span>
              <span aria-hidden="true" className="inline-block transition-transform duration-200 group-hover:translate-x-0.5">→</span>
            </>
          )}
        </button>
      </form>
    </>
  )
}
