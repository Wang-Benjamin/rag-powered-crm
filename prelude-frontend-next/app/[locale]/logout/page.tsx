'use client'

import { useEffect } from 'react'
import { useRouter } from '@/i18n/navigation'
import { useTranslations } from 'next-intl'
import { useAuth } from '@/hooks/useAuth'
import { PageLoader } from '@/components/ui/page-loader'

export default function LogoutPage() {
  const router = useRouter()
  const { logout } = useAuth()
  const t = useTranslations('auth.logout')

  useEffect(() => {
    // Clear all auth data
    logout()

    // Also clear any additional storage items
    if (typeof window !== 'undefined') {
      // Clear all localStorage items related to auth
      const keysToRemove = [
        'id_token',
        'refresh_token',
        'auth_provider',
        'auth_service_name',
        'google_access_token',
        'google_user_email',
        'google_connected',
        'google_auth_time',
        'google_refresh_token',
        'microsoft_access_token',
        'microsoft_user_email',
        'microsoft_connected',
        'microsoft_auth_time',
        'microsoft_refresh_token',
        'auth-storage',
        'prelude.syncError.v1',
      ]

      keysToRemove.forEach((key) => {
        localStorage.removeItem(key)
      })

      // Clear sessionStorage
      sessionStorage.clear()

      // Clear cookies if any
      document.cookie.split(';').forEach(function (c) {
        document.cookie = c
          .replace(/^ +/, '')
          .replace(/=.*/, '=;expires=' + new Date().toUTCString() + ';path=/')
      })
    }

    // Redirect to login page
    router.push('/login')
  }, [logout, router])

  return (
    <div className="flex min-h-screen items-center justify-center bg-bone">
      <PageLoader brand label={t('loggingOut')} />
    </div>
  )
}
