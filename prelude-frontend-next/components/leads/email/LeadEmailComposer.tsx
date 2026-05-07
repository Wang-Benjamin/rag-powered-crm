'use client'

import React, { useState } from 'react'
import { useTranslations } from 'next-intl'
import { toast } from 'sonner'
import { crmService } from '@/lib/api/crm'
import { crmApiClient } from '@/lib/api/client'
import type { Lead } from '@/types/leads'
import type { ReplyContext } from '@/types/email'
import EmailComposer from '@/components/email/shared/EmailComposer'
import { useSavedTemplates } from '@/hooks/useSavedTemplates'
import { useFactoryDefaults } from '@/hooks/useFactoryDefaults'
import { getNextBuyersMorningWindow } from '@/lib/utils/scheduleTime'

interface LeadEmailComposerProps {
  lead: Lead
  onClose: () => void
  onEmailSent?: (data: any) => void
  embedded?: boolean
}

const LeadEmailComposer: React.FC<LeadEmailComposerProps> = ({
  lead,
  onClose,
  onEmailSent,
  embedded = false,
}) => {
  const t = useTranslations('email')
  const { userTemplates } = useSavedTemplates({ templateType: 'leadgen' })
  const {
    products, setProducts, tradeCerts, setTradeCerts,
    moq, setMoq, leadTime, setLeadTime,
    sampleStatus, setSampleStatus,
  } = useFactoryDefaults()
  // Random 11:30am–12:29pm ET seed for the schedule popover; stable per-mount.
  const [defaultScheduleTime] = useState(() => getNextBuyersMorningWindow())

  const handleGenerateEmail = async (
    prompt: string,
    templateId?: string | null,
    factoryData?: Record<string, any>
  ) => {
    const leadId = lead.leadId
    if (!leadId) {
      throw new Error('No valid lead ID found. Cannot generate email without lead ID.')
    }

    const data = await crmService.generateInitialOutreach({
      leadId: String(leadId),
      customPrompt: prompt.trim() || undefined,
      templateId: templateId || undefined,
      products: factoryData?.products,
      certifications: factoryData?.certifications,
      moq: factoryData?.moq,
      leadTime: factoryData?.leadTime,
      sampleStatus: factoryData?.sampleStatus,
    })
    if (data.classification?.intent === 'ooo') {
      toast.error(t('composer.buyerOoo'))
      return { subject: '', body: '' }
    }
    return {
      subject:
        data.subject ||
        data.emailData?.subject ||
        data.email?.subject ||
        `Regarding ${lead.company || 'your business'}`,
      body: data.body || data.emailData?.body || data.email?.body || '',
    }
  }

  const handleSendEmail = async (
    toEmail: string,
    subject: string,
    body: string,
    _replyContext?: ReplyContext
  ) => {
    const leadId = lead.leadId
    if (!leadId) {
      throw new Error('No valid lead ID found. Cannot send email without lead ID.')
    }

    const authProvider = typeof window !== 'undefined' ? localStorage.getItem('auth_provider') : null
    const provider =
      authProvider === 'google' ? 'gmail' : authProvider === 'microsoft' ? 'outlook' : undefined

    await crmService.sendInitialOutreach({
      leadId: String(leadId),
      toEmail,
      subject,
      body,
      provider: provider ?? undefined,
    })
  }

  const handleScheduleSend = async (
    scheduledAt: string,
    toEmail: string,
    subject: string,
    body: string,
  ) => {
    const leadId = lead.leadId
    if (!leadId) {
      throw new Error('No valid lead ID found.')
    }
    const authProvider = typeof window !== 'undefined' ? localStorage.getItem('auth_provider') : null
    const provider =
      authProvider === 'google' ? 'gmail' : authProvider === 'microsoft' ? 'outlook' : 'sendgrid'
    await crmApiClient.post('/initial-outreach/schedule', {
      scheduledAt,
      leadId: String(leadId),
      toEmail,
      subject,
      body,
      provider,
    })
  }

  const leadId = String(lead.leadId || '')

  return (
    <EmailComposer
      entityType="lead"
      entityId={leadId}
      entityEmail={lead.personnel?.find((p: any) => p.email)?.email || ''}
      entityName={lead.company || lead.name || 'Lead'}
      onGenerateEmail={handleGenerateEmail}
      onSendEmail={handleSendEmail}
      onScheduleSend={handleScheduleSend}
      onClose={onClose}
      onEmailSent={onEmailSent}
      embedded={embedded}
      userTemplates={userTemplates}
      defaultScheduleTime={defaultScheduleTime}
      factoryData={{
        products,
        certifications: tradeCerts,
        moq,
        leadTime,
        sampleStatus,
        onProductsChange: setProducts,
        onCertificationsChange: setTradeCerts,
        onMoqChange: setMoq,
        onLeadTimeChange: setLeadTime,
        onSampleStatusChange: setSampleStatus,
      }}
    />
  )
}

export default LeadEmailComposer
