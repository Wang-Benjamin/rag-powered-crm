'use client'

import React from 'react'
import SidebarMenu from './sidebar/SidebarMenu'
import { useTrialStatus } from '@/hooks/useTrialStatus'
import { TrialExpiredBanner } from '@/components/trial/TrialExpiredBanner'
import { SyncErrorBanner } from '@/components/sync/SyncErrorBanner'

export default function DashboardLayoutContent({ children }: { children: React.ReactNode }) {
  const { isExpired } = useTrialStatus()

  return (
    <div className="dashboard-container flex h-screen flex-col overflow-hidden">
      <TrialExpiredBanner show={isExpired} />
      <SyncErrorBanner />

      <div className="flex flex-1 overflow-hidden">
        {/* Left Sidebar Navigation */}
        <div className="relative shrink-0 overflow-visible border-r border-rule bg-gradient-to-b from-bone via-paper to-cream transition-all duration-300">
          <SidebarMenu />
        </div>

        <div className="flex-1 overflow-hidden">
          <div className="h-full">
            {children}
          </div>
        </div>
      </div>
    </div>
  )
}
