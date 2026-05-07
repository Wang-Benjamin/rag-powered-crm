'use client'

import React, { useEffect, useState } from 'react'
import { useRouter } from '@/i18n/navigation'
import { useParams, usePathname } from 'next/navigation'
import { WorkspaceProvider } from '@/contexts/WorkspaceContext'
import { EmailSyncProvider } from '@/contexts/EmailSyncProvider'
import { useAuth } from '@/hooks/useAuth'
import DashboardLayoutContent from '@/components/layout/DashboardLayoutContent'
import { invitationsApi } from '@/lib/api/invitationsApi'
import PreloadProgress from '@/components/preload/PreloadProgress'
import { PageLoader } from '@/components/ui/page-loader'

interface WorkspaceLayoutProps {
  children: React.ReactNode
}

export default function WorkspaceLayout({ children }: WorkspaceLayoutProps) {
  const params = useParams()
  const workspaceId = (params?.workspaceId as string) || ''
  const pathname = usePathname()
  const router = useRouter()
  const { user, isAuthenticated, isLoading } = useAuth()
  const [onboardingChecked, setOnboardingChecked] = useState(false)
  const [preloadComplete, setPreloadComplete] = useState(() => {
    if (typeof window !== 'undefined') {
      return sessionStorage.getItem('workspace_preloaded') === 'true'
    }
    return false
  })

  // Any onboarding-related page (full-screen /onboarding or in-sidebar /user-onboarding)
  const isOnboardingRoute = pathname?.includes('/onboarding')
  // Full-screen onboarding: no sidebar, no desktop guard
  const isFullScreenOnboarding = isOnboardingRoute && !pathname?.includes('/user-onboarding')

  // Gate 1: Auth — redirect to login if not authenticated
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/login')
      return
    }

    if (!workspaceId || workspaceId === 'undefined') {
      console.error('Invalid workspaceId:', workspaceId)
      router.push('/login')
    }
  }, [workspaceId, router, isAuthenticated, isLoading])

  // Gate 2: Onboarding — check onboarding_status after auth is confirmed
  useEffect(() => {
    if (!isAuthenticated || isLoading || !user?.email) return
    if (onboardingChecked) return

    if (isOnboardingRoute) {
      setOnboardingChecked(true)
      return
    }

    let cancelled = false
    async function checkOnboarding() {
      try {
        const response = await invitationsApi.getUserInvitations(user!.email)
        if (cancelled) return

        const status = response.user?.onboardingStatus
        // Redirect to full-screen onboarding if not completed and not skipped
        if (status !== 'completed' && status !== 'skipped') {
          router.push(`/workspace/${workspaceId}/onboarding`)
          return
        }
      } catch {
        // If we can't fetch, allow through (don't block on network error)
      }
      if (!cancelled) setOnboardingChecked(true)
    }

    checkOnboarding()
    return () => {
      cancelled = true
    }
  }, [isAuthenticated, isLoading, user?.email, pathname, workspaceId, router])

  const handlePreloadComplete = () => {
    sessionStorage.setItem('workspace_preloaded', 'true')
    setPreloadComplete(true)
  }

  const handlePreloadError = () => {
    // Still mark as complete — don't block the app on preload failure
    handlePreloadComplete()
  }

  // Show loading while auth or onboarding check is in progress
  if (isLoading || !isAuthenticated || (!onboardingChecked && !isOnboardingRoute)) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bone">
        <PageLoader brand label="Preparing workspace" />
      </div>
    )
  }

  // Full-screen onboarding — no sidebar, no preload
  if (isFullScreenOnboarding) {
    return <WorkspaceProvider workspaceId={workspaceId}>{children}</WorkspaceProvider>
  }

  // Preload gate — show PreloadProgress if cache is cold (not already done in callback)
  if (!preloadComplete) {
    return (
      <WorkspaceProvider workspaceId={workspaceId}>
        <PreloadProgress onComplete={handlePreloadComplete} onError={handlePreloadError} />
      </WorkspaceProvider>
    )
  }

  return (
    <WorkspaceProvider workspaceId={workspaceId}>
      <EmailSyncProvider>
        <DashboardLayoutContent>{children}</DashboardLayoutContent>
      </EmailSyncProvider>
    </WorkspaceProvider>
  )
}
