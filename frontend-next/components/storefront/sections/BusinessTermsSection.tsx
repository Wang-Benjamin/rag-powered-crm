'use client'

import { useTranslations } from 'next-intl'
import type { FactoryTerms, UseFactoryProfileDraft } from '@/hooks/useFactoryProfileDraft'
import { Field, FieldRow, Notice, SectionShell, TextInput } from '../primitives'

interface BusinessTermsSectionProps {
  draft: UseFactoryProfileDraft
}

export function BusinessTermsSection({ draft }: BusinessTermsSectionProps) {
  const t = useTranslations('storefront')
  // Phase A canonical shape only — `<BusinessTermsSection>` is the source of
  // truth for what the buyer page shows. Legacy data written by the old
  // onboarding wizard at a flat `factory_details.{moq, lead_time, ...}` path
  // is intentionally NOT surfaced; the seller has to re-enter terms here
  // for them to publish.
  const terms: FactoryTerms = draft.factoryDetails.terms ?? {}

  const update = (patch: Partial<FactoryTerms>) => {
    draft.setFactoryField('terms', { ...terms, ...patch })
  }

  return (
    <SectionShell title={t('businessTerms.sectionTitle')}>
      <Notice>{t('businessTerms.notice')}</Notice>
      <FieldRow>
        <Field label={t('businessTerms.fields.moq')} htmlFor="t-moq">
          <TextInput
            id="t-moq"
            value={terms.moq ?? ''}
            onChange={(e) => update({ moq: e.target.value })}
          />
        </Field>
        <Field label={t('businessTerms.fields.leadTime')} htmlFor="t-lead">
          <TextInput
            id="t-lead"
            value={terms.leadTime ?? ''}
            onChange={(e) => update({ leadTime: e.target.value })}
          />
        </Field>
        <Field label={t('businessTerms.fields.samplePolicy')} htmlFor="t-sample">
          <TextInput
            id="t-sample"
            value={terms.samplePolicy ?? ''}
            onChange={(e) => update({ samplePolicy: e.target.value })}
          />
        </Field>
        <Field label={t('businessTerms.fields.shipping')} htmlFor="t-ship">
          <TextInput
            id="t-ship"
            value={terms.shipping ?? ''}
            onChange={(e) => update({ shipping: e.target.value })}
          />
        </Field>
        <Field label={t('businessTerms.fields.payment')} htmlFor="t-pay" full>
          <TextInput
            id="t-pay"
            value={terms.payment ?? ''}
            onChange={(e) => update({ payment: e.target.value })}
          />
        </Field>
      </FieldRow>
    </SectionShell>
  )
}
