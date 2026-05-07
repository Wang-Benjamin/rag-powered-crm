'use client'

import React from 'react'
import dynamic from 'next/dynamic'
import { useRouter } from '@/i18n/navigation'
import { useParams, useSearchParams } from 'next/navigation'
import CustomerRelationshipManagement from '@/components/crm/customers/CustomerRelationshipManagement'
import { Dialog, DialogContent } from '@/components/ui/dialog'

const CustomerDetailPage = dynamic(() => import('@/components/crm/customers/CustomerDetailModal'))

export default function CRMPage() {
  const params = useParams()
  const searchParams = useSearchParams()
  const router = useRouter()

  const workspaceId = params?.workspaceId as string
  const customerIdParam = params?.customerId as string[] | undefined
  const customerId = customerIdParam?.[0]
  const initialTab = searchParams?.get('tab') || 'overview'

  const handleCloseModal = () => {
    router.push(`/workspace/${workspaceId}/crm`)
  }

  return (
    <>
      <CustomerRelationshipManagement wsConnection={{ isConnected: true, onRetry: () => {} }} />

      <Dialog open={!!customerId} onOpenChange={(open) => !open && handleCloseModal()}>
        <DialogContent className="h-[95vh] w-full max-w-full overflow-y-auto p-0">
          {customerId && <CustomerDetailPage customerId={customerId} initialTab={initialTab} />}
        </DialogContent>
      </Dialog>
    </>
  )
}
