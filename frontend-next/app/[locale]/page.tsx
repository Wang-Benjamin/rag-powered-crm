'use client'

import { useEffect } from 'react'
import { useRouter } from '@/i18n/navigation'
import { useAuth } from '@/hooks/useAuth'
import { workspacePathFromToken } from '@/lib/auth/tokenUtils'
import { PageLoader } from '@/components/ui/page-loader'

export default function HomePage() {
  const router = useRouter()
  const { isAuthenticated, isLoading } = useAuth()

  useEffect(() => {
    if (!isLoading) {
      if (isAuthenticated) {
        const idToken = localStorage.getItem('id_token')
        if (idToken) {
          const path = workspacePathFromToken(idToken)
          if (path) {
            router.push(path)
          } else {
            console.error('Error parsing token')
            router.push('/login')
          }
        }
      } else {
        router.push('/login')
      }
    }
  }, [isAuthenticated, isLoading, router])

  // Show loading while determining auth state
  return (
    <div className="flex min-h-screen items-center justify-center bg-bone">
      <PageLoader brand label="Checking session" />
    </div>
  )
}
