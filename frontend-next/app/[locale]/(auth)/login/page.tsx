'use client'

import React, { useState, useEffect, useCallback, useRef } from 'react'
import { useRouter } from '@/i18n/navigation'
import { useTranslations } from 'next-intl'
import { syncLocaleFromBackend } from '@/lib/locale'
import { useAuth } from '@/hooks/useAuth'
import { toWorkspaceId } from '@/lib/auth/workspaceId'
import Showcase from './Showcase'
import MainView from './views/MainView'
import PasswordView from './views/PasswordView'
import WechatQrView from './views/WechatQrView'
import WechatBindView from './views/WechatBindView'

type LoginView = 'main' | 'password' | 'wechat' | 'wechat-bind'

export default function LoginPage() {
  const router = useRouter()
  const { loginWith, isAuthenticated, authError } = useAuth()
  const t = useTranslations('auth.login')

  const [loadingProvider, setLoadingProvider] = useState<string | null>(null)
  const [currentView, setCurrentView] = useState<LoginView>('password')
  const [username, setUsername] = useState('aoxue@preludeos.com')
  const [password, setPassword] = useState('271828abc@')
  const [loginError, setLoginError] = useState<string | null>(null)
  const [showPassword, setShowPassword] = useState(false)

  // WeChat state
  const [wechatQrUrl, setWechatQrUrl] = useState<string | null>(null)
  const [wechatSceneId, setWechatSceneId] = useState<string | null>(null)
  const [wechatNickname, setWechatNickname] = useState<string | null>(null)
  const [wechatLoading, setWechatLoading] = useState(false)
  const [wechatExpired, setWechatExpired] = useState(false)
  const [wechatScanned, setWechatScanned] = useState(false)
  const [bindMode, setBindMode] = useState<'existing' | 'new'>('existing')
  const pollRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    if (isAuthenticated) {
      const idToken = localStorage.getItem('id_token')
      if (idToken) {
        try {
          const payload = JSON.parse(atob(idToken.split('.')[1]))
          const userEmail = payload.email || payload.user_email
          const workspaceId = toWorkspaceId(userEmail)
          router.push(`/workspace/${workspaceId}/crm`)
        } catch (error) {
          console.error('Error parsing token:', error)
        }
      }
    }
  }, [isAuthenticated, router])

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  const goBackToMain = () => {
    setCurrentView('main')
    setLoginError(null)
    setShowPassword(false)
    setWechatScanned(false)
    if (pollRef.current) clearInterval(pollRef.current)
  }

  const handleGoogleLogin = async () => {
    setLoadingProvider('google')
    setLoginError(null)
    try {
      await loginWith('google')
    } catch (error) {
      setLoginError(error instanceof Error ? error.message : t('loginFailed'))
      setLoadingProvider(null)
    }
  }

  const handleMicrosoftLogin = async () => {
    setLoadingProvider('microsoft')
    setLoginError(null)
    try {
      await loginWith('microsoft')
    } catch (error) {
      setLoginError(error instanceof Error ? error.message : t('loginFailed'))
      setLoadingProvider(null)
    }
  }

  const handlePasswordLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoginError(null)
    setLoadingProvider('password')
    try {
      const response = await fetch('/api/proxy/settings/auth/login-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password }),
      })
      const data = await response.json()
      if (!response.ok) {
        if (response.status === 404) setLoginError(t('usernameNotFound'))
        else if (response.status === 401) setLoginError(t('incorrectPassword'))
        else if (response.status === 400) setLoginError(data.detail || t('oauthAccount'))
        else setLoginError(data.detail || t('loginFailed'))
        return
      }
      localStorage.setItem('id_token', data.id_token)
      localStorage.setItem('refresh_token', data.refresh_token)
      localStorage.setItem('auth_provider', 'password')
      localStorage.setItem('auth_service_name', 'password')
      syncLocaleFromBackend().catch(() => {})
      const payload = JSON.parse(atob(data.id_token.split('.')[1]))
      const userEmail = payload.email || payload.user_email
      const workspaceId = toWorkspaceId(userEmail)
      window.location.href = `/workspace/${workspaceId}/crm`
    } catch (error) {
      setLoginError(t('networkError'))
    } finally {
      setLoadingProvider(null)
    }
  }

  // ── WeChat QR Login ──
  const startWechatLogin = useCallback(async () => {
    setWechatLoading(true)
    setWechatExpired(false)
    setWechatScanned(false)
    setLoginError(null)
    setWechatNickname(null)

    try {
      const response = await fetch('/api/proxy/settings/wechat/qr/login', {
        method: 'POST',
      })
      if (!response.ok) throw new Error('Failed to generate QR code')
      const data = await response.json()

      setWechatQrUrl(data.qr_url)
      setWechatSceneId(data.scene_id)
      setCurrentView('wechat')

      if (pollRef.current) clearInterval(pollRef.current)
      const expireAt = Date.now() + data.expire_seconds * 1000

      pollRef.current = setInterval(async () => {
        if (Date.now() > expireAt) {
          if (pollRef.current) clearInterval(pollRef.current)
          setWechatExpired(true)
          return
        }

        try {
          const statusResp = await fetch(`/api/proxy/settings/wechat/qr/status/${data.scene_id}`)
          if (!statusResp.ok) {
            if (statusResp.status === 410) {
              if (pollRef.current) clearInterval(pollRef.current)
              setWechatExpired(true)
            }
            return
          }
          const statusData = await statusResp.json()

          if (statusData.status === 'scanned') {
            setWechatScanned(true)
          } else if (statusData.status === 'bound') {
            if (pollRef.current) clearInterval(pollRef.current)
            setWechatScanned(true)
            localStorage.setItem('id_token', statusData.id_token)
            localStorage.setItem('refresh_token', statusData.refresh_token)
            localStorage.setItem('auth_provider', 'wechat')
            localStorage.setItem('auth_service_name', 'wechat')
            syncLocaleFromBackend().catch(() => {})
            const payload = JSON.parse(atob(statusData.id_token.split('.')[1]))
            const userEmail = payload.email || payload.user_email
            const workspaceId = toWorkspaceId(userEmail)
            window.location.href = `/workspace/${workspaceId}/crm`
          } else if (statusData.status === 'needs_bind') {
            if (pollRef.current) clearInterval(pollRef.current)
            setWechatNickname(statusData.wechat_nickname || '')
            setCurrentView('wechat-bind')
          }
        } catch {
          // Ignore polling errors
        }
      }, 2000)
    } catch (error) {
      setLoginError(error instanceof Error ? error.message : t('loginFailed'))
    } finally {
      setWechatLoading(false)
    }
  }, [t])

  const handleWechatBind = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!wechatSceneId) return
    setLoginError(null)
    setLoadingProvider('wechat-bind')

    try {
      const response = await fetch('/api/proxy/settings/wechat/bind', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scene_id: wechatSceneId,
          username: username.trim(),
          password,
        }),
      })
      const data = await response.json()
      if (!response.ok) {
        setLoginError(data.detail || t('loginFailed'))
        return
      }
      localStorage.setItem('id_token', data.id_token)
      localStorage.setItem('refresh_token', data.refresh_token)
      localStorage.setItem('auth_provider', 'wechat')
      localStorage.setItem('auth_service_name', 'wechat')
      syncLocaleFromBackend().catch(() => {})
      const payload = JSON.parse(atob(data.id_token.split('.')[1]))
      const userEmail = payload.email || payload.user_email
      const workspaceId = toWorkspaceId(userEmail)
      window.location.href = `/workspace/${workspaceId}/crm`
    } catch {
      setLoginError(t('networkError'))
    } finally {
      setLoadingProvider(null)
    }
  }

  const handleWechatRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!wechatSceneId) return
    setLoginError(null)
    setLoadingProvider('wechat-register')

    try {
      const response = await fetch('/api/proxy/settings/wechat/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scene_id: wechatSceneId,
          username: username.trim(),
          password,
        }),
      })
      const data = await response.json()
      if (!response.ok) {
        setLoginError(data.detail || t('loginFailed'))
        return
      }
      localStorage.setItem('id_token', data.id_token)
      localStorage.setItem('refresh_token', data.refresh_token)
      localStorage.setItem('auth_provider', 'wechat')
      localStorage.setItem('auth_service_name', 'wechat')
      syncLocaleFromBackend().catch(() => {})
      const payload = JSON.parse(atob(data.id_token.split('.')[1]))
      const userEmail = payload.email || payload.user_email
      const workspaceId = toWorkspaceId(userEmail)
      window.location.href = `/workspace/${workspaceId}/crm`
    } catch {
      setLoginError(t('networkError'))
    } finally {
      setLoadingProvider(null)
    }
  }

  const monoTagForView = () => {
    if (currentView === 'wechat') return t('wechatSigninTag')
    if (currentView === 'wechat-bind') return t('linkWechatTag')
    return t('secureSignin')
  }

  const combinedError = loginError || authError

  return (
    <main className="grid grid-cols-[minmax(520px,560px)_1fr] min-h-screen bg-bone font-body text-ink text-[15px] max-lg:grid-cols-1 antialiased">
      {/* ═══════════ LEFT : AUTH PANE ═══════════ */}
      <section
        className="bg-paper border-r border-rule grid grid-rows-[auto_1fr_auto] px-14 pt-10 pb-8 relative max-lg:px-10"
        aria-label="Sign in"
      >
        <header className="flex items-center justify-between">
          <a href="#" aria-label="Prelude 璞序" className="inline-flex items-center gap-3 no-underline text-deep">
            <span className="font-display text-2xl tracking-[-0.01em] text-deep leading-none">Prelude</span>
            <span className="font-display text-xl text-mute tracking-[0.04em] border-l border-rule pl-3.5 leading-none">璞序</span>
          </a>
          <span className="font-mono text-[10.5px] font-medium tracking-[0.14em] uppercase text-mute whitespace-nowrap">
            <span className="inline-block w-[5px] h-[5px] rounded-full bg-accent mr-2 align-[1px] shadow-[0_0_0_3px_var(--accent-lo)]" />
            {monoTagForView()}
          </span>
        </header>

        <div className="self-center max-w-[400px] w-full mx-auto pt-4 pb-6">
          {currentView === 'main' && (
            <MainView onUsernameLogin={() => setCurrentView('password')} />
          )}
          {currentView === 'password' && (
            <PasswordView
              username={username}
              password={password}
              showPassword={showPassword}
              loadingProvider={loadingProvider}
              error={combinedError}
              onUsernameChange={setUsername}
              onPasswordChange={setPassword}
              onTogglePassword={() => setShowPassword((s) => !s)}
              onSubmit={handlePasswordLogin}
              onBack={goBackToMain}
            />
          )}
          {currentView === 'wechat' && (
            <WechatQrView
              wechatQrUrl={wechatQrUrl}
              wechatScanned={wechatScanned}
              wechatExpired={wechatExpired}
              onBack={goBackToMain}
              onRefresh={startWechatLogin}
            />
          )}
          {currentView === 'wechat-bind' && (
            <WechatBindView
              username={username}
              password={password}
              showPassword={showPassword}
              wechatNickname={wechatNickname}
              bindMode={bindMode}
              loadingProvider={loadingProvider}
              error={combinedError}
              onUsernameChange={setUsername}
              onPasswordChange={setPassword}
              onTogglePassword={() => setShowPassword((s) => !s)}
              onBindModeChange={(m) => {
                setBindMode(m)
                setLoginError(null)
              }}
              onBind={handleWechatBind}
              onRegister={handleWechatRegister}
              onBack={goBackToMain}
            />
          )}
        </div>

        <footer className="flex items-center justify-between gap-3">
          <span className="font-mono text-[10px] font-medium tracking-[0.16em] uppercase text-mute">{t('copyright')}</span>
          <span className="font-mono text-[10px] font-medium tracking-[0.16em] uppercase text-mute">{t('version')}</span>
        </footer>
      </section>

      {/* ═══════════ RIGHT : SHOWCASE ═══════════ */}
      <Showcase />
    </main>
  )
}
