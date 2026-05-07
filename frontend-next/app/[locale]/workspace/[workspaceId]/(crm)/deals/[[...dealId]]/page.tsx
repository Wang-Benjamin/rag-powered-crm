'use client'

import React from 'react'
import dynamic from 'next/dynamic'
import { useRouter } from '@/i18n/navigation'
import { useParams, useSearchParams } from 'next/navigation'
import DealsWrapper from '@/components/crm/deals/DealsWrapper'
import { Dialog, DialogContent } from '@/components/ui/dialog'

const DealDetailPage = dynamic(() => import('@/components/crm/deals/DealDetailModal'))

export default function DealsPage() {
  const params = useParams()
  const searchParams = useSearchParams()
  const router = useRouter()

  const workspaceId = params?.workspaceId as string
  const dealIdParam = params?.dealId as string[] | undefined
  const rawDealId = dealIdParam?.[0]
  // Guard: only treat as valid if it's a numeric string (not "undefined", "NaN", etc.)
  const dealId = rawDealId && /^\d+$/.test(rawDealId) ? rawDealId : undefined
  const initialTab = searchParams?.get('tab') || 'overview'

  const handleCloseModal = () => {
    router.push(`/workspace/${workspaceId}/deals`)
  }

  return (
    <>
      <DealsWrapper wsConnection={{ isConnected: true, onRetry: () => {} }} />

      <Dialog open={!!dealId} onOpenChange={(open) => !open && handleCloseModal()}>
        <DialogContent className="h-[95vh] w-full max-w-full overflow-y-auto p-0">
          {dealId && <DealDetailPage dealId={dealId} initialTab={initialTab} />}
        </DialogContent>
      </Dialog>
    </>
  )
}
