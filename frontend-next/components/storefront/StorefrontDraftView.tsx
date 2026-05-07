'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { toast } from 'sonner'
import { useFactoryProfileDraft } from '@/hooks/useFactoryProfileDraft'
import { BusinessTermsSection } from './sections/BusinessTermsSection'
import { CertificationsSection } from './sections/CertificationsSection'
import { CompanyInfoSection } from './sections/CompanyInfoSection'
import { ContactSection } from './sections/ContactSection'
import { FactoryImagesSection } from './sections/FactoryImagesSection'

function formatUpdatedAt(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString()
}

export function StorefrontDraftView() {
  const t = useTranslations('storefront')
  const draft = useFactoryProfileDraft()
  const [submitting, setSubmitting] = useState(false)

  const caption = draft.updatedAt
    ? t('submitZone.captionPending', { time: formatUpdatedAt(draft.updatedAt) })
    : t('submitZone.captionDraft')

  const handleSubmit = async () => {
    if (submitting) return
    setSubmitting(true)
    try {
      await draft.saveNow()
      toast.success(t('submitZone.savedToast'))
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : t('submitZone.saveFailed')
      toast.error(msg)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <CompanyInfoSection draft={draft} />
      <CertificationsSection />
      <BusinessTermsSection draft={draft} />
      <FactoryImagesSection draft={draft} />
      <ContactSection draft={draft} />

      <div className="mt-8 flex items-center justify-between rounded-lg border border-zinc-200 bg-white px-6 py-4">
        <span className="text-xs text-zinc-500">{caption}</span>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={submitting || draft.isLoading}
          className="rounded-md bg-zinc-900 px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-800 disabled:opacity-50"
        >
          {submitting ? t('submitZone.saving') : t('submitZone.submitDraft')}
        </button>
      </div>
    </div>
  )
}
