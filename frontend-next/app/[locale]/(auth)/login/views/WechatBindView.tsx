'use client'

import React from 'react'
import { useTranslations } from 'next-intl'
import {
  inputCls,
  fldLabelCls,
  primaryCtaCls,
  smallSpinnerOnDeepCls,
  BackToMain,
  ErrorBanner,
  PasswordToggle,
} from '../loginPrimitives'

type Props = {
  username: string
  password: string
  showPassword: boolean
  wechatNickname: string | null
  bindMode: 'existing' | 'new'
  loadingProvider: string | null
  error: string | null | undefined
  onUsernameChange: (v: string) => void
  onPasswordChange: (v: string) => void
  onTogglePassword: () => void
  onBindModeChange: (m: 'existing' | 'new') => void
  onBind: (e: React.FormEvent) => void
  onRegister: (e: React.FormEvent) => void
  onBack: () => void
}

export default function WechatBindView({
  username,
  password,
  showPassword,
  wechatNickname,
  bindMode,
  loadingProvider,
  error,
  onUsernameChange,
  onPasswordChange,
  onTogglePassword,
  onBindModeChange,
  onBind,
  onRegister,
  onBack,
}: Props) {
  const t = useTranslations('auth.login')

  const isLink = bindMode === 'existing'
  const submitLabel = isLink ? t('wechatBindExisting') : t('wechatCreateNew')
  const usernameLabel = isLink ? t('username') : t('wechatCreateUsernameLabel')
  const passwordLabel = isLink ? t('password') : t('wechatCreatePasswordLabel')
  const usernamePlaceholder = isLink ? t('usernamePlaceholder') : t('wechatCreateUsernamePlaceholder')
  const passwordPlaceholder = isLink ? t('passwordPlaceholder') : t('wechatCreatePasswordPlaceholder')
  const autocompletePassword = isLink ? 'current-password' : 'new-password'
  const bindNicknameInitial = wechatNickname?.trim().charAt(0) || ''

  const toggleBtn = (active: boolean) =>
    `h-10 px-3 border-0 font-body text-[13.5px] font-medium rounded-[7px] cursor-pointer inline-flex items-center justify-center gap-1.5 transition-all duration-200 focus-visible:outline-none focus-visible:shadow-[0_0_0_3px_var(--accent-lo)] ${
      active
        ? 'bg-deep text-bone shadow-[0_4px_10px_-6px_oklch(0.25_0.02_260/0.35)]'
        : 'bg-transparent text-mute hover:text-ink'
    }`

  return (
    <>
      <BackToMain onBack={onBack} />

      <div className="text-center mb-6">
        <div
          className="relative inline-grid place-items-center w-14 h-14 rounded-2xl bg-deep text-bone font-display text-2xl mb-3.5 overflow-hidden shadow-[0_14px_32px_-18px_oklch(0.25_0.02_260/0.35)]"
          aria-hidden="true"
        >
          <span
            className="absolute inset-0 opacity-70 pointer-events-none"
            style={{
              background:
                'radial-gradient(ellipse at 80% 120%, color-mix(in oklab, var(--accent) 55%, transparent) 0%, transparent 65%)',
            }}
          />
          <span className="relative z-[1]">{bindNicknameInitial || 'P'}</span>
          <span className="absolute -right-1 -bottom-1 w-[22px] h-[22px] rounded-full border-2 border-paper grid place-items-center z-[1]" style={{ background: '#09b83e' }}>
            <svg className="w-3 h-3 text-white" viewBox="0 0 48 48" fill="currentColor" aria-hidden="true">
              <path d="M18.5 6C9.4 6 2 12.4 2 20.3c0 4.4 2.4 8.3 6.2 10.9L6.6 36l5.6-2.8c1.9.5 3.9.8 5.9.8.5 0 1 0 1.5-.1-.3-1-.5-2.1-.5-3.2 0-7.3 7-13.1 15.6-13.1h.8C34 11.6 27 6 18.5 6z" />
            </svg>
          </span>
        </div>
        <h1 className="display display-s mb-1.5">
          {t('wechatWelcome')}
          {wechatNickname ? (
            <>
              , <em>{wechatNickname}</em>
            </>
          ) : null}
        </h1>
        <p className="text-[13.5px] text-mute m-0">{t('wechatNeedsBind')}</p>
      </div>

      <div
        className="grid grid-cols-2 gap-0.5 p-0.5 bg-cream border border-rule rounded-[10px] mb-5"
        role="tablist"
        aria-label="Account mode"
      >
        <button
          type="button"
          onClick={() => onBindModeChange('existing')}
          role="tab"
          aria-selected={isLink}
          className={toggleBtn(isLink)}
        >
          <svg className={`w-[13px] h-[13px] ${isLink ? 'opacity-100' : 'opacity-70'}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
          </svg>
          {t('wechatBindExisting')}
        </button>
        <button
          type="button"
          onClick={() => onBindModeChange('new')}
          role="tab"
          aria-selected={!isLink}
          className={toggleBtn(!isLink)}
        >
          <svg className={`w-[13px] h-[13px] ${!isLink ? 'opacity-100' : 'opacity-70'}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          {t('wechatCreateNew')}
        </button>
      </div>

      <ErrorBanner message={error} />

      <form
        onSubmit={isLink ? onBind : onRegister}
        noValidate
        className="flex flex-col gap-4 mt-1"
      >
        <div className="flex flex-col gap-2">
          <label htmlFor="bind-username" className={fldLabelCls}>{usernameLabel}</label>
          <input
            id="bind-username"
            className={inputCls}
            type="text"
            value={username}
            onChange={(e) => onUsernameChange(e.target.value)}
            required
            placeholder={usernamePlaceholder}
            autoComplete="username"
          />
          {!isLink && (
            <div className="text-[11.5px] text-mute -mt-0.5">{t('wechatCreateUsernameHint')}</div>
          )}
        </div>

        <div className="flex flex-col gap-2">
          <label htmlFor="bind-password" className={fldLabelCls}>{passwordLabel}</label>
          <div className="relative">
            <input
              id="bind-password"
              className={`${inputCls} pr-[46px]`}
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => onPasswordChange(e.target.value)}
              required
              placeholder={passwordPlaceholder}
              autoComplete={autocompletePassword}
            />
            <PasswordToggle show={showPassword} onToggle={onTogglePassword} />
          </div>
        </div>

        <button
          type="submit"
          className={`${primaryCtaCls} group mt-2`}
          disabled={!!loadingProvider}
          aria-busy={!!loadingProvider}
        >
          {loadingProvider ? (
            <>
              <span className={smallSpinnerOnDeepCls} />
              <span>{t('signingIn')}</span>
            </>
          ) : (
            <>
              <span>{submitLabel}</span>
              <span aria-hidden="true" className="inline-block transition-transform duration-200 group-hover:translate-x-0.5">→</span>
            </>
          )}
        </button>
      </form>
    </>
  )
}
