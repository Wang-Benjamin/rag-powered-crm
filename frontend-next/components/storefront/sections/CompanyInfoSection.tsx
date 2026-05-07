'use client'

import { useTranslations } from 'next-intl'
import { AutofilledFieldHighlight } from '@/components/onboarding/customize-ai/ingestion/AutofilledFieldHighlight'
import { DocumentDropzone } from '@/components/onboarding/customize-ai/ingestion/DocumentDropzone'
import type { UseFactoryProfileDraft } from '@/hooks/useFactoryProfileDraft'
import {
  Disclosure,
  Field,
  FieldRow,
  SectionShell,
  TextArea,
  TextInput,
} from '../primitives'

interface CompanyInfoSectionProps {
  draft: UseFactoryProfileDraft
}

export function CompanyInfoSection({ draft }: CompanyInfoSectionProps) {
  const t = useTranslations('storefront')
  const {
    companyProfile,
    factoryDetails,
    autofilledKeys,
    setCompanyField,
    setFactoryField,
    handleIngestionReady,
    handleIngestionFailed,
  } = draft

  // Phase A canonical reads only — legacy wizard fields (`yearEstablished`,
  // `employees`) are intentionally NOT surfaced here. The seller has to
  // re-enter values through this form to publish them.
  const yearValue =
    companyProfile.yearFounded != null ? String(companyProfile.yearFounded) : ''
  const staffValue = companyProfile.staff ?? ''

  return (
    <SectionShell title={t('companyInfo.sectionTitle')}>
      <p className="mb-2 text-xs text-zinc-500">{t('companyInfo.dropHelper')}</p>
      <DocumentDropzone
        kind="company_profile"
        accept="application/pdf,.pdf"
        acceptLabel="PDF"
        maxSizeMB={50}
        label={t('companyInfo.dropLabel')}
        onReady={handleIngestionReady}
        onFailed={handleIngestionFailed}
      />
      <Disclosure trigger={t('companyInfo.manualTrigger')}>
        <FieldRow>
          <Field label={t('companyInfo.fields.nameEn')} htmlFor="f-name-en" full>
            <AutofilledFieldHighlight active={autofilledKeys.has('companyNameEn')}>
              <TextInput
                id="f-name-en"
                value={companyProfile.companyNameEn ?? ''}
                onChange={(e) => setCompanyField('companyNameEn', e.target.value)}
              />
            </AutofilledFieldHighlight>
          </Field>
          <Field label={t('companyInfo.fields.nameZh')} htmlFor="f-name-zh" full>
            <AutofilledFieldHighlight active={autofilledKeys.has('companyNameZh')}>
              <TextInput
                id="f-name-zh"
                value={companyProfile.companyNameZh ?? ''}
                onChange={(e) => setCompanyField('companyNameZh', e.target.value)}
              />
            </AutofilledFieldHighlight>
          </Field>
          <Field label={t('companyInfo.fields.tagline')} htmlFor="f-tag" full>
            <TextArea
              id="f-tag"
              rows={2}
              value={companyProfile.tagline ?? ''}
              onChange={(e) => setCompanyField('tagline', e.target.value)}
            />
          </Field>
          <Field label={t('companyInfo.fields.year')} htmlFor="f-year">
            <TextInput
              id="f-year"
              inputMode="numeric"
              value={yearValue}
              onChange={(e) => {
                const raw = e.target.value.trim()
                if (raw === '') {
                  setCompanyField('yearFounded', undefined)
                  return
                }
                const n = Number.parseInt(raw, 10)
                setCompanyField('yearFounded', Number.isFinite(n) ? n : undefined)
              }}
            />
          </Field>
          <Field label={t('companyInfo.fields.employees')} htmlFor="f-staff">
            <TextInput
              id="f-staff"
              value={staffValue}
              onChange={(e) => setCompanyField('staff', e.target.value)}
            />
          </Field>
          <Field label={t('companyInfo.fields.capacity')} htmlFor="f-cap">
            <TextInput
              id="f-cap"
              value={factoryDetails.capacity ?? ''}
              onChange={(e) => setFactoryField('capacity', e.target.value)}
            />
          </Field>
          <Field label={t('companyInfo.fields.exportShare')} htmlFor="f-exp">
            <TextInput
              id="f-exp"
              value={companyProfile.exportShare ?? ''}
              onChange={(e) => setCompanyField('exportShare', e.target.value)}
            />
          </Field>
        </FieldRow>
      </Disclosure>
    </SectionShell>
  )
}
