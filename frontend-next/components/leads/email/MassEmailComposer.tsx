'use client'

import React, { useState } from 'react'
import { useTranslations } from 'next-intl'
import { crmService } from '@/lib/api/crm'
import { crmApiClient } from '@/lib/api/client'
import { useAuth } from '@/hooks/useAuth'
import { useMassEmailComposer } from '@/hooks/useMassEmailComposer'
import { useSavedTemplates } from '@/hooks/useSavedTemplates'
import { useFactoryDefaults } from '@/hooks/useFactoryDefaults'
import MassEmailComposerUI from '@/components/email/shared/MassEmailComposerUI'
import type { Lead } from '@/types/leads'
import { getNextBuyersMorningWindow } from '@/lib/utils/scheduleTime'

interface Recipient {
  id: string
  name?: string
  email: string
  company?: string
}

interface Column {
  id: string
  label: string
  description: string
}

const COLUMNS: Column[] = [
  { id: 'company', label: 'Company', description: 'Company name' },
  { id: 'location', label: 'Location', description: 'Company location' },
  { id: 'industry', label: 'Industry', description: 'Business industry' },
  { id: 'website', label: 'Website', description: 'Company website URL' },
  { id: 'phone', label: 'Phone', description: 'Contact phone number' },
]

interface MassEmailComposerProps {
  selectedLeadIds: string[]
  allLeads?: Lead[]
  onClose: () => void
  onEmailsSent?: (data: any) => void
}

const MassEmailComposer: React.FC<MassEmailComposerProps> = ({
  selectedLeadIds,
  allLeads = [],
  onClose,
  onEmailsSent,
}) => {
  const t = useTranslations('email')
  const { user } = useAuth()
  const {
    userTemplates,
    selectedTemplate: selectedSavedTemplate,
    selectTemplate: setSelectedSavedTemplate,
  } = useSavedTemplates({ templateType: 'leadgen', enabled: !!user?.email })

  const {
    products, setProducts, tradeCerts, setTradeCerts,
    moq, setMoq, leadTime, setLeadTime,
    sampleStatus, setSampleStatus,
  } = useFactoryDefaults()
  // Random 11:30am–12:29pm ET seed for the schedule popover; stable per-mount.
  const [defaultScheduleTime] = useState(() => getNextBuyersMorningWindow())

  const allRecipients: Recipient[] = allLeads.map((lead) => ({
    id: String(lead.leadId || lead.id || ''),
    name: lead.company,
    email: lead.personnel?.[0]?.email || '',
    company: lead.company,
  }))

  const apiHandlers = {
    generatePersonalized: async ({
      selectedIds,
      customMessage,
      templateId,
    }: {
      selectedIds: string[]
      customMessage: string
      templateId?: string | null
      [key: string]: any
    }) => {
      return await crmService.generateInitialOutreachMass({
        leadIds: selectedIds,
        customPrompt: customMessage || undefined,
        templateId: templateId || undefined,
        products: products.filter((p) => p.name || p.fobPrice || p.landedPrice).length
          ? products
          : undefined,
        certifications: tradeCerts.length ? tradeCerts : undefined,
        moq: moq || undefined,
        leadTime: leadTime || undefined,
        sampleStatus: sampleStatus || undefined,
      })
    },

    sendPersonalized: async ({
      emails,
      provider,
      modifiedIndices,
      campaignContext,
    }: {
      emails: any[]
      provider: string | null
      modifiedIndices?: number[]
      campaignContext?: { customPrompt?: string; [key: string]: any }
    }) => {
      const mappedEmails = emails.map((email) => ({
        leadId: email.leadId,
        subject: email.subject,
        body: email.body,
        toEmail: email.toEmail,
      }))
      const modifiedEmails = modifiedIndices?.length
        ? mappedEmails.filter((_, i) => modifiedIndices.includes(i))
        : []
      return await crmService.sendInitialOutreachMass({
        emails: mappedEmails,
        modifiedEmails,
        provider: provider ?? undefined,
        offer: campaignContext?.offer,
        ask: campaignContext?.ask,
        detail: campaignContext?.detail,
        // Trade fields → campaign.trade_context
        products: campaignContext?.products,
        certifications: campaignContext?.certifications,
        moq: campaignContext?.moq,
        leadTime: campaignContext?.leadTime,
        sampleStatus: campaignContext?.sampleStatus,
      })
    },

    scheduleSend: async (params: {
      scheduledAt: string
      selectedIds: string[]
      emails?: any[]
      provider: string | null
      modifiedIndices?: number[]
    }) => {
      const mappedEmails = (params.emails || []).map((email) => ({
        leadId: email.leadId,
        subject: email.subject,
        body: email.body,
        toEmail: email.toEmail,
      }))
      const modifiedEmails = params.modifiedIndices?.length
        ? mappedEmails.filter((_, i) => params.modifiedIndices?.includes(i))
        : []
      return await crmApiClient.post('/initial-outreach-mass/schedule', {
        scheduledAt: params.scheduledAt,
        emails: mappedEmails,
        modifiedEmails,
        provider: params.provider,
      })
    },

    preparePersonalizedEmail: (email: any) => ({
      subject: email.subject,
      body: email.body,
      leadId: email.leadId,
      toEmail: email.toEmail,
      companyName: email.leadCompany,
      recipient: {
        id: email.leadId,
        name: email.leadCompany,
        email: email.toEmail,
        company: email.leadCompany,
      },
    }),
  }

  const getCompanyName = (email: any): string =>
    email.recipient?.company || email.leadCompany || 'Unknown'
  const getCompanyEmail = (email: any): string =>
    email.toEmail || email.recipient?.email || ''

  const massEmailState = useMassEmailComposer({
    selectedIds: new Set(selectedLeadIds),
    allRecipients,
    apiHandlers,
    tradeFields: { products, certifications: tradeCerts, moq, leadTime, sampleStatus },
  })

  return (
    <MassEmailComposerUI
      title={t('composer.massEmailTitle', {
        count: massEmailState.recipients.length,
        label: t('recipientLabels.leads'),
      })}
      columns={COLUMNS}
      recipientLabel={t('recipientLabels.leads')}
      userTemplates={userTemplates}
      getCompanyName={getCompanyName}
      getCompanyEmail={getCompanyEmail}
      source="buyers"
      onClose={onClose}
      onEmailsSent={onEmailsSent}
      onTemplateSelect={setSelectedSavedTemplate}
      defaultScheduleTime={defaultScheduleTime}
      {...massEmailState}
      bodyEditorRef={massEmailState.bodyTextareaRef as React.RefObject<HTMLDivElement>}
      tradeFields={{
        variant: 'trade' as const,
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

export default MassEmailComposer
