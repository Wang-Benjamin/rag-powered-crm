'use client'

import { useState, useEffect } from 'react'
import { useRouter } from '@/i18n/navigation'
import { useParams } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'
import { invitationsApi } from '@/lib/api/invitationsApi'
import { CustomizeAIQuestionnaire } from '@/components/onboarding/customize-ai/CustomizeAIQuestionnaire'
import { PageLoader } from '@/components/ui/page-loader'

export default function FullScreenOnboardingPage() {
  const { user } = useAuth()
  const params = useParams()
  const router = useRouter()
  const workspaceId = (params?.workspaceId as string) || ''
  const [savedOnboardingStep, setSavedOnboardingStep] = useState(0)
  const [companyDataExists, setCompanyDataExists] = useState(false)
  const [onboardingStatus, setOnboardingStatus] = useState<string>()
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!user?.email) return

    let cancelled = false
    async function fetchStep() {
      try {
        const data = await invitationsApi.getUserInvitations(user!.email)
        if (cancelled) return
        if (data.user?.onboardingStep != null) {
          setSavedOnboardingStep(data.user.onboardingStep)
        }
        if (data.user?.onboardingProgress?.companyDataExists) {
          setCompanyDataExists(true)
        }
        if (data.user?.onboardingStatus) {
          setOnboardingStatus(data.user.onboardingStatus)
        }
      } catch {
        // Allow rendering at step 0 on error
      }
      if (!cancelled) setLoading(false)
    }

    fetchStep()
    return () => {
      cancelled = true
    }
  }, [user?.email])

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bone">
        <PageLoader brand label="Preparing onboarding" />
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper p-4 md:p-8">
      <div className="w-full max-w-5xl">
        <CustomizeAIQuestionnaire
          key={savedOnboardingStep}
          userEmail={user?.email}
          initialStep={savedOnboardingStep}
          onboardingStatus={onboardingStatus}
          companyDataExists={companyDataExists}
          onComplete={() => router.push(`/workspace/${workspaceId}/crm`)}
          onSkip={() => router.push(`/workspace/${workspaceId}/crm`)}
        />
      </div>
    </div>
  )
}
