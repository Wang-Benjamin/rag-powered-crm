'use client'

import React from 'react'
import { useTranslations } from 'next-intl'
import { useMassEmailComposer } from '@/hooks/useMassEmailComposer'
import { useSavedTemplates } from '@/hooks/useSavedTemplates'
import { useFactoryDefaults } from '@/hooks/useFactoryDefaults'
import MassEmailComposerUI from '@/components/email/shared/MassEmailComposerUI'
import { useAuth } from '@/hooks/useAuth'
import { useCRM } from '@/contexts/CRMContext'
import { crmApiClient } from '@/lib/api/client'
import type { Customer } from '@/types/crm'

interface Recipient {
  id: string
  dealId?: string
  name?: string
  email: string
  company?: string
}

interface Column {
  id: string
  label: string
  description: string
}

type EntityType = 'customer' | 'deal'

const COLUMNS: Record<EntityType, Column[]> = {
  customer: [
    { id: 'name', label: 'Company Name', description: 'Customer company name' },
    { id: 'phone', label: 'Phone', description: 'Customer phone number' },
  ],
  deal: [
    { id: 'dealName', label: 'Deal Name', description: 'Name of the deal' },
    { id: 'clientName', label: 'Client', description: 'Client company name' },
    { id: 'valueUsd', label: 'Value', description: 'Deal value in USD' },
    { id: 'roomStatus', label: 'Status', description: 'Current deal room status' },
    { id: 'clientEmail', label: 'Email', description: 'Client email address' },
  ],
}

interface MassEmailComposerProps {
  entityType?: EntityType
  selectedClientIds?: string[]
  selectedDealIds?: Set<string>
  onClose: () => void
  onEmailsSent?: (result: any) => void
}

const MassEmailComposer: React.FC<MassEmailComposerProps> = ({
  entityType = 'customer',
  selectedClientIds = [],
  selectedDealIds = new Set(),
  onClose,
  onEmailsSent,
}) => {
  const t = useTranslations('email')
  const { user } = useAuth()
  const { customers, deals } = useCRM()

  const {
    userTemplates,
    selectedTemplate: selectedSavedTemplate,
    selectTemplate: setSelectedSavedTemplate,
  } = useSavedTemplates({ templateType: 'crm', enabled: !!user?.email })

  const {
    products, setProducts, tradeCerts, setTradeCerts,
    moq, setMoq, leadTime, setLeadTime,
    sampleStatus, setSampleStatus,
  } = useFactoryDefaults()

  const { allRecipients, selectedIds } = (() => {
    if (entityType === 'deal') {
      const selectedDeals = deals.filter((deal) => selectedDealIds.has(String(deal.dealId || '')))
      const recipients: Recipient[] = deals
        .filter((deal) => deal.clientEmail)
        .map((deal) => ({
          id: String(deal.clientId || ''),
          dealId: String(deal.dealId || ''),
          name: deal.dealName,
          email: deal.clientEmail!,
          company: deal.clientName,
        }))
      const ids = new Set(selectedDeals.map((deal) => String(deal.clientId || '')))
      return { allRecipients: recipients, selectedIds: ids }
    } else {
      const recipients: Recipient[] = customers.map((customer: Customer) => ({
        id: String(customer.id),
        name: customer.company || customer.clientName || '',
        email: customer.clientEmail || '',
        company: customer.company || customer.clientName || '',
      }))
      return { allRecipients: recipients, selectedIds: new Set(selectedClientIds) }
    }
  })()

  const getDealIdForClientId = (clientId: string): string | null => {
    if (entityType !== 'deal') return null
    return allRecipients.find((r) => r.id === clientId)?.dealId || null
  }

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
      const payload: Record<string, any> = {
        customerIds: selectedIds,
        customPrompt: customMessage,
        templateId: templateId || null,
      }
      // Always include factory data
      const validProducts = products.filter((p) => p.name || p.fobPrice || p.landedPrice)
      if (validProducts.length) payload.products = validProducts
      if (tradeCerts.length) payload.certifications = tradeCerts
      if (moq) payload.moq = moq
      if (leadTime) payload.leadTime = leadTime
      if (sampleStatus) payload.sampleStatus = sampleStatus
      return await crmApiClient.post('/generate-personalized-mass-emails', payload, {
        timeout: 120000,
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
      campaignContext?: Record<string, any>
    }) => {
      let emailsToSend = emails

      if (entityType === 'deal') {
        emailsToSend = emails.map((email) => ({
          ...email,
          dealId: getDealIdForClientId(email.clientId),
        }))
      }

      const modifiedEmails = modifiedIndices?.length
        ? emailsToSend.filter((_, index) => modifiedIndices.includes(index))
        : []

      return await crmApiClient.post('/send-personalized-mass-emails', {
        emails: emailsToSend,
        provider,
        modifiedEmails,
        // Trade fields → campaign.trade_context (email_mass_router._build_trade_context)
        customPrompt: campaignContext?.customPrompt,
        products: campaignContext?.products,
        certifications: campaignContext?.certifications,
        moq: campaignContext?.moq,
        leadTime: campaignContext?.leadTime,
        sampleStatus: campaignContext?.sampleStatus,
      })
    },

    preparePersonalizedEmail: (email: any) => ({
      subject: email.subject,
      body: email.body,
      clientId: email.clientId,
      ...(entityType === 'deal' ? { dealId: email.dealId } : {}),
      toEmail: email.clientEmail,
    }),

    scheduleSend: async (params: {
      scheduledAt: string
      selectedIds: string[]
      emails?: any[]
      provider: string | null
      modifiedIndices?: number[]
    }) => {
      const emailsToSchedule =
        entityType === 'deal'
          ? params.emails?.map((email: any) => ({
              ...email,
              dealId: getDealIdForClientId(email.clientId),
            }))
          : params.emails
      const modifiedEmails = params.modifiedIndices?.length
        ? emailsToSchedule?.filter((_: any, i: number) => params.modifiedIndices?.includes(i))
        : []

      return await crmApiClient.post('/schedule-mass-email', {
        scheduledAt: params.scheduledAt,
        emailType: 'personalized',
        provider: params.provider,
        emails: emailsToSchedule,
        modifiedEmails,
      })
    },
  }

  const massEmailState = useMassEmailComposer({
    selectedIds,
    allRecipients,
    apiHandlers,
    tradeFields: { products, certifications: tradeCerts, moq, leadTime, sampleStatus },
  })

  const getCompanyName = (email: any) =>
    entityType === 'deal' ? email.dealName || email.clientName : email.clientName
  const getCompanyEmail = (email: any) => email.clientEmail

  const recipientLabel =
    entityType === 'deal' ? t('recipientLabels.deals') : t('recipientLabels.clients')

  return (
    <MassEmailComposerUI
      title={t('composer.massEmailTitle', {
        count: massEmailState.recipients.length,
        label: recipientLabel,
      })}
      columns={COLUMNS[entityType]}
      recipientLabel={recipientLabel}
      userTemplates={userTemplates}
      getCompanyName={getCompanyName}
      getCompanyEmail={getCompanyEmail}
      source="crm"
      onClose={onClose}
      onEmailsSent={onEmailsSent}
      onTemplateSelect={setSelectedSavedTemplate}
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
