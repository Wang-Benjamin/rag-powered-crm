'use client'

import React from 'react'
import { useSearchParams } from 'next/navigation'
import EmailSettingsTab from '@/components/email/settings/EmailSettingsTab'
import { EmailTemplatesTab } from '@/components/email/templates/EmailTemplatesTab'

export default function ProfilesPage() {
  const searchParams = useSearchParams()

  const tabParam = searchParams?.get('tab')
  const isNewTemplate = searchParams?.get('new') === 'true'
  const activeTab = tabParam === 'preferences' || tabParam === 'templates' ? tabParam : 'templates'

  return (
    <>
      <div className="h-full">
        {activeTab === 'preferences' ? (
          <EmailSettingsTab />
        ) : (
          <EmailTemplatesTab autoCreateNew={isNewTemplate} />
        )}
      </div>
    </>
  )
}
