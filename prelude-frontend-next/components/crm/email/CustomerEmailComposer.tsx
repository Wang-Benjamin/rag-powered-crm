'use client'

import React from 'react'
import { useTranslations } from 'next-intl'
import { toast } from 'sonner'
import { crmApiClient } from '@/lib/api/client'
import { crmService } from '@/lib/api/crm'
import { useAuth } from '@/hooks/useAuth'
import type { Customer } from '@/types/crm'
import type { ReplyContext } from '@/types/email'
import EmailComposer from '@/components/email/shared/EmailComposer'
import { useSavedTemplates } from '@/hooks/useSavedTemplates'
import { useFactoryDefaults } from '@/hooks/useFactoryDefaults'

interface CustomerEmailComposerProps {
  customer: Customer
  onClose: () => void
  onEmailSent?: (data: any) => void
  embedded?: boolean
  dealId?: string | null
}

const CustomerEmailComposer: React.FC<CustomerEmailComposerProps> = ({
  customer,
  onClose,
  onEmailSent,
  embedded = false,
  dealId = null,
}) => {
  const t = useTranslations('crm')
  const tEmail = useTranslations('email')
  const { user } = useAuth()
  const { userTemplates } = useSavedTemplates({ templateType: 'crm' })
  const {
    products, setProducts, tradeCerts, setTradeCerts,
    moq, setMoq, leadTime, setLeadTime,
    sampleStatus, setSampleStatus,
  } = useFactoryDefaults()

  const handleGenerateEmail = async (
    prompt: string,
    templateId?: string | null,
    factoryData?: Record<string, any>
  ) => {
    const data = await crmApiClient.post('/generate-email', {
      customerId: customer.id,
      customPrompt: prompt,
      templateId: templateId || null,
      ...factoryData,
    })
    if (data.classification?.intent === 'ooo') {
      toast.error(tEmail('composer.buyerOoo'))
      return { subject: '', body: '' }
    }
    return {
      subject:
        data.emailData?.subject ||
        t('emailComposer.fallbackSubject', { company: customer.company }),
      body:
        data.emailData?.body ||
        t('emailComposer.fallbackBody', { contact: customer.clientName || 'there' }),
    }
  }

  const handleScheduleSend = async (
    scheduledAt: string,
    toEmail: string,
    subject: string,
    body: string,
  ) => {
    const authProvider = typeof window !== 'undefined' ? localStorage.getItem('auth_provider') : null
    const provider =
      authProvider === 'google' ? 'gmail' : authProvider === 'microsoft' ? 'outlook' : 'sendgrid'
    await crmApiClient.post('/schedule-direct-email', {
      scheduledAt,
      toEmail,
      subject,
      body,
      customerId: Number(customer.id),
      provider,
      dealId: dealId || undefined,
    })
  }

  const handleSendEmail = async (
    toEmail: string,
    subject: string,
    body: string,
    replyContext?: ReplyContext
  ) => {
    const result = await crmService.sendEmailWithReply(
      Number(customer.id),
      toEmail,
      subject,
      body,
      replyContext,
      dealId
    )
    if (!result.success) {
      throw new Error(result.error || 'Failed to send email')
    }
  }

  return (
    <EmailComposer
      entityType="customer"
      entityId={String(customer.id)}
      entityEmail={customer.clientEmail || ''}
      entityName={customer.company || customer.clientName || t('emailComposer.entityFallback')}
      onGenerateEmail={handleGenerateEmail}
      onSendEmail={handleSendEmail}
      onScheduleSend={handleScheduleSend}
      onClose={onClose}
      onEmailSent={onEmailSent}
      embedded={embedded}
      userTemplates={userTemplates}
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

export default CustomerEmailComposer
