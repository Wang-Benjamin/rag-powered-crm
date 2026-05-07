'use client'

import React, { useState, useEffect } from 'react'
import dynamic from 'next/dynamic'
import { motion } from 'framer-motion'
import { useSearchParams } from 'next/navigation'
import { useLeadContext } from '@/contexts/LeadContext'

import LeadManagement from './LeadManagement'

const CompetitorView = dynamic(() => import('./bol/CompetitorView'))
const CampaignList = dynamic(() => import('./campaigns/CampaignList'))

interface LeadGenerationHubProps {
  workspaceId: string
}

function LeadGenerationHub({ workspaceId }: LeadGenerationHubProps) {
  const searchParams = useSearchParams()
  const tabFromUrl = searchParams?.get('tab') || 'lead-management'
  const [activeMainTab, setActiveMainTab] = useState<string>(tabFromUrl)
  const { isLoadedFromCache } = useLeadContext()

  const animationDuration = isLoadedFromCache ? 0.05 : 0.2

  useEffect(() => {
    setActiveMainTab(tabFromUrl)
  }, [tabFromUrl])

  return (
    <div className="flex h-full flex-col">
      {/* Main Content */}
      <div className="flex-1 overflow-hidden">
        <div className="h-full overflow-y-auto bg-muted">
          {activeMainTab === 'lead-management' && (
            <motion.div
              key="lead-management"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: animationDuration }}
              className="h-full"
            >
              <LeadManagement />
            </motion.div>
          )}

          {activeMainTab === 'competitors' && (
            <motion.div
              key="competitors"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: animationDuration }}
              className="h-full overflow-y-auto"
            >
              <CompetitorView />
            </motion.div>
          )}

          {activeMainTab === 'campaigns' && (
            <motion.div
              key="campaigns"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: animationDuration }}
              className="h-full"
            >
              <CampaignList />
            </motion.div>
          )}
        </div>
      </div>
    </div>
  )
}

export default LeadGenerationHub
