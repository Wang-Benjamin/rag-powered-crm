'use client'

import React from 'react'
import { AlertTriangle, Sparkles } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { FeedbackSection } from './FeedbackSection'

interface CustomerFeedbackPanelProps {
  customerId: number
  currentUserId?: number
}

export function CustomerFeedbackPanel({ customerId, currentUserId }: CustomerFeedbackPanelProps) {
  const t = useTranslations('crm')

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      {/* Churn Risk Feedback */}
      <FeedbackSection
        title={t('feedback.churnRisk')}
        description={t('feedback.churnRiskDescription')}
        customerId={customerId}
        feedbackCategory="churnRisk"
        currentUserId={currentUserId}
        icon={AlertTriangle}
        iconColor="text-orange-500"
      />

      {/* AI Insights Feedback */}
      <FeedbackSection
        title={t('feedback.aiInsights')}
        description={t('feedback.aiInsightsDescription')}
        customerId={customerId}
        feedbackCategory="aiInsights"
        currentUserId={currentUserId}
        icon={Sparkles}
        iconColor="text-zinc-500"
      />
    </div>
  )
}
