'use client'

import { useEffect, useState, useRef, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'
import { workspacePathFromToken } from '@/lib/auth/tokenUtils'
import { getLocaleCookie } from '@/lib/locale'
import PreloadProgress from '@/components/preload/PreloadProgress'
import { PageLoader } from '@/components/ui/page-loader'

// Force dynamic rendering for this page
export const dynamic = 'force-dynamic'

function AuthCallbackContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { handleAuthCode } = useAuth()
  const [error, setError] = useState<string | null>(null)
  const [authComplete, setAuthComplete] = useState(false)
  const hasProcessed = useRef(false)

  const localePath = (path: string) => {
    const locale = getLocaleCookie()
    return `/${locale}${path}`
  }

  const handlePreloadComplete = () => {
    const idToken = localStorage.getItem('id_token')
    if (idToken) {
      const path = workspacePathFromToken(idToken, { locale: getLocaleCookie() })
      if (path) {
        sessionStorage.setItem('workspace_preloaded', 'true')
        router.push(path)
      } else {
        router.push(localePath('/login'))
      }
    } else {
      router.push(localePath('/login'))
    }
  }

  const handlePreloadError = () => {
    handlePreloadComplete()
  }

  useEffect(() => {
    if (hasProcessed.current) return

    const handleCallback = async () => {
      hasProcessed.current = true
      if (!searchParams) {
        setError('No parameters found')
        setTimeout(() => router.push(localePath('/login')), 3000)
        return
      }

      const code = searchParams.get('code')
      const state = searchParams.get('state')
      const errorParam = searchParams.get('error')

      if (errorParam) {
        setError(`OAuth error: ${errorParam}`)
        setTimeout(() => router.push(localePath('/login')), 3000)
        return
      }

      if (!code || !state) {
        setError('Missing authorization code')
        setTimeout(() => router.push(localePath('/login')), 3000)
        return
      }

      try {
        const success = await handleAuthCode(code, state)
        if (success) {
          setAuthComplete(true)
        } else {
          throw new Error('Authentication failed')
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Authentication failed'
        setError(errorMessage)
        setTimeout(() => router.push(localePath('/login')), 5000)
      }
    }

    handleCallback()
  }, [searchParams, router, handleAuthCode])

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted">
        <div className="text-center">
          <h2 className="mb-4 text-2xl font-bold text-red-600">Authentication Error</h2>
          <p className="mb-4 text-foreground">{error}</p>
          <p className="text-mute">Redirecting to login...</p>
        </div>
      </div>
    )
  }

  return (
    <PreloadProgress
      initialStage={authComplete ? 'loading' : 'authenticating'}
      onComplete={handlePreloadComplete}
      onError={handlePreloadError}
    />
  )
}

export default function AuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-bone">
          <PageLoader brand label="Signing you in" />
        </div>
      }
    >
      <AuthCallbackContent />
    </Suspense>
  )
}
