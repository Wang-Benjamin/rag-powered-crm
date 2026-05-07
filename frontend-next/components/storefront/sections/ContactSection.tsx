'use client'

import { useTranslations } from 'next-intl'
import type { ContactInfo, UseFactoryProfileDraft } from '@/hooks/useFactoryProfileDraft'
import { Field, FieldRow, SectionShell, TextInput } from '../primitives'

interface ContactSectionProps {
  draft: UseFactoryProfileDraft
}

const LANG_KEYS = ['zh', 'en', 'both'] as const
type LangKey = (typeof LANG_KEYS)[number]

export function ContactSection({ draft }: ContactSectionProps) {
  const t = useTranslations('storefront')
  const contact: ContactInfo = draft.companyProfile.contact ?? {}
  const langs = new Set<string>(contact.languages ?? [])

  const update = (patch: Partial<ContactInfo>) => {
    draft.setCompanyField('contact', { ...contact, ...patch })
  }

  const toggleLang = (key: LangKey) => {
    const next = new Set(langs)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    update({ languages: Array.from(next) })
  }

  return (
    <SectionShell title={t('contact.sectionTitle')}>
      <FieldRow>
        <Field label={t('contact.fields.name')} htmlFor="c-name">
          <TextInput
            id="c-name"
            value={contact.name ?? ''}
            onChange={(e) => update({ name: e.target.value })}
          />
        </Field>
        <Field label={t('contact.fields.title')} htmlFor="c-role">
          <TextInput
            id="c-role"
            value={contact.title ?? ''}
            onChange={(e) => update({ title: e.target.value })}
          />
        </Field>
        <Field label={t('contact.fields.email')} htmlFor="c-email">
          <TextInput
            id="c-email"
            type="email"
            value={contact.email ?? ''}
            onChange={(e) => update({ email: e.target.value })}
          />
        </Field>
        <Field label={t('contact.fields.phone')} htmlFor="c-phone">
          <TextInput
            id="c-phone"
            value={contact.phone ?? ''}
            onChange={(e) => update({ phone: e.target.value })}
          />
        </Field>
        <Field label={t('contact.fields.languages')} full>
          <div className="flex flex-wrap gap-2">
            {LANG_KEYS.map((key) => {
              const on = langs.has(key)
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => toggleLang(key)}
                  className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                    on
                      ? 'border-zinc-900 bg-zinc-900 text-white'
                      : 'border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50'
                  }`}
                >
                  {t(`contact.languageOptions.${key}`)}
                </button>
              )
            })}
          </div>
        </Field>
      </FieldRow>
    </SectionShell>
  )
}
