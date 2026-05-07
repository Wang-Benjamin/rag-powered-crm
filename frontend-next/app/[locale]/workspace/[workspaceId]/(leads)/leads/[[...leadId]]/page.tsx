'use client'

import React from 'react'
import dynamic from 'next/dynamic'
import { useRouter } from '@/i18n/navigation'
import { useParams, useSearchParams } from 'next/navigation'
import LeadGenerationHub from '@/components/leads/LeadGenerationHub'
import { Dialog, DialogContent } from '@/components/ui/dialog'

const LeadDetailPage = dynamic(() => import('@/components/leads/details/LeadDetailModal'))

export default function LeadsPage() {
  const params = useParams()
  const searchParams = useSearchParams()
  const router = useRouter()

  const workspaceId = params?.workspaceId as string
  const leadIdParam = params?.leadId as string[] | undefined
  const leadId = leadIdParam?.[0]
  const initialTab = searchParams?.get('tab') || 'overview'

  const handleCloseModal = () => {
    router.push(`/workspace/${workspaceId}/leads`)
  }

  return (
    <>
      <LeadGenerationHub workspaceId={workspaceId} />

      <Dialog open={!!leadId} onOpenChange={(open) => !open && handleCloseModal()}>
        <DialogContent className="h-[95vh] w-full max-w-full overflow-y-auto p-0">
          {leadId && <LeadDetailPage leadId={leadId} initialTab={initialTab} />}
        </DialogContent>
      </Dialog>
    </>
  )
}
