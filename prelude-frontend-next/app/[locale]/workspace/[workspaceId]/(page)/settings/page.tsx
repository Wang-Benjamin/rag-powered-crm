'use client'

import { useState, useEffect } from 'react'
import { useRouter, usePathname } from '@/i18n/navigation'
import { useTranslations, useLocale } from 'next-intl'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Globe, Check } from 'lucide-react'
import { settingsService } from '@/lib/api/settings'
import { setLocaleCookie } from '@/lib/locale'
import { toast } from 'sonner'

const LOCALE_OPTIONS = [
  { value: 'en', labelKey: 'en' as const },
  { value: 'zh-CN', labelKey: 'zhCN' as const },
] as const

export default function SettingsPage() {
  const router = useRouter()
  const pathname = usePathname()
  const t = useTranslations('settings')
  const currentLocale = useLocale()
  const [selectedLocale, setSelectedLocale] = useState(currentLocale)
  const [isSaving, setIsSaving] = useState(false)

  useEffect(() => {
    setSelectedLocale(currentLocale)
  }, [currentLocale])

  async function handleLocaleChange(newLocale: string) {
    if (newLocale === selectedLocale) return
    setIsSaving(true)
    try {
      await settingsService.updateLocalePreference(newLocale)
      setLocaleCookie(newLocale)
      setSelectedLocale(newLocale)
      router.replace(pathname, { locale: newLocale })
    } catch (error) {
      console.error('Failed to update locale:', error)
      toast.error(t('page.title'), { description: t('language.updateFailed') })
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="mx-auto mt-12 max-w-md">
      <div className="mb-6">
        <h1 className="title-page">{t('page.title')}</h1>
        <p className="mt-2 text-zinc-600">{t('page.description')}</p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center space-x-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-zinc-100">
              <Globe className="h-5 w-5 text-zinc-900" />
            </div>
            <CardTitle className="title-panel">{t('language.title')}</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <p className="mb-4 text-sm text-zinc-600">{t('language.description')}</p>
          <div className="space-y-2">
            {LOCALE_OPTIONS.map((option) => (
              <button
                key={option.value}
                onClick={() => handleLocaleChange(option.value)}
                disabled={isSaving}
                className={`flex w-full items-center justify-between rounded-md px-3 py-2 text-sm transition-colors ${
                  selectedLocale === option.value
                    ? 'bg-zinc-900 text-zinc-50'
                    : 'bg-zinc-50 text-zinc-900 hover:bg-zinc-100'
                } ${isSaving ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}`}
              >
                <span>{t(`language.${option.labelKey}`)}</span>
                {selectedLocale === option.value && <Check className="h-4 w-4" />}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
